"""
Módulo de Configuración Global del Gateway IoT.
Centraliza constantes de hardware, límites físicos de sensores y rutas agnósticas al SO.
"""

from pathlib import Path
from typing import List

# ==============================================================================
# RUTAS DEL SISTEMA (Multiplataforma con Pathlib)
# ==============================================================================
BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = BASE_DIR / "data"
MODELS_DIR: Path = BASE_DIR / "models"
FIRMWARE_DIR: Path = BASE_DIR / "firmware"

# Asegurar existencia de directorios de almacenamiento
DATA_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

DATASET_PATH: Path = DATA_DIR / "dataset_secado_cafe.csv"
MODEL_PATH: Path = MODELS_DIR / "modelo_secado.pkl"

# ==============================================================================
# PARÁMETROS DE HARDWARE Y COMUNICACIÓN SERIAL
# ==============================================================================
BAUD_RATES: List[int] = [9600, 19200, 38400, 57600, 115200]
DEFAULT_BAUDRATE: int = 9600
SERIAL_TIMEOUT_SECONDS: float = 2.5
SERIAL_STABILIZATION_DELAY: float = 1.5

# ==============================================================================
# LÍMITES FÍSICOS DE SENSORES Y SEGURIDAD AGRONÓMICA
# ==============================================================================
TEMP_MIN_CELSIUS: float = -10.0
TEMP_MAX_CELSIUS: float = 80.0
HUM_MIN_PERCENT: float = 0.0
HUM_MAX_PERCENT: float = 100.0
TEMP_GRANO_MAX_CELSIUS: float = 85.0

# Umbral crítico: Temperaturas de grano superiores a 45°C dañan el embrión y degradan la taza
CRITICAL_GRAIN_OVERHEAT_THRESHOLD: float = 45.0

# ==============================================================================
# PARÁMETROS DEL MODELO DE MACHINE LEARNING
# ==============================================================================
FEATURE_COLUMNS: List[str] = ['Temp_Ambiente', 'Humedad_Ambiente', 'Temp_Grano']
TARGET_COLUMN: str = 'Tiempo_Restante_Horas'
RF_N_ESTIMATORS: int = 100
RF_MAX_DEPTH: int = 12
RF_RANDOM_STATE: int = 42

# Capacidad del búfer histórico en memoria de la UI
HISTORY_MAX_ROWS: int = 60

# ==============================================================================
# PARÁMETROS DE CONTROL TÉRMICO Y TOLERANCIAS ARDUINO (PROTOTIPO DEMO EN VIVO)
# ==============================================================================
# Calibrado -15°C respecto a la escala agroindustrial real (38°C -> 23°C)
# para permitir demostración práctica inmediata a temperatura ambiente de aula/laboratorio
DEFAULT_IDEAL_TEMP: float = 23.0
TOLERANCIA_IDEAL_TEMP: float = 1.0  # ±1.0°C: Verde, Fan OFF
UMBRAL_CERCA_TEMP: float = 3.5      # <= 3.5°C: Amarillo, Fan 60%
                                   # > 3.5°C: Rojo, Fan 100%

# ==============================================================================
# PERFILES CLIMÁTICOS DE REGIONES PRODUCTORAS DE PERÚ (CALIBRADOS PARA PROTOTIPO)
# ==============================================================================
PERU_REGIONS_DATA = {
    "San Martín (Moyobamba / Tarapoto)": {
        "departamento": "San Martín",
        "zona": "Selva Alta",
        "precipitacion_anual_mm": 2200,
        "riesgo_humedad": "Muy Alto (Peligro de moho/fermentación secundaria)",
        "humedad_tipica": 85.0,
        "temp_base_ideal": 25.5,  # Escala prototipo (-15°C de 40.5°C real)
        "descripcion": "Zona de precipitaciones intensas y saturación higrométrica. Consigna prototipo calibrada a 25.5°C (reducida 15°C para demo en vivo)."
    },
    "Junín (Chanchamayo / Satipo)": {
        "departamento": "Junín",
        "zona": "Selva Central",
        "precipitacion_anual_mm": 1850,
        "riesgo_humedad": "Alto (Lluvias frecuentes de tarde)",
        "humedad_tipica": 78.0,
        "temp_base_ideal": 24.0,  # Escala prototipo (-15°C de 39.0°C real)
        "descripcion": "Valle emblemático cafetalero de selva central. Consigna prototipo calibrada a 24.0°C para prueba en vivo."
    },
    "Cajamarca (Jaén / San Ignacio)": {
        "departamento": "Cajamarca",
        "zona": "Ceja de Selva / Valles Interandinos",
        "precipitacion_anual_mm": 1150,
        "riesgo_humedad": "Moderado / Bajo",
        "humedad_tipica": 65.0,
        "temp_base_ideal": 22.0,  # Escala prototipo (-15°C de 37.0°C real)
        "descripcion": "Mayor productor de cafés especiales del norte. Menor humedad relativa ambiental, consigna prototipo calibrada a 22.0°C."
    },
    "Cusco (Quillabamba / La Convención)": {
        "departamento": "Cusco",
        "zona": "Ceja de Selva Sur",
        "precipitacion_anual_mm": 1450,
        "riesgo_humedad": "Moderado-Alto",
        "humedad_tipica": 72.0,
        "temp_base_ideal": 23.0,  # Escala prototipo (-15°C de 38.0°C real)
        "descripcion": "Valles de alta pendiente con café y cacao chuncho. Consigna prototipo calibrada a 23.0°C."
    },
    "Amazonas (Rodríguez de Mendoza)": {
        "departamento": "Amazonas",
        "zona": "Bosque de Neblina",
        "precipitacion_anual_mm": 1700,
        "riesgo_humedad": "Alto (Neblina matutina y lloviznas)",
        "humedad_tipica": 80.0,
        "temp_base_ideal": 24.5,  # Escala prototipo (-15°C de 39.5°C real)
        "descripcion": "Alta humedad ambiental persistente. Consigna prototipo calibrada a 24.5°C."
    },
    "Piura (Huancabamba)": {
        "departamento": "Piura",
        "zona": "Sierra Norte",
        "precipitacion_anual_mm": 850,
        "riesgo_humedad": "Bajo (Clima templado seco)",
        "humedad_tipica": 58.0,
        "temp_base_ideal": 21.0,  # Escala prototipo (-15°C de 36.0°C real)
        "descripcion": "Cafés de altura en microclimas secos. Consigna prototipo calibrada a 21.0°C."
    },
    "Puno (Sandia / San Juan del Oro)": {
        "departamento": "Puno",
        "zona": "Ceja de Selva Puneña",
        "precipitacion_anual_mm": 1300,
        "riesgo_humedad": "Moderado",
        "humedad_tipica": 68.0,
        "temp_base_ideal": 22.5,  # Escala prototipo (-15°C de 37.5°C real)
        "descripcion": "Zona de cafés premiados mundialmente. Consigna prototipo calibrada a 22.5°C."
    }
}

