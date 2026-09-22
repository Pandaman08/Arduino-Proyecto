/*
  ==============================================================================
  Firmware Bidireccional Arduino Nano - Sistema de Secado de Café y Cacao
  ==============================================================================
  Conexión de Sensores:
    - DHT22 (Temperatura y Humedad Ambiente)   -> Pin Digital D2
    - DS18B20 (Temperatura en masa del Grano)  -> Pin Digital D3 (Pull-up 4.7k a 5V)
  
  Conexión de Actuadores y Pantalla:
    - LED Verde                                 -> Pin Digital D4
    - LED Amarillo                              -> Pin Digital D6 (Mapeo físico verificado)
    - LED Rojo                                  -> Pin Digital D5 (Mapeo físico verificado)
    - Ventilador (Control PWM)                  -> Pin Digital D9 (~PWM)
    - Pantalla LCD 16x2 I2C                     -> Pines A4 (SDA) y A5 (SCL) [Dirección 0x27 o 0x3F]
  
  Lógica de Control Automático de Temperatura Ideal (Demostración Rápida en Vivo):
    - 🟢 LED Verde: Temperatura ideal alcanzada (dentro de ±0.8°C).
      -> Ventilador APAGADO (PWM 0) para conservar la temperatura ideal.
    - 🟡 LED Amarillo: En camino / aproximándose a la ideal (entre 0.8°C y 2.2°C).
      -> Ventilador al 60% (~PWM 153) para estabilización suave.
    - 🔴 LED Rojo: Falta mucho / Alerta de desviación (> 2.2°C).
      -> Ventilador al 100% (PWM 255) a máxima potencia.
    - Reactivación: Si la temperatura se desvía nuevamente, el ventilador y los
      LEDs se reactivan automáticamente para mantenerla en el punto óptimo.
  
  Comandos Seriales Recibidos (9600 baudios):
    'T:XX.X'      : Fijar Temperatura Ideal predicha por el ML (ej. 'T:23.0')
    'V'           : Encender LED Verde manualmente
    'A'           : Encender LED Amarillo manualmente
    'R'           : Encender LED Rojo manualmente
    '1'           : Ventilador al 60% (~PWM 153) manual
    '2'           : Ventilador al 100% (PWM 255) manual
    '0'           : Apagar todo (LEDs, Ventilador a 0, Pantalla en reposo)
    'D:Tu Frase'  : Mostrar frase personalizada en la Pantalla LCD (hasta 32 caracteres)
    'I'           : Iniciar transmisión de telemetría y control térmico automático
    'P'           : Pausar transmisión de telemetría y apagar actuadores
  ==============================================================================
*/

#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <DHT.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// Definición de pines para Sensores
#define PIN_DHT 2
#define TIPO_DHT DHT22
#define PIN_ONEWIRE 3

// Definición de pines para Actuadores
#define PIN_LED_VERDE 4
#define PIN_LED_AMARILLO 6  // Pin D6: LED Amarillo
#define PIN_LED_ROJO 5      // Pin D5: LED Rojo
#define PIN_VENTILADOR 9    // Pin D9: Ventilador PWM

// Inicialización de Pantalla LCD 16x2 I2C (0x27 o 0x3F según fabricante)
LiquidCrystal_I2C lcd(0x27, 16, 2);

// Inicialización de librerías de sensores
DHT dht(PIN_DHT, TIPO_DHT);
OneWire oneWire(PIN_ONEWIRE);
DallasTemperature sensorGrano(&oneWire);

// Variables de estado y temporización
bool modoAnalisisActivo = true;        // Activo por defecto para respuesta inmediata en demostración
unsigned long ultimaLecturaMs = 0;
const unsigned long INTERVALO_ENVIO_MS = 2000;

// Parámetros de Control Térmico Automático (Consigna ML Prototipo -15°C para Demo en Vivo)
// Umbrales calibrados para demostración en vivo inmediata:
// - Reposo (~22.5°C - 23.5°C): 🟢 LED Verde (±0.8°C, Fan OFF)
// - Tocar sensor con dedos (24°C - 25°C): 🟡 LED Amarillo (0.8°C a 2.2°C, Fan 60%)
// - Sujetar sensor firmemente (> 25.2°C): 🔴 LED Rojo (> 2.2°C, Fan 100%)
float tempIdeal = 23.0;               // Temperatura ideal prototipo calibrada para demostración en vivo (°C)
const float TOLERANCIA_IDEAL = 0.8;   // ±0.8 °C: Ideal alcanzada (Verde, Fan OFF)
const float UMBRAL_CERCA = 2.2;       // Hasta 2.2 °C de distancia: En camino (Amarillo, Fan 60%)
                                      // Más de 2.2 °C: Falta mucho / Desviación (Rojo, Fan 100%)

// Variables de diagnóstico en tiempo real
int pwmVentiladorActual = 0;
char estadoLedActual = '0';           // 'V', 'A', 'R', '0'

// Declaración previa de funciones
void mostrarEnLCD(String texto);
void apagarTodo();
void regularTemperaturaYActuadores(float tempActual);

void setup() {
  Serial.begin(9600);

  // Configurar actuadores
  pinMode(PIN_LED_VERDE, OUTPUT);
  pinMode(PIN_LED_AMARILLO, OUTPUT);
  pinMode(PIN_LED_ROJO, OUTPUT);
  pinMode(PIN_VENTILADOR, OUTPUT);

  // Inicializar Display LCD
  lcd.init();
  lcd.backlight();
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("SECADO CAFE IA  ");
  lcd.setCursor(0, 1);
  lcd.print("Id:23.0C LISTO  ");

  apagarTodo();

  // Inicializar sensores
  dht.begin();
  sensorGrano.begin();
  sensorGrano.setResolution(10); // Resolución 10 bits (0.25°C): muestreo rápido 187ms para respuesta ágil

  delay(1000);
  Serial.println("SISTEMA_LISTO");
}

void loop() {
  // ---------------------------------------------------------------------------
  // 1. ESCUCHA DE COMANDOS DESDE STREAMLIT (Bidireccional)
  // ---------------------------------------------------------------------------
  if (Serial.available() > 0) {
    char comando = Serial.read();

    switch (comando) {
      // --- Consigna de Temperatura Ideal desde Modelo ML de Streamlit ---
      case 'T':
      case 't': {
        delay(25); // Espera breve para asegurar la llegada completa del valor
        String valorStr = Serial.readStringUntil('\n');
        valorStr.trim();
        if (valorStr.startsWith(":")) {
          valorStr = valorStr.substring(1);
          valorStr.trim();
        }
        float nuevaTemp = valorStr.toFloat();
        if (nuevaTemp >= 10.0 && nuevaTemp <= 50.0) {
          tempIdeal = nuevaTemp;
          Serial.print("ACK: Temp Ideal fijada a ");
          Serial.print(tempIdeal, 1);
          Serial.println(" C");

          // Actualización visual inmediata en la pantalla LCD
          if (modoAnalisisActivo) {
            sensorGrano.requestTemperatures();
            float tg = sensorGrano.getTempCByIndex(0);
            if (tg == DEVICE_DISCONNECTED_C || tg < -40.0 || tg > 100.0) {
              tg = dht.readTemperature();
            }
            if (!isnan(tg)) {
              regularTemperaturaYActuadores(tg);
              lcd.setCursor(0, 1);
              lcd.print("G:");
              lcd.print(tg, 1);
              lcd.print("C Id:");
              lcd.print(tempIdeal, 1);
              lcd.print("C");
            }
          } else {
            lcd.clear();
            lcd.setCursor(0, 0);
            lcd.print("CONSIGNA IDEAL: ");
            lcd.setCursor(0, 1);
            lcd.print("T.Ideal: ");
            lcd.print(tempIdeal, 1);
            lcd.print("C ");
          }
        } else {
          Serial.println("ERR: Temp ideal fuera de rango (10-50 C)");
        }
        break;
      }

      // --- Prueba de Pantalla LCD ---
      case 'D':
      case 'd': {
        delay(35); // Breve espera para que el buffer serie reciba todo el texto
        String texto = Serial.readStringUntil('\n');
        texto.trim();
        if (texto.startsWith(":")) {
          texto = texto.substring(1);
          texto.trim();
        }
        mostrarEnLCD(texto);
        Serial.print("ACK: Display: ");
        Serial.println(texto);
        break;
      }

      // --- Control Manual de Indicadores Luminosos ---
      case 'V':
      case 'v':
        digitalWrite(PIN_LED_VERDE, HIGH);
        digitalWrite(PIN_LED_AMARILLO, LOW);
        digitalWrite(PIN_LED_ROJO, LOW);
        estadoLedActual = 'V';
        Serial.println("ACK: LED Verde Encendido");
        break;

      case 'A':
      case 'a':
        digitalWrite(PIN_LED_VERDE, LOW);
        digitalWrite(PIN_LED_AMARILLO, HIGH);
        digitalWrite(PIN_LED_ROJO, LOW);
        estadoLedActual = 'A';
        Serial.println("ACK: LED Amarillo Encendido");
        break;

      case 'R':
      case 'r':
        digitalWrite(PIN_LED_VERDE, LOW);
        digitalWrite(PIN_LED_AMARILLO, LOW);
        digitalWrite(PIN_LED_ROJO, HIGH);
        estadoLedActual = 'R';
        Serial.println("ACK: LED Rojo Encendido");
        break;

      // --- Control Manual de Ventilación ---
      case '1':
        analogWrite(PIN_VENTILADOR, 153); // ~60% PWM
        pwmVentiladorActual = 153;
        Serial.println("ACK: Ventilador 60%");
        break;

      case '2':
        analogWrite(PIN_VENTILADOR, 255); // 100% PWM
        pwmVentiladorActual = 255;
        Serial.println("ACK: Ventilador 100%");
        break;

      case '0':
        apagarTodo();
        Serial.println("ACK: Todo Apagado");
        break;

      // --- Telemetría y Análisis Térmico Automático ---
      case 'I':
      case 'i':
        modoAnalisisActivo = true;
        ultimaLecturaMs = millis() - INTERVALO_ENVIO_MS;
        Serial.println("ACK: Analisis Iniciado");
        break;

      case 'P':
      case 'p':
        modoAnalisisActivo = false;
        apagarTodo();
        Serial.println("ACK: Analisis Pausado");
        mostrarEnLCD("ANALISIS PAUSADO");
        break;

      default:
        // Ignorar retornos de carro o saltos de línea sueltos
        break;
    }
  }

  // ---------------------------------------------------------------------------
  // 2. TRANSMISIÓN DE TELEMETRÍA Y REGULACIÓN TÉRMICA EN LAZO CERRADO
  // ---------------------------------------------------------------------------
  if (modoAnalisisActivo) {
    unsigned long tiempoActual = millis();

    if (tiempoActual - ultimaLecturaMs >= INTERVALO_ENVIO_MS) {
      ultimaLecturaMs = tiempoActual;

      // Lectura de sensor DHT22 (Ambiente)
      float humAmbiente = dht.readHumidity();
      float tempAmbiente = dht.readTemperature();

      // Lectura de sensor DS18B20 (Grano en masa)
      sensorGrano.requestTemperatures();
      float tempGrano = sensorGrano.getTempCByIndex(0);

      // Verificación de integridad de sensores
      bool dhtValido = !isnan(humAmbiente) && !isnan(tempAmbiente);
      bool dsValido = (tempGrano != DEVICE_DISCONNECTED_C) && (tempGrano > -40.0) && (tempGrano < 100.0);

      if (dhtValido && dsValido) {
        // 1. Envío de Telemetría Serial CSV (TempAmbiente,Humedad,TempGrano)
        Serial.print(tempAmbiente, 1);
        Serial.print(",");
        Serial.print(humAmbiente, 1);
        Serial.print(",");
        Serial.println(tempGrano, 1);

        // 2. Control Automático: Regular ventilador y LEDs hacia la tempIdeal
        float tempControl = dsValido ? tempGrano : tempAmbiente;
        regularTemperaturaYActuadores(tempControl);

        // 3. Actualización de Pantalla LCD 16x2
        // Fila 0: Temperatura Ambiente y Humedad (ej. "A:28.5C H:65%   ")
        lcd.setCursor(0, 0);
        lcd.print("A:");
        lcd.print(tempAmbiente, 1);
        lcd.print("C H:");
        lcd.print((int)humAmbiente);
        lcd.print("%   ");

        // Fila 1: Temperatura del Grano y Temperatura Ideal ML (ej. "G:32.1C Id:38.0C")
        lcd.setCursor(0, 1);
        lcd.print("G:");
        lcd.print(tempGrano, 1);
        lcd.print("C Id:");
        lcd.print(tempIdeal, 1);
        lcd.print("C");
      }
    }
  }
}

// -----------------------------------------------------------------------------
// Función de Control Térmico en Lazo Cerrado (Ventilador + Semáforo LED)
// -----------------------------------------------------------------------------
void regularTemperaturaYActuadores(float tempActual) {
  float diferencia = abs(tempActual - tempIdeal);

  if (diferencia <= TOLERANCIA_IDEAL) {
    // --- ESTADO 1: TEMPERATURA IDEAL ALCANZADA ---
    // Encender únicamente LED Verde
    digitalWrite(PIN_LED_VERDE, HIGH);
    digitalWrite(PIN_LED_AMARILLO, LOW);
    digitalWrite(PIN_LED_ROJO, LOW);

    // Apagar ventilador para preservar la temperatura alcanzada
    analogWrite(PIN_VENTILADOR, 0);
    pwmVentiladorActual = 0;
    estadoLedActual = 'V';
  } 
  else if (diferencia <= UMBRAL_CERCA) {
    // --- ESTADO 2: EN CAMINO / CERCA DE LA TEMPERATURA IDEAL ---
    // Encender únicamente LED Amarillo
    digitalWrite(PIN_LED_VERDE, LOW);
    digitalWrite(PIN_LED_AMARILLO, HIGH);
    digitalWrite(PIN_LED_ROJO, LOW);

    // Ventilador a velocidad moderada (~60%) para aproximación controlada
    analogWrite(PIN_VENTILADOR, 153);
    pwmVentiladorActual = 153;
    estadoLedActual = 'A';
  } 
  else {
    // --- ESTADO 3: FALTA MUCHO PARA LLEGAR A LA TEMPERATURA IDEAL ---
    // Encender únicamente LED Rojo
    digitalWrite(PIN_LED_VERDE, LOW);
    digitalWrite(PIN_LED_AMARILLO, LOW);
    digitalWrite(PIN_LED_ROJO, HIGH);

    // Ventilador al 100% de potencia para acelerar la estabilización
    analogWrite(PIN_VENTILADOR, 255);
    pwmVentiladorActual = 255;
    estadoLedActual = 'R';
  }
}

// Función para mostrar texto formateado en 2 líneas de 16 caracteres
void mostrarEnLCD(String texto) {
  lcd.clear();
  if (texto.length() == 0) {
    return;
  }

  if (texto.length() <= 16) {
    lcd.setCursor(0, 0);
    lcd.print(texto);
  } else {
    // Primera fila (primeros 16 caracteres)
    lcd.setCursor(0, 0);
    lcd.print(texto.substring(0, 16));
    // Segunda fila (siguientes hasta 16 caracteres)
    lcd.setCursor(0, 1);
    lcd.print(texto.substring(16, min((int)texto.length(), 32)));
  }
}

// Apagar todos los actuadores y restablecer estado seguro
void apagarTodo() {
  digitalWrite(PIN_LED_VERDE, LOW);
  digitalWrite(PIN_LED_AMARILLO, LOW);
  digitalWrite(PIN_LED_ROJO, LOW);
  analogWrite(PIN_VENTILADOR, 0);
  pwmVentiladorActual = 0;
  estadoLedActual = '0';
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("STANDBY LISTO   ");
  lcd.setCursor(0, 1);
  lcd.print("T.Ideal: ");
  lcd.print(tempIdeal, 1);
  lcd.print("C ");
}

