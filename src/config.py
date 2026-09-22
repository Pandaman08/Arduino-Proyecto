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
