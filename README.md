# ☕ Monitor IoT - Secado de Granos con IA (Café y Cacao)

Sistema de **Puerta de Enlace Inteligente (IoT Edge Gateway)** para el monitoreo en tiempo real y la predicción del tiempo restante de deshidratación en granos de café y cacao, combinando telemetría de sensores industriales (DHT22 y DS18B20), microcontroladores Arduino y algoritmos de Machine Learning (**Random Forest Regressor** de Scikit-Learn) desplegados en una interfaz web moderna con **Streamlit**.

---

## 🏛️ Arquitectura del Sistema

El proyecto sigue una estructura desacoplada (**Clean Architecture / Separation of Concerns**):

```text
Arduino-Proyecto/
├── .gitignore                         # Exclusiones de Git (cachés, entornos, modelos)
├── README.md                          # Documentación integral del proyecto
├── requirements.txt                   # Dependencias fijadas para el entorno
├── app.py                             # Orquestador liviano y punto de entrada (Streamlit)
│
├── data/                              # Datasets locales de entrenamiento
│   └── dataset_secado_cafe.csv
│
├── models/                            # Artefactos serializados del modelo (.pkl)
│   └── modelo_secado.pkl
│
├── firmware/                          # Código fuente del microcontrolador
│   └── arduino_secado/
│       └── arduino_secado.ino         # Sketch Arduino Nano con temporización no bloqueante
│
├── src/                               # Módulos Python del Gateway
│   ├── config.py                      # Rutas multiplataforma (Pathlib) y constantes
│   ├── hardware/                      # Abstracción de comunicación serial y filtrado de ruido
│   │   └── serial_manager.py          # SerialManager, TelemetryReading y simulador
│   ├── ml/                            # Motor de Inteligencia Artificial
│   │   └── model_manager.py           # DryingPredictor, métricas y evaluación agronómica
│   └── ui/                            # Capa de presentación visual
│       ├── styles.py                  # Tokens de diseño y hojas de estilo CSS
│       └── components.py              # Tarjetas de métricas, gráficos en vivo y sidebar
│
└── tests/                             # Suite de pruebas unitarias automatizadas
    ├── test_hardware.py               # Validación de tramas y rechazo de ruido eléctrico
    └── test_ml.py                     # Validación de inferencia, entrenamiento y consistencia
```

---

## 🔌 Hardware y Conexiones

El microcontrolador **Arduino Nano** muestrea las variables cada **2 segundos** y envía una trama CSV limpia:
```text
Temp_Ambiente,Humedad_Ambiente,Temp_Grano
Ejemplo: 28.5,65.0,26.2
```

### Diagrama de Conexión de Sensores
* **DHT22** (Temperatura y Humedad Ambiente):
  * `VCC` -> `5V` (Arduino)
  * `GND` -> `GND` (Arduino)
  * `DATA` -> `Pin Digital D2`
* **DS18B20** (Temperatura interna en masa de grano):
  * `VCC` -> `5V`
  * `GND` -> `GND`
  * `DATA` -> `Pin Digital D3` *(con resistencia pull-up de 4.7kΩ conectada entre DATA y 5V)*.

---

## 🚀 Instalación y Puesta en Marcha

### 1. Clonar o descargar el repositorio
```bash
git clone <url-del-repositorio>
cd Arduino-Proyecto
```

### 2. Crear entorno virtual (Recomendado)
* **Linux / macOS:**
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```
* **Windows:**
  ```powershell
  python -m venv .venv
  .venv\Scripts\Activate.ps1
  ```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Permisos de puerto serie (Solo en Linux)
Para evitar errores de permisos al abrir `/dev/ttyUSB0` o `/dev/ttyACM0`:
```bash
sudo usermod -a -G dialout $USER
```
*(Reinicia sesión para que el cambio de grupo surta efecto).*

### 5. Ejecutar la aplicación
```bash
streamlit run app.py
```
La aplicación abrirá automáticamente el navegador en `http://localhost:8501`.

---

## 🧪 Pruebas Unitarias Automatizadas

El proyecto incluye tests con `pytest` para garantizar la estabilidad del software:
```bash
pytest tests/ -v
```

Casos de prueba evaluados:
* Decodificación y parseo de tramas válidas.
* Rechazo y aislamiento de ruido eléctrico (líneas truncadas, valores corruptos).
* Validación de rangos físicos de los sensores.
* Generación determinista de datasets sintéticos.
* Pipeline de reentrenamiento, persistencia e inferencia de Machine Learning.
* Activación de alertas de sobrecalentamiento crítico del grano ($>45^\circ\text{C}$).

---

## 🛡️ Robustez y Tolerancia a Fallos

1. **Aislamiento de Ruido Eléctrico**: Las tramas con anomalías de transmisión son interceptadas por `try/except ValueError` y registradas en el monitor de depuración sin detener la interfaz.
2. **Tolerancia a Desconexión Física**: Si el cable USB del Arduino es desconectado, `serial.SerialException` y `OSError` capturan el evento, liberan el descriptor de archivo de forma segura y muestran una alerta visual en la UI.
3. **Modo Simulación**: Permite operar la interfaz y verificar el modelo de IA en tiempo real sin requerir el hardware físico conectado.
