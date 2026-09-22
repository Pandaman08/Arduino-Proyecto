"""
Módulo de Machine Learning para Inferencia y Entrenamiento de Secado.
Implementa el algoritmo Random Forest Regressor con tipado y validación de métricas.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

from ..config import (
    DATASET_PATH,
    MODEL_PATH,
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    RF_N_ESTIMATORS,
    RF_MAX_DEPTH,
    RF_RANDOM_STATE,
    CRITICAL_GRAIN_OVERHEAT_THRESHOLD
)


@dataclass
class ModelEvaluation:
    """Métricas y metadatos del estado del modelo."""
    is_newly_trained: bool
    samples_count: int
    r2_score: Optional[float] = None
    mae_hours: Optional[float] = None


def create_synthetic_dataset(csv_path: Path, n_samples: int = 800) -> pd.DataFrame:
    """
    Genera un conjunto de datos sintético calibrado con cinética de secado
    de café y cacao cuando no existe un archivo previo.
    """
    np.random.seed(RF_RANDOM_STATE)
    temp_amb = np.random.uniform(20.0, 42.0, n_samples)
    hum_amb = np.random.uniform(35.0, 85.0, n_samples)
    temp_grano = np.clip(temp_amb + np.random.uniform(-2.0, 5.0, n_samples), 18.0, 48.0)

    # Cinética de transferencia de calor y masa:
    # Mayor temperatura y menor humedad atmosférica aceleran la deshidratación
    factor_secado = (temp_grano * 0.45 + temp_amb * 0.35) / (hum_amb * 0.5)
    tiempo_restante = np.clip(
        60.0 - (factor_secado * 25.0) + np.random.normal(0, 2.0, n_samples),
        0.5,
        48.0
    )

    df = pd.DataFrame({
        'Temp_Ambiente': np.round(temp_amb, 1),
        'Humedad_Ambiente': np.round(hum_amb, 1),
        'Temp_Grano': np.round(temp_grano, 1),
        'Tiempo_Restante_Horas': np.round(tiempo_restante, 1)
    })

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)
    return df


class DryingPredictor:
    """Clase principal para entrenamiento, serialización e inferencia de secado con Random Forest."""

    def __init__(self, model_path: Path = MODEL_PATH, dataset_path: Path = DATASET_PATH):
        self.model_path: Path = model_path
        self.dataset_path: Path = dataset_path
        self.model: Optional[RandomForestRegressor] = None

    def is_loaded(self) -> bool:
        """Indica si el modelo ya está cargado en memoria."""
        return self.model is not None

    def load(self) -> None:
        """Carga el modelo pre-entrenado desde el archivo .pkl."""
        if not self.model_path.exists():
            raise FileNotFoundError(f"No se encontró el archivo del modelo en '{self.model_path}'.")
        self.model = joblib.load(self.model_path)

    def train(self) -> ModelEvaluation:
        """
        Entrena un nuevo modelo Random Forest a partir del dataset local y lo persiste en disco.
        """
        if not self.dataset_path.exists():
            create_synthetic_dataset(self.dataset_path)

        df = pd.read_csv(self.dataset_path)

        # Validación estricta de estructura tabular
        required_cols = FEATURE_COLUMNS + [TARGET_COLUMN]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Faltan columnas obligatorias en el dataset: {missing}")

        X = df[FEATURE_COLUMNS]
        y = df[TARGET_COLUMN]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=RF_RANDOM_STATE
        )

        modelo = RandomForestRegressor(
            n_estimators=RF_N_ESTIMATORS,
            max_depth=RF_MAX_DEPTH,
            random_state=RF_RANDOM_STATE,
            n_jobs=1  # Compatibilidad total y determinismo
        )
        modelo.fit(X_train, y_train)

        y_pred = modelo.predict(X_test)
        r2 = float(r2_score(y_test, y_pred))
        mae = float(mean_absolute_error(y_test, y_pred))

        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(modelo, self.model_path)
        self.model = modelo

        return ModelEvaluation(
            is_newly_trained=True,
            samples_count=len(df),
            r2_score=r2,
            mae_hours=mae
        )

    def predict(self, temp_ambiente: float, humedad_ambiente: float, temp_grano: float) -> float:
        """
        Realiza la predicción del tiempo restante en horas a partir de las 3 variables de sensores.
        """
        if self.model is None:
            raise RuntimeError("El modelo predictivo no ha sido cargado ni entrenado.")

        input_data = pd.DataFrame([{
            'Temp_Ambiente': temp_ambiente,
            'Humedad_Ambiente': humedad_ambiente,
            'Temp_Grano': temp_grano
        }])

        prediccion = float(self.model.predict(input_data)[0])
        return max(0.0, prediccion)

    @staticmethod
    def get_drying_stage_info(remaining_hours: float, grain_temp: float) -> Tuple[str, str]:
        """
        Determina la fase operativa de secado y evalúa alertas agroindustriales.
        
        Returns:
            Tuple[estado, tipo_badge]
        """
        if grain_temp > CRITICAL_GRAIN_OVERHEAT_THRESHOLD:
            return ("⚠️ ALERTA: Grano Sobrecalentado (>45°C)", "alert-danger")
        if remaining_hours > 30.0:
            return ("Fase 1: Alto Contenido de Humedad", "status-normal")
        if remaining_hours > 10.0:
            return ("Fase 2: Deshidratación Activa", "status-normal")
        return ("Fase 3: Etapa Final de Secado", "status-final")


def load_or_train_predictor(
    model_path: Path = MODEL_PATH,
    dataset_path: Path = DATASET_PATH
) -> Tuple[DryingPredictor, ModelEvaluation]:
    """Función de alto nivel para inicializar o entrenar el predictor en el Gateway."""
    predictor = DryingPredictor(model_path=model_path, dataset_path=dataset_path)

    if model_path.exists():
        try:
            predictor.load()
            return predictor, ModelEvaluation(is_newly_trained=False, samples_count=0)
        except Exception:
            # Si el archivo está corrupto o es de otra versión, reentrenar
            pass

    eval_info = predictor.train()
    return predictor, eval_info
