/*
  ==============================================================================
  Firmware Bidireccional Arduino Nano - Sistema de Secado de Café y Cacao
  ==============================================================================
  Conexión de Sensores:
    - DHT22 (Temperatura y Humedad Ambiente)   -> Pin Digital D2
    - DS18B20 (Temperatura en masa del Grano)  -> Pin Digital D3 (Pull-up 4.7k a 5V)
  
  Conexión de Actuadores y Pantalla:
    - LED Verde                                 -> Pin Digital D4
    - LED Amarillo                              -> Pin Digital D6 (Corregido mapeo físico)
    - LED Rojo                                  -> Pin Digital D5 (Corregido mapeo físico)
    - Ventilador (Control PWM)                  -> Pin Digital D9 (~PWM)
    - Pantalla LCD 16x2 I2C                     -> Pines A4 (SDA) y A5 (SCL) [Dirección 0x27 o 0x3F]
  
  Comandos Seriales Recibidos (9600 baudios):
    'V'           : Encender LED Verde
    'A'           : Encender LED Amarillo
    'R'           : Encender LED Rojo
    '1'           : Ventilador al 60% (~PWM 153)
    '2'           : Ventilador al 100% (PWM 255)
    '0'           : Apagar todo (LEDs, Ventilador a 0, Pantalla en reposo)
    'D:Tu Frase'  : Mostrar frase personalizada en la Pantalla LCD (hasta 32 caracteres)
    'I'           : Iniciar transmisión periódica de telemetría (cada 2s)
    'P'           : Pausar transmisión de telemetría
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
bool modoAnalisisActivo = false;
unsigned long ultimaLecturaMs = 0;
const unsigned long INTERVALO_ENVIO_MS = 2000;

// Declaración previa de funciones
void mostrarEnLCD(String texto);
void apagarTodo();

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
  lcd.print("SECADO CAFE IA");
  lcd.setCursor(0, 1);
  lcd.print("SISTEMA LISTO");

  apagarTodo();

  // Inicializar sensores
  dht.begin();
  sensorGrano.begin();

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

      // --- Prueba de Indicadores Luminosos ---
      case 'V':
      case 'v':
        digitalWrite(PIN_LED_VERDE, HIGH);
        Serial.println("ACK: LED Verde Encendido");
        break;

      case 'A':
      case 'a':
        digitalWrite(PIN_LED_AMARILLO, HIGH);
        Serial.println("ACK: LED Amarillo Encendido");
        break;

      case 'R':
      case 'r':
        digitalWrite(PIN_LED_ROJO, HIGH);
        Serial.println("ACK: LED Rojo Encendido");
        break;

      // --- Control de Ventilación ---
      case '1':
        analogWrite(PIN_VENTILADOR, 153); // ~60% PWM
        Serial.println("ACK: Ventilador 60%");
        break;

      case '2':
        analogWrite(PIN_VENTILADOR, 255); // 100% PWM
        Serial.println("ACK: Ventilador 100%");
        break;

      case '0':
        apagarTodo();
        Serial.println("ACK: Todo Apagado");
        break;

      // --- Telemetría y Análisis ---
      case 'I':
      case 'i':
        modoAnalisisActivo = true;
        ultimaLecturaMs = millis() - INTERVALO_ENVIO_MS;
        Serial.println("ACK: Analisis Iniciado");
        break;

      case 'P':
      case 'p':
        modoAnalisisActivo = false;
        Serial.println("ACK: Analisis Pausado");
        lcd.clear();
        lcd.setCursor(0, 0);
        lcd.print("ANALISIS PAUSADO");
        break;

      default:
        // Ignorar retornos de carro o saltos de línea sueltos
        break;
    }
  }

  // ---------------------------------------------------------------------------
  // 2. TRANSMISIÓN PERIÓDICA DE TELEMETRÍA (Solo si 'I' está activo)
  // ---------------------------------------------------------------------------
  if (modoAnalisisActivo) {
    unsigned long tiempoActual = millis();

    if (tiempoActual - ultimaLecturaMs >= INTERVALO_ENVIO_MS) {
      ultimaLecturaMs = tiempoActual;

      // Lectura de sensor DHT22
      float humAmbiente = dht.readHumidity();
      float tempAmbiente = dht.readTemperature();

      // Lectura de sensor DS18B20
      sensorGrano.requestTemperatures();
      float tempGrano = sensorGrano.getTempCByIndex(0);

      // Verificación de integridad de sensores
      bool dhtValido = !isnan(humAmbiente) && !isnan(tempAmbiente);
      bool dsValido = (tempGrano != DEVICE_DISCONNECTED_C) && (tempGrano > -40.0) && (tempGrano < 100.0);

      if (dhtValido && dsValido) {
        // Formato CSV requerido: TempAmbiente,Humedad,TempGrano
        Serial.print(tempAmbiente, 1);
        Serial.print(",");
        Serial.print(humAmbiente, 1);
        Serial.print(",");
        Serial.println(tempGrano, 1);

        // Actualizar LCD en modo análisis
        lcd.setCursor(0, 0);
        lcd.print("A:");
        lcd.print(tempAmbiente, 1);
        lcd.print("C H:");
        lcd.print((int)humAmbiente);
        lcd.print("%  ");
        
        lcd.setCursor(0, 1);
        lcd.print("Grano:");
        lcd.print(tempGrano, 1);
        lcd.print("C    ");
      }
    }
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

// Apagar actuadores
void apagarTodo() {
  digitalWrite(PIN_LED_VERDE, LOW);
  digitalWrite(PIN_LED_AMARILLO, LOW);
  digitalWrite(PIN_LED_ROJO, LOW);
  analogWrite(PIN_VENTILADOR, 0);
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("STANDBY / LISTO");
}
