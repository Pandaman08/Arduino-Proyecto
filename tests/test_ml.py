"""
Pruebas Unitarias para el Módulo de Machine Learning.
Valida entrenamiento, inferencia, consistencia y alertas agroindustriales.
"""

from pathlib import Path
import pytest
from src.ml.model_manager import (
    DryingPredictor,
    create_synthetic_dataset,
    load_or_train_predictor
)
from src.config import FEATURE_COLUMNS, TARGET_COLUMN


def test_create_synthetic_dataset(tmp_path: Path):
    """Verifica que la generación de dataset cree las columnas requeridas."""
    test_csv = tmp_path / "test_dataset.csv"
    df = create_synthetic_dataset(test_csv, n_samples=50)

    assert test_csv.exists()
    assert len(df) == 50
    for col in FEATURE_COLUMNS + [TARGET_COLUMN]:
        assert col in df.columns
    assert (df['Tiempo_Restante_Horas'] >= 0.0).all()


def test_predictor_train_and_inference(tmp_path: Path):
    """Valida el ciclo de vida completo: entrenamiento, persistencia e inferencia."""
    test_csv = tmp_path / "data.csv"
    test_model = tmp_path / "model.pkl"

    create_synthetic_dataset(test_csv, n_samples=100)

    predictor = DryingPredictor(model_path=test_model, dataset_path=test_csv)
    eval_info = predictor.train()

    assert test_model.exists()
    assert eval_info.is_newly_trained is True
    assert eval_info.r2_score is not None
    assert predictor.is_loaded() is True

    # Inferencia
    pred_horas = predictor.predict(temp_ambiente=28.5, humedad_ambiente=65.0, temp_grano=26.2)
    assert isinstance(pred_horas, float)
    assert pred_horas >= 0.0


def test_drying_stage_evaluation():
    """Valida las alertas agronómicas de sobrecalentamiento y las fases de secado."""
    # Alerta por sobrecalentamiento de grano (>45°C)
    msg, badge = DryingPredictor.get_drying_stage_info(remaining_hours=15.0, grain_temp=46.5)
    assert "ALERTA" in msg
    assert badge == "alert-danger"

    # Fase inicial (humedad alta, > 30 horas)
    msg, badge = DryingPredictor.get_drying_stage_info(remaining_hours=35.0, grain_temp=30.0)
    assert "Fase 1" in msg

    # Fase final (< 10 horas)
    msg, badge = DryingPredictor.get_drying_stage_info(remaining_hours=5.0, grain_temp=35.0)
    assert "Fase 3" in msg
    assert badge == "status-final"
