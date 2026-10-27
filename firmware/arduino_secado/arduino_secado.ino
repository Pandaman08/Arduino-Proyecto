// Control experimental de secado - Arduino Nano
//
// Mapeo conservado del sketch anterior:
//   DHT22 (o DHT21 confirmado físicamente) : D2
//   DS18B20                              : D3
//   LED verde/amarillo/rojo              : D4/D6/D5
//   Ventilador PWM                       : D9
//   LCD I2C                              : SDA=A4, SCL=A5, 0x27
//
// No se activa ningún relé de calefactor en esta configuración. Para usarlo
// primero debe confirmarse el hardware y una carga de baja tensión protegida.

#include <Arduino.h>
#include <DHT.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <LiquidCrystal_I2C.h>

#define DHT_SENSOR_TYPE DHT22
#define ENABLE_HEATER 0

const uint8_t PIN_DHT = 2;
const uint8_t PIN_ONEWIRE = 3;
const uint8_t PIN_LED_VERDE = 4;
const uint8_t PIN_LED_ROJO = 5;
const uint8_t PIN_LED_AMARILLO = 6;
const uint8_t PIN_VENTILADOR = 9;
const uint8_t PIN_FOCO_RELE = 8;  // Reservado; no activo mientras ENABLE_HEATER=0.

const unsigned long SAMPLE_INTERVAL_MS = 2000UL;
const unsigned long DS_CONVERSION_MS = 200UL;
const unsigned long CONTROL_WATCHDOG_MS = 15000UL;
const unsigned long HEATER_MIN_SWITCH_MS = 5000UL;
const float SETPOINT_MIN_C = 10.0;
const float SETPOINT_MAX_C = 50.0;
const float MAX_SAFE_GRAIN_C = 45.0;
const float HYSTERESIS_C = 0.8;

DHT dht(PIN_DHT, DHT_SENSOR_TYPE);
OneWire oneWire(PIN_ONEWIRE);
DallasTemperature sensorGrano(&oneWire);
LiquidCrystal_I2C lcd(0x27, 16, 2);

enum OperatingMode { MODE_MONITOREO, MODE_CONTROL };
OperatingMode modoActual = MODE_MONITOREO;

bool telemetriaActiva = false;
bool conversionPendiente = false;
bool alarmaSeguridad = false;
bool watchdogDisparado = false;
bool calefactorActivo = false;
bool sensorValido = false;
uint8_t pwmVentiladorFijo = 0;
uint8_t pwmVentiladorActual = 0;
unsigned long ultimoMuestreo = 0;
unsigned long inicioConversion = 0;
unsigned long ultimoComandoControl = 0;
unsigned long ultimoCambioCalefactor = 0;
unsigned long secuencia = 0;
float setpoint = 30.0;
float tempAmbiente = 0.0;
float humedadAmbiente = 0.0;
float tempGrano = 0.0;

char commandBuffer[80];
uint8_t commandLength = 0;

const char* modeName() {
  return modoActual == MODE_CONTROL ? "CONTROL" : "MONITOREO";
}

void setLeds(bool verde, bool amarillo, bool rojo) {
  digitalWrite(PIN_LED_VERDE, verde ? HIGH : LOW);
  digitalWrite(PIN_LED_AMARILLO, amarillo ? HIGH : LOW);
  digitalWrite(PIN_LED_ROJO, rojo ? HIGH : LOW);
}

void setHeater(bool enabled) {
#if ENABLE_HEATER
  unsigned long now = millis();
  if (enabled != calefactorActivo && (now - ultimoCambioCalefactor >= HEATER_MIN_SWITCH_MS || ultimoCambioCalefactor == 0)) {
    calefactorActivo = enabled;
    digitalWrite(PIN_FOCO_RELE, enabled ? HIGH : LOW);
    ultimoCambioCalefactor = now;
  }
#else
  (void)enabled;
  calefactorActivo = false;
#endif
}

void setFan(uint8_t pwm) {
  pwmVentiladorActual = pwm;
  analogWrite(PIN_VENTILADOR, pwm);
}

void safeOutputs() {
  setHeater(false);
  setFan(0);
  setLeds(false, false, false);
}

void alarmOutputs() {
  setHeater(false);
  setFan(255);
  setLeds(false, false, true);
}

void ack(const String& message) {
  Serial.print("ACK:");
  Serial.println(message);
}

void err(const String& message) {
  Serial.print("ERR:");
  Serial.println(message);
}

void refreshControlWatchdog() {
  ultimoComandoControl = millis();
  watchdogDisparado = false;
}

void showStatus() {
  Serial.print("ESTADO,modo=");
  Serial.print(modeName());
  Serial.print(",activo=");
  Serial.print(telemetriaActiva ? 1 : 0);
  Serial.print(",sp=");
  Serial.print(setpoint, 1);
  Serial.print(",foco=");
#if ENABLE_HEATER
  Serial.print(calefactorActivo ? 1 : 0);
#else
  Serial.print("NA");
#endif
  Serial.print(",vent=");
  Serial.print(pwmVentiladorActual);
  Serial.print(",seq=");
  Serial.println(secuencia);
}

void showLcd() {
  lcd.setCursor(0, 0);
  lcd.print("T:");
  lcd.print(tempAmbiente, 1);
  lcd.print(" G:");
  lcd.print(tempGrano, 1);
  lcd.print("   ");
  lcd.setCursor(0, 1);
  lcd.print(modeName());
  lcd.print(" H:");
  lcd.print(humedadAmbiente, 0);
  lcd.print("% ");
}

bool parseNumber(const String& text, float& value) {
  if (text.length() == 0) return false;
  value = text.toFloat();
  bool hasDigit = false;
  for (uint16_t i = 0; i < text.length(); ++i) {
    char c = text.charAt(i);
    if (c >= '0' && c <= '9') hasDigit = true;
    if ((c < '0' || c > '9') && c != '-' && c != '+' && c != '.') return false;
  }
  return hasDigit;
}

void setMode(OperatingMode newMode) {
  modoActual = newMode;
  telemetriaActiva = true;
  alarmaSeguridad = false;
  if (newMode == MODE_MONITOREO) {
    setHeater(false);
    setFan(pwmVentiladorFijo);
    setLeds(pwmVentiladorFijo > 0, pwmVentiladorFijo == 0, false);
  } else {
    setFan(0);
    setHeater(false);
    setLeds(false, true, false);
    refreshControlWatchdog();
  }
}

void applyControl() {
  if (!sensorValido) {
    safeOutputs();
    return;
  }
  if (tempGrano >= MAX_SAFE_GRAIN_C) {
    alarmaSeguridad = true;
    alarmOutputs();
    return;
  }
  alarmaSeguridad = false;
  if (modoActual == MODE_MONITOREO) {
    setHeater(false);
    setFan(pwmVentiladorFijo);
    setLeds(pwmVentiladorFijo > 0, pwmVentiladorFijo == 0, false);
    return;
  }

  // El equipo actual solo tiene ventilador. No se afirma que pueda calentar.
  if (tempGrano > setpoint + HYSTERESIS_C) {
    setFan(255);
    setLeds(false, false, false);
  } else if (tempGrano < setpoint - HYSTERESIS_C) {
    setFan(0);
    setLeds(true, false, false);
  } else {
    setLeds(false, true, false);
  }
#if ENABLE_HEATER
  if (tempGrano < setpoint - HYSTERESIS_C) setHeater(true);
  if (tempGrano > setpoint + HYSTERESIS_C) setHeater(false);
#else
  setHeater(false);
#endif
}

void emitTelemetry() {
  if (!telemetriaActiva || !sensorValido) return;
  ++secuencia;
  Serial.print("TEL,");
  Serial.print(secuencia);
  Serial.print(",");
  Serial.print(tempAmbiente, 2);
  Serial.print(",");
  Serial.print(humedadAmbiente, 2);
  Serial.print(",");
  Serial.print(tempGrano, 2);
  Serial.print(",");
  Serial.print(setpoint, 2);
  Serial.print(",");
  Serial.print(modeName());
  Serial.print(",");
#if ENABLE_HEATER
  Serial.print(calefactorActivo ? 1 : 0);
#else
  Serial.print("NA");
#endif
  Serial.print(",");
  Serial.println(pwmVentiladorActual);
}

void finishSensorConversion() {
  if (!conversionPendiente || millis() - inicioConversion < DS_CONVERSION_MS) return;
  float grain = sensorGrano.getTempCByIndex(0);
  conversionPendiente = false;
  if (grain == DEVICE_DISCONNECTED_C || grain < -10.0 || grain > 85.0) {
    sensorValido = false;
    err("SENSOR_DS18B20");
    safeOutputs();
    return;
  }
  tempGrano = grain;
  sensorValido = true;
  applyControl();
  showLcd();
  emitTelemetry();
}

void startSensorSample() {
  float amb = dht.readTemperature();
  float hum = dht.readHumidity();
  if (isnan(amb) || isnan(hum) || amb < -10.0 || amb > 80.0 || hum < 0.0 || hum > 100.0) {
    sensorValido = false;
    err("SENSOR_DHT");
    safeOutputs();
    return;
  }
  tempAmbiente = amb;
  humedadAmbiente = hum;
  sensorGrano.requestTemperatures();
  inicioConversion = millis();
  conversionPendiente = true;
}

void processCommand(String command) {
  command.trim();
  if (command.length() == 0) return;
  String upper = command;
  upper.toUpperCase();

  if (upper == "ESTADO") {
    showStatus();
    return;
  }
  if (upper == "PARAR" || upper == "P") {
    telemetriaActiva = false;
    safeOutputs();
    ack("PARAR_APLICADO");
    return;
  }
  if (upper == "MODO:MONITOREO" || upper == "MODO:ANTES") {
    setMode(MODE_MONITOREO);
    ack("MODO_MONITOREO_APLICADO");
    return;
  }
  if (upper == "MODO:CONTROL" || upper == "MODO:DESPUES" || upper == "MODO:DESPUÉS" || upper == "I") {
    setMode(MODE_CONTROL);
    ack("MODO_CONTROL_APLICADO");
    return;
  }
  if (upper == "V" || upper == "A" || upper == "R") {
    modoActual = MODE_MONITOREO;
    telemetriaActiva = true;
    pwmVentiladorFijo = upper == "V" ? 153 : (upper == "A" ? 255 : 0);
    setFan(pwmVentiladorFijo);
    setLeds(upper == "V", upper == "A", upper == "R");
    ack("ACTUADOR_FIJO_APLICADO");
    return;
  }
  if (upper == "1" || upper == "2" || upper == "0") {
    modoActual = MODE_MONITOREO;
    telemetriaActiva = true;
    pwmVentiladorFijo = upper == "1" ? 153 : (upper == "2" ? 255 : 0);
    setFan(pwmVentiladorFijo);
    setLeds(pwmVentiladorFijo > 0, pwmVentiladorFijo == 0, false);
    ack("ACTUADOR_FIJO_APLICADO");
    return;
  }
  if (upper.startsWith("SP:") || upper.startsWith("T:")) {
    String raw = command.substring(command.indexOf(':') + 1);
    float requested = 0.0;
    if (!parseNumber(raw, requested) || requested < SETPOINT_MIN_C || requested > SETPOINT_MAX_C) {
      err("SP_FUERA_DE_RANGO");
      return;
    }
    setpoint = requested;
    if (modoActual == MODE_CONTROL) refreshControlWatchdog();
    ack(modoActual == MODE_MONITOREO ? "SP_ACEPTADO_SIN_CAMBIO_ACTUADORES" : "SP_APLICADO_CONTROL");
    return;
  }
  if (upper.startsWith("VENT:")) {
    if (modoActual == MODE_CONTROL) {
      err("VENT_SOLO_MONITOREO");
      return;
    }
    float requested = 0.0;
    if (!parseNumber(command.substring(5), requested) || requested < 0 || requested > 255) {
      err("VENT_FUERA_DE_RANGO");
      return;
    }
    pwmVentiladorFijo = (uint8_t)requested;
    setFan(pwmVentiladorFijo);
    ack("VENT_FIJO_APLICADO");
    return;
  }
  if (upper.startsWith("D:")) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print(command.substring(2).substring(0, 16));
    ack("LCD_APLICADO");
    return;
  }
  err("COMANDO_INVALIDO");
}

void readSerialCommands() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (commandLength > 0) {
        commandBuffer[commandLength] = '\0';
        processCommand(String(commandBuffer));
        commandLength = 0;
      }
    } else if (commandLength < sizeof(commandBuffer) - 1) {
      commandBuffer[commandLength++] = c;
    } else {
      commandLength = 0;
      err("COMANDO_DEMASIADO_LARGO");
    }
  }
}

void setup() {
  pinMode(PIN_LED_VERDE, OUTPUT);
  pinMode(PIN_LED_AMARILLO, OUTPUT);
  pinMode(PIN_LED_ROJO, OUTPUT);
  pinMode(PIN_VENTILADOR, OUTPUT);
#if ENABLE_HEATER
  pinMode(PIN_FOCO_RELE, OUTPUT);
#endif
  safeOutputs();
  Serial.begin(9600);
  dht.begin();
  sensorGrano.begin();
  sensorGrano.setResolution(10);
  sensorGrano.setWaitForConversion(false);
  lcd.init();
  lcd.backlight();
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("SECADO SEGURO");
  lcd.setCursor(0, 1);
  lcd.print("MONITOREO OFF");
  Serial.println("SISTEMA,READY,MONITOREO,ACTUADORES_OFF");
}

void loop() {
  readSerialCommands();
  if (modoActual == MODE_CONTROL && telemetriaActiva && millis() - ultimoComandoControl > CONTROL_WATCHDOG_MS) {
    if (!watchdogDisparado) {
      watchdogDisparado = true;
      safeOutputs();
      err("WATCHDOG_CONTROL");
    }
  }
  finishSensorConversion();
  if (telemetriaActiva && !conversionPendiente && millis() - ultimoMuestreo >= SAMPLE_INTERVAL_MS) {
    ultimoMuestreo = millis();
    startSensorSample();
  }
}
