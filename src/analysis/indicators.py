"""Cálculo reproducible de indicadores experimentales sobre series SQLite."""

from dataclasses import asdict, dataclass
from datetime import datetime
import math
from typing import Any, Iterable, Mapping, Optional

import numpy as np


@dataclass(frozen=True)
class IndicatorResult:
    duration_hours: Optional[float] = None
    mass_loss_percent: Optional[float] = None
    thermal_mae_c: Optional[float] = None
    time_in_range_percent: Optional[float] = None
    ambient_humidity_mean_percent: Optional[float] = None
    grain_temperature_mean_c: Optional[float] = None
    energy_kwh: Optional[float] = None
    energy_is_estimated: bool = False
    prediction_mae_hours: Optional[float] = None
    prediction_rmse_hours: Optional[float] = None
    valid_measurements: int = 0
    missing_data: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _get(item: Any, key: str, default=None):
    return item.get(key, default) if isinstance(item, Mapping) else getattr(item, key, default)


def _number(value: Any) -> Optional[float]:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _timestamp(value: Any) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")) if value is not None else None
    except ValueError:
        return None


def _rows(measurements: Iterable[Any]) -> list[dict[str, Any]]:
    result = []
    for item in measurements:
        timestamp = _timestamp(_get(item, "timestamp_utc"))
        grain = _number(_get(item, "grain_temperature_c"))
        if timestamp is None or grain is None:
            continue
        result.append({
            "timestamp": timestamp, "grain_temperature_c": grain,
            "ambient_humidity_percent": _number(_get(item, "ambient_humidity_percent")),
            "fan_pwm": _number(_get(item, "fan_pwm")),
            "focus_state": _get(item, "focus_state"),
            "predicted_remaining_hours": _number(_get(item, "predicted_remaining_hours")),
        })
    return sorted(result, key=lambda row: row["timestamp"])


def _durations(rows: list[dict[str, Any]]) -> list[float]:
    return [max(0.0, (right["timestamp"] - left["timestamp"]).total_seconds()) for left, right in zip(rows, rows[1:])]


def _weighted_mean(values: list[Optional[float]], durations: list[float]) -> Optional[float]:
    pairs = [(value, duration) for value, duration in zip(values, durations) if value is not None and duration > 0]
    return float(sum(value * duration for value, duration in pairs) / sum(duration for _, duration in pairs)) if pairs else None


def _power_factor(row: dict[str, Any]) -> Optional[float]:
    pwm = row.get("fan_pwm")
    focus = str(row.get("focus_state") or "").lower()
    if pwm is None and not focus:
        return None
    fan_factor = (pwm / 255.0) if pwm is not None else 0.0
    heater_factor = 1.0 if focus in {"1", "on", "true", "encendido", "v"} else 0.0
    return max(fan_factor, heater_factor)


def calculate_experiment_indicators(experiment: Any, measurements: Iterable[Any], target_tolerance_c: float = 0.8) -> dict[str, Any]:
    """Calcula indicadores; los valores imposibles quedan como ``None``."""
    rows = _rows(measurements)
    missing: list[str] = []
    reference = _number(_get(experiment, "thermal_reference_c"))
    status = str(_get(experiment, "status", ""))
    criterion = _get(experiment, "completion_criterion")
    started, ended = _timestamp(_get(experiment, "started_at_utc")), _timestamp(_get(experiment, "ended_at_utc"))
    duration = (max(0.0, (ended - started).total_seconds()) / 3600.0) if status == "finalizado" and criterion and started and ended else None
    if duration is None:
        missing.append("duración: falta criterio de finalización o corrida finalizada")
    initial, final = _number(_get(experiment, "initial_weight_g")), _number(_get(experiment, "final_weight_g"))
    mass_loss = ((initial - final) / initial * 100.0) if initial and initial > 0 and final is not None else None
    if mass_loss is None:
        missing.append("pérdida de masa: faltan pesos inicial/final")

    durations = _durations(rows)
    thermal_mae = in_range = humidity_mean = grain_mean = None
    if rows and durations and reference is not None:
        errors = [abs(row["grain_temperature_c"] - reference) for row in rows[:-1]]
        total = sum(durations)
        thermal_mae = _weighted_mean(errors, durations)
        in_range = 100.0 * sum(dt for row, dt in zip(rows[:-1], durations) if abs(row["grain_temperature_c"] - reference) <= target_tolerance_c) / total
        humidity_mean = _weighted_mean([row["ambient_humidity_percent"] for row in rows[:-1]], durations)
        grain_mean = _weighted_mean([row["grain_temperature_c"] for row in rows[:-1]], durations)
    else:
        missing.append("indicadores térmicos: faltan dos lecturas válidas con timestamps")

    nominal_power = _number(_get(experiment, "nominal_power_w"))
    factors = [_power_factor(row) for row in rows[:-1]]
    energy = None
    if nominal_power is not None and nominal_power >= 0 and durations and any(factor is not None for factor in factors):
        energy = sum((factor or 0.0) * nominal_power * dt / 3600.0 for factor, dt in zip(factors, durations)) / 1000.0
    if energy is None:
        missing.append("energía: falta potencia nominal y estado medible de actuadores")

    errors = []
    if ended is not None:
        for row in rows:
            prediction = row["predicted_remaining_hours"]
            if prediction is not None:
                actual = max(0.0, (ended - row["timestamp"]).total_seconds() / 3600.0)
                errors.append(prediction - actual)
    prediction_mae = float(np.mean(np.abs(errors))) if errors else None
    prediction_rmse = float(np.sqrt(np.mean(np.square(errors)))) if errors else None
    if not errors:
        missing.append("error predictivo: faltan tiempos reales de finalización y predicciones")
    return IndicatorResult(
        duration_hours=duration, mass_loss_percent=mass_loss, thermal_mae_c=thermal_mae,
        time_in_range_percent=in_range, ambient_humidity_mean_percent=humidity_mean,
        grain_temperature_mean_c=grain_mean, energy_kwh=energy, energy_is_estimated=energy is not None,
        prediction_mae_hours=prediction_mae, prediction_rmse_hours=prediction_rmse,
        valid_measurements=len(rows), missing_data=tuple(dict.fromkeys(missing)),
    ).as_dict()
