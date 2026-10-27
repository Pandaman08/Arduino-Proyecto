"""Modelos y valores controlados del almacenamiento experimental."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Optional


class GrainType(StrEnum):
    CAFE = "cafe"
    CACAO = "cacao"


class ExperimentPhase(StrEnum):
    ANTES = "antes"
    DESPUES = "despues"


class MeasurementOrigin(StrEnum):
    REAL = "real"
    SIMULADO = "simulado"


class ExperimentStatus(StrEnum):
    PREPARADO = "preparado"
    EJECUTANDO = "ejecutando"
    PAUSADO = "pausado"
    FINALIZADO = "finalizado"
    INTERRUMPIDO = "interrumpido"


@dataclass(frozen=True)
class Experiment:
    id: int
    run_code: str
    grain_type: str
    phase: str
    origin: str
    status: str
    thermal_reference_c: float
    batch_id: Optional[str] = None
    pair_id: Optional[str] = None
    started_at_utc: Optional[str] = None
    ended_at_utc: Optional[str] = None
    initial_weight_g: Optional[float] = None
    final_weight_g: Optional[float] = None
    initial_moisture_percent: Optional[float] = None
    final_moisture_percent: Optional[float] = None
    actuator_config_json: Optional[str] = None
    nominal_power_w: Optional[float] = None
    observations: Optional[str] = None
    completion_criterion: Optional[str] = None
    created_at_utc: Optional[str] = None
    updated_at_utc: Optional[str] = None


@dataclass(frozen=True)
class Measurement:
    experiment_id: int
    timestamp_utc: str
    node_id: Optional[str] = None
    message_id: Optional[str] = None
    sequence_number: Optional[int] = None
    ambient_temperature_c: Optional[float] = None
    ambient_humidity_percent: Optional[float] = None
    grain_temperature_c: Optional[float] = None
    reference_temperature_c: Optional[float] = None
    setpoint_c: Optional[float] = None
    focus_state: Optional[str] = None
    fan_pwm: Optional[int] = None
    predicted_remaining_hours: Optional[float] = None
    origin: str = MeasurementOrigin.REAL
    quality: str = "valida"


@dataclass(frozen=True)
class Event:
    experiment_id: int
    event_type: str
    description: str
    timestamp_utc: Optional[str] = None
    mode_from: Optional[str] = None
    mode_to: Optional[str] = None
    details_json: Optional[str] = None
