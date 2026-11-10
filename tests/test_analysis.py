"""Pruebas de indicadores y estadística con datos sintéticos controlados."""

from src.analysis.indicators import calculate_experiment_indicators
from src.analysis.reports import dataframe_csv
from src.analysis.statistics import compare_experiments, statistical_tests


def experiment(**overrides):
    value = {
        "status": "finalizado", "completion_criterion": "humedad objetivo alcanzada",
        "started_at_utc": "2026-01-01T00:00:00Z", "ended_at_utc": "2026-01-01T02:00:00Z",
        "initial_weight_g": 100.0, "final_weight_g": 80.0, "thermal_reference_c": 30.0,
        "nominal_power_w": 100.0,
    }
    value.update(overrides)
    return value


def measurements():
    return [
        {"timestamp_utc": "2026-01-01T00:00:00Z", "grain_temperature_c": 30.0, "ambient_humidity_percent": 50.0, "fan_pwm": 255, "predicted_remaining_hours": 2.0},
        {"timestamp_utc": "2026-01-01T01:00:00Z", "grain_temperature_c": 31.0, "ambient_humidity_percent": 60.0, "fan_pwm": 255, "predicted_remaining_hours": 1.0},
        {"timestamp_utc": "2026-01-01T02:00:00Z", "grain_temperature_c": 29.0, "ambient_humidity_percent": 70.0, "fan_pwm": 0, "predicted_remaining_hours": 0.0},
    ]


def test_indicators_use_irregular_series_and_do_not_confuse_mass_with_moisture():
    result = calculate_experiment_indicators(experiment(), measurements())
    assert result["duration_hours"] == 2.0
    assert result["mass_loss_percent"] == 20.0
    assert result["thermal_mae_c"] == 0.5
    assert result["time_in_range_percent"] == 50.0
    assert result["ambient_humidity_mean_percent"] == 55.0
    assert result["grain_temperature_mean_c"] == 30.5
    assert result["energy_kwh"] == 0.2
    assert result["energy_is_estimated"] is True
    assert result["prediction_mae_hours"] == 0.0


def test_indicators_report_missing_completion_and_measurements():
    result = calculate_experiment_indicators(experiment(completion_criterion=None), [])
    assert result["duration_hours"] is None
    assert result["thermal_mae_c"] is None
    assert any("criterio" in item for item in result["missing_data"])


def test_paired_comparison_uses_pair_id_not_row_order():
    rows = [
        {"phase": "despues", "pair_id": "P2", "thermal_mae_c": 2.0},
        {"phase": "antes", "pair_id": "P1", "thermal_mae_c": 4.0},
        {"phase": "despues", "pair_id": "P1", "thermal_mae_c": 3.0},
        {"phase": "antes", "pair_id": "P2", "thermal_mae_c": 5.0},
    ]
    result = compare_experiments(rows, "thermal_mae_c", paired=True)
    assert result["before"]["n"] == 2
    assert result["after"]["n"] == 2
    assert result["difference"] == -2.0


def test_statistical_tests_expose_small_sample_limitation():
    result = statistical_tests([1.0], [0.5], paired=True)
    assert result["p_value"] is None
    assert "al menos dos" in result["limitation"]
    result = statistical_tests([1, 2, 4], [2, 4, 3], paired=True)
    assert result["test"] == "t pareada"
    assert result["shapiro"] is not None


def test_csv_export_is_reproducible_bytes():
    content = dataframe_csv([{"corrida": "R1", "valor": 2}])
    assert content.startswith("corrida,valor".encode())
    assert b"R1" in content
