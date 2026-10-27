"""Pruebas del almacenamiento experimental local."""

import sqlite3

import pytest

from src.persistence import (
    ExperimentManager,
    ExperimentPhase,
    ExperimentStatus,
    GrainType,
    Measurement,
    MeasurementOrigin,
    MeasurementRepository,
    SQLiteDatabase,
    initialize_schema,
)


def make_database(tmp_path):
    database = SQLiteDatabase(tmp_path / "experimentos.db")
    initialize_schema(database)
    return database


def make_experiment(manager, **overrides):
    values = {
        "grain_type": GrainType.CAFE,
        "phase": ExperimentPhase.ANTES,
        "origin": MeasurementOrigin.SIMULADO,
        "thermal_reference_c": 23.0,
        "batch_id": "LOTE-01",
        "pair_id": "PAR-01",
        "actuator_config": {"control_automatico": False, "ventilador_pwm": 0},
    }
    values.update(overrides)
    return manager.create_experiment(**values)


def test_schema_is_created_and_existing_data_survives(tmp_path):
    database = make_database(tmp_path)
    manager = ExperimentManager(database)
    experiment = make_experiment(manager)

    initialize_schema(database)

    with database.connection() as connection:
        tables = {row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert {"experimentos", "mediciones", "eventos"}.issubset(tables)
        assert connection.execute("SELECT COUNT(*) FROM experimentos").fetchone()[0] == 1
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert experiment.status == ExperimentStatus.PREPARADO


def test_experiment_state_transitions_and_invalid_transitions(tmp_path):
    manager = ExperimentManager(make_database(tmp_path))
    experiment = make_experiment(manager)

    with pytest.raises(ValueError, match="Transición inválida"):
        manager.pause(experiment.id)
    started = manager.start(experiment.id)
    assert started.status == ExperimentStatus.EJECUTANDO
    assert started.started_at_utc is not None
    paused = manager.pause(experiment.id)
    resumed = manager.resume(paused.id)
    finished = manager.finish(resumed.id, final_weight_g=810.0, final_moisture_percent=11.5)

    assert paused.status == ExperimentStatus.PAUSADO
    assert resumed.status == ExperimentStatus.EJECUTANDO
    assert finished.status == ExperimentStatus.FINALIZADO
    assert finished.ended_at_utc is not None
    assert finished.final_weight_g == 810.0
    with pytest.raises(ValueError, match="Transición inválida"):
        manager.resume(finished.id)

    with manager.database.connection() as connection:
        events = connection.execute("SELECT event_type, mode_from, mode_to FROM eventos ORDER BY id").fetchall()
    assert [event["event_type"] for event in events] == ["creada", "iniciada", "pausada", "reanudada", "finalizada"]


def test_phase_and_origin_are_fixed_and_real_simulated_data_are_separated(tmp_path):
    database = make_database(tmp_path)
    manager = ExperimentManager(database)
    measurements = MeasurementRepository(database)
    real = make_experiment(manager, grain_type=GrainType.CACAO, phase=ExperimentPhase.DESPUES, origin=MeasurementOrigin.REAL)
    simulated = make_experiment(manager, origin=MeasurementOrigin.SIMULADO)

    assert real.phase == ExperimentPhase.DESPUES
    with pytest.raises(ValueError):
        measurements.record(Measurement(
            experiment_id=real.id, timestamp_utc="2026-01-01T00:00:00Z", sequence_number=1,
            origin=MeasurementOrigin.SIMULADO,
        ))
    assert measurements.record(Measurement(
        experiment_id=real.id, timestamp_utc="2026-01-01T00:00:00Z", sequence_number=1,
        origin=MeasurementOrigin.REAL, quality="valida",
    ))
    assert measurements.record(Measurement(
        experiment_id=simulated.id, timestamp_utc="2026-01-01T00:00:00Z", sequence_number=1,
        origin=MeasurementOrigin.SIMULADO, quality="valida",
    ))
    assert measurements.count_for_experiment(real.id) == 1
    assert measurements.count_for_experiment(simulated.id) == 1

    manager.start(simulated.id)
    with database.connection() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="fase"):
            connection.execute("UPDATE experimentos SET phase = 'despues' WHERE id = ?", (simulated.id,))


def test_measurements_are_idempotent_by_message_or_sequence(tmp_path):
    database = make_database(tmp_path)
    manager = ExperimentManager(database)
    repository = MeasurementRepository(database)
    experiment = make_experiment(manager)

    measurement = Measurement(
        experiment_id=experiment.id, timestamp_utc="2026-01-01T00:00:00Z", node_id="nano-01",
        sequence_number=7, ambient_temperature_c=28.5, ambient_humidity_percent=65.0,
        grain_temperature_c=26.2, setpoint_c=23.0, predicted_remaining_hours=12.3,
        origin=MeasurementOrigin.SIMULADO,
    )
    assert repository.record(measurement) is True
    assert repository.record(measurement) is False
    assert repository.count_for_experiment(experiment.id) == 1
    assert repository.record(Measurement(
        experiment_id=experiment.id, timestamp_utc="2026-01-01T00:00:01Z", node_id="nano-01",
        message_id="msg-1", origin=MeasurementOrigin.SIMULADO,
    )) is True
    assert repository.record(Measurement(
        experiment_id=experiment.id, timestamp_utc="2026-01-01T00:00:02Z", node_id="nano-01",
        message_id="msg-1", origin=MeasurementOrigin.SIMULADO,
    )) is False
    assert repository.count_for_experiment(experiment.id) == 2


def test_queries_by_grain_phase_origin_and_date(tmp_path):
    manager = ExperimentManager(make_database(tmp_path))
    make_experiment(manager, run_code="OLD", grain_type=GrainType.CAFE, phase=ExperimentPhase.ANTES)
    make_experiment(manager, run_code="NEW", grain_type=GrainType.CACAO, phase=ExperimentPhase.DESPUES, origin=MeasurementOrigin.REAL)

    all_experiments = manager.list_experiments()
    assert {experiment.run_code for experiment in all_experiments} == {"OLD", "NEW"}
    assert [experiment.run_code for experiment in manager.list_experiments(grain_type="cacao")] == ["NEW"]
    assert [experiment.run_code for experiment in manager.list_experiments(phase="antes")] == ["OLD"]
    assert [experiment.run_code for experiment in manager.list_experiments(origin="real")] == ["NEW"]
    assert len(manager.list_experiments(date_from="1900-01-01T00:00:00Z", date_to="2999-01-01T00:00:00Z")) == 2


def test_recovery_marks_active_runs_interrupted_and_keeps_measurements(tmp_path):
    database = make_database(tmp_path)
    manager = ExperimentManager(database)
    repository = MeasurementRepository(database)
    experiment = make_experiment(manager)
    manager.start(experiment.id)
    repository.record(Measurement(
        experiment_id=experiment.id, timestamp_utc="2026-01-01T00:00:00Z", sequence_number=1,
        origin=MeasurementOrigin.SIMULADO,
    ))

    recovered = ExperimentManager(database).recover_interrupted_runs("Prueba de recuperación")
    assert recovered == 1
    assert manager.get_experiment(experiment.id).status == ExperimentStatus.INTERRUMPIDO
    assert repository.count_for_experiment(experiment.id) == 1
    assert manager.list_experiments()[0].ended_at_utc is not None
