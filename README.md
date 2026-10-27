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
├── app.py                             # Orquestador de las seis secciones Streamlit
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
│   ├── hardware/                      # Parseo serial usado por el puente independiente
│   │   └── serial_manager.py          # SerialManager, TelemetryReading y simulador
│   ├── ml/                            # Motor de Inteligencia Artificial
│   │   └── model_manager.py           # DryingPredictor, métricas y evaluación agronómica
│   ├── mqtt/                          # Cliente EMQX, puente y adaptador Streamlit
│   ├── persistence/                   # SQLite, experimentos, mediciones e historial
│   ├── services/                      # Procesamiento de telemetría y predicción
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

### Streamlit, MQTT y demostración

La interfaz no abre directamente el puerto del Arduino. Para control físico,
ejecuta el puente en otro proceso y configura `MQTT_STREAMLIT_ENABLED=true`.
Sin MQTT, activa **Modo demostración** en la barra lateral: los datos se marcan
como simulados y no se mezclan con mediciones reales.

Las seis secciones disponibles son Dashboard general, Gestión de experimentos,
Control de hardware, Historial, Comparación ANTES/DESPUÉS e IA y diagnóstico.
El modelo Random Forest predice tiempo restante; no genera una temperatura ideal.

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

---

## Arquitectura final y flujo de datos

```text
Arduino Nano ──USB/Serial──> bridge_cli ──WSS/TLS──> EMQX
                                      │                    │
                                      └── SQLite            ├── Streamlit
                                          (experimentos)   └── recorder_cli
```

Streamlit no abre el puerto serial. El puente es el único proceso autorizado a
usar el Arduino físico; los nodos virtuales publican únicamente telemetría
marcada como `simulado=true` y no suscriben comandos.

El flujo experimental es:

```text
crear corrida → seleccionar ANTES/DESPUÉS → iniciar con ACK
→ registrar mediciones → pausar/reanudar → finalizar
→ calcular indicadores → comparar por pair_id
```

## EMQX y protocolo MQTT

La infraestructura utilizada es el broker existente del equipo:

```text
Host: cafes.duckdns.org
Transporte: MQTT sobre WebSockets seguros
Endpoint: wss://cafes.duckdns.org/mqtt
Puerto: 443
TLS: verificación de certificado habilitada
```

Los tópicos conservados son:

```text
secado/<nodo>/telemetria
secado/<nodo>/estado
secado/<nodo>/cmd
secado/<nodo>/ack
```

La telemetría contiene `node_id`, timestamp UTC, secuencia, `t_amb`, `hum`,
`t_grano`, `sp` cuando existe, `modo`, `vent` cuando el firmware lo reporta,
`foco` cuando existe, `simulado` y `version`. El puente acepta tanto la trama
serial enriquecida `TEL,...` como el CSV legado de tres campos.

No se almacenan credenciales administrativas en el repositorio. Configura un
`.env` local a partir de `.env.example` con credenciales de aplicación MQTT.

## Comandos de ejecución

### Linux/macOS

```bash
source .venv/bin/activate
cp .env.example .env
# Editar .env y completar credenciales de aplicación si EMQX las requiere

streamlit run app.py
python -m src.mqtt.bridge_cli --port /dev/ttyUSB0 --node-id secador_01
python -m src.mqtt.recorder_cli --experiment-id ID --node-id secador_01
python -m src.mqtt.virtual_nodes_cli --interval 2
python -m src.mqtt.check_connection --timeout 5 --node-id nodo_prueba --publish-test
```

### Windows PowerShell

```powershell
.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
# Editar .env y completar credenciales de aplicación si EMQX las requiere

streamlit run app.py
python -m src.mqtt.bridge_cli --port COM3 --node-id secador_01
python -m src.mqtt.recorder_cli --experiment-id ID --node-id secador_01
python -m src.mqtt.virtual_nodes_cli --interval 2
python -m src.mqtt.check_connection --timeout 5 --node-id nodo_prueba --publish-test
```

No ejecutes simultáneamente Streamlit y otro proceso que intente abrir el mismo
puerto serial. La interfaz debe comunicarse por MQTT cuando se usa hardware.

## Experimentos ANTES/DESPUÉS

- `ANTES` utiliza `MODO:MONITOREO` y actuadores fijos definidos antes de iniciar.
- `DESPUÉS` utiliza `MODO:CONTROL`; el firmware aplica sus reglas e histéresis.
- La fase y el origen son inmutables después del inicio.
- Una corrida real solo se inicia cuando el puente recibe confirmación del
  Arduino; un rechazo se conserva como ACK/ERR y no se presenta como éxito.
- `pair_id` es el único criterio para comparar corridas pareadas.
- Las corridas simuladas se excluyen del análisis real por defecto.

## Indicadores y estadística

Los cálculos están en [src/analysis/indicators.py](src/analysis/indicators.py) y
[src/analysis/statistics.py](src/analysis/statistics.py). Se usan timestamps
reales y ponderación por los intervalos entre lecturas.

Se calculan duración con criterio de finalización, pérdida relativa de masa,
MAE térmico, porcentaje dentro de `referencia ± 0.8 °C`, humedad ambiental
promedio, temperatura promedio, energía estimada y MAE/RMSE predictivo cuando
existen tiempos reales de finalización. La pérdida de masa no se convierte en
humedad interna del grano.

Las pruebas disponibles son t pareada, Wilcoxon, t de Welch y Mann-Whitney.
Shapiro se aplica a diferencias pareadas cuando hay tamaño suficiente y no son
constantes. Un p-valor no se interpreta automáticamente como mejora: también se
reportan magnitud, dirección, tamaño muestral, intervalo y limitaciones.

La interfaz permite descargar CSV, Excel, PDF y gráficos PNG mediante
[src/analysis/reports.py](src/analysis/reports.py).

## Random Forest

El modelo conserva `RandomForestRegressor` y utiliza:

```text
Entradas: Temp_Ambiente, Humedad_Ambiente, Temp_Grano
Objetivo: Tiempo_Restante_Horas
```

El dataset actual es sintético local y sirve únicamente para demostrar el flujo
de inferencia. No constituye validación agronómica. El modelo no calcula la
temperatura ideal ni reemplaza el setpoint del firmware.

Si el modelo serializado fue creado con otra versión de scikit-learn, la carga
detecta la incompatibilidad y lo reentrena con el dataset local. Para futuros
datos reales existe `train_from_labeled_runs`, que exige una etiqueta `run_id` y
separa entrenamiento/prueba por corrida para evitar fuga temporal. No se
reentrenan modelos automáticamente con lecturas sin etiqueta de tiempo restante.

## Pruebas y auditoría

```bash
pytest tests/ -v
```

La suite cubre hardware y CSV, MQTT con mocks, persistencia SQLite, duplicados,
experimentos, indicadores, datos faltantes, comparaciones, estadística y
exportación. AppTest verifica las seis secciones principales de Streamlit.

Las pruebas locales no sustituyen la verificación física del Arduino ni una
conclusión experimental. La conectividad contra EMQX debe distinguirse de las
pruebas con mocks y no requiere enviar comandos reales durante una prueba de
diagnóstico.

## Problemas conocidos y trabajo futuro

- Aún no hay suficientes corridas reales para afirmar mejoras ANTES/DESPUÉS.
- Deben confirmarse físicamente el tipo DHT, el LCD, el driver del ventilador y
  la ausencia/autorización de un relé de calefactor.
- Las estimaciones de energía requieren potencia nominal confiable o medición
  eléctrica; PWM no equivale automáticamente a vatios.
- Se debe incorporar un dataset real etiquetado por corrida/lote antes de usar
  el modelo con fines académicos concluyentes.
- La siguiente fase puede abordar mejoras adicionales de despliegue, pero esta
  versión no incorpora Google Earth Engine, servicios cloud nuevos ni otro
  broker MQTT.
