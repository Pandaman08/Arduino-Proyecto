"""Persistencia local de experimentos, mediciones y eventos."""

from .database import SQLiteDatabase
from .experiments import ExperimentManager
from .measurements import MeasurementRepository
from .history import HistoryRepository
from .models import (
    Experiment,
    Event,
    ExperimentPhase,
    ExperimentStatus,
    GrainType,
    Measurement,
    MeasurementOrigin,
)
from .schema import initialize_schema


def initialize_database(path=None, recover_interrupted=True):
    """Inicializa el esquema y opcionalmente recupera corridas activas."""
    database = SQLiteDatabase(path)
    initialize_schema(database)
    if recover_interrupted:
        ExperimentManager(database).recover_interrupted_runs()
    return database


__all__ = [
    "SQLiteDatabase",
    "ExperimentManager",
    "MeasurementRepository",
    "HistoryRepository",
    "Experiment",
    "Event",
    "Measurement",
    "ExperimentPhase",
    "ExperimentStatus",
    "GrainType",
    "MeasurementOrigin",
    "initialize_database",
    "initialize_schema",
]
