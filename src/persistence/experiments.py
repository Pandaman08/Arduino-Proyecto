"""Gestión de ciclo de vida, consultas y eventos de corridas experimentales."""

import json
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

from .database import SQLiteDatabase
from .models import Event, Experiment, ExperimentPhase, ExperimentStatus, GrainType, MeasurementOrigin


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _row_to_experiment(row) -> Experiment:
    return Experiment(**dict(row))


class ExperimentManager:
    """Servicio de aplicación para crear y transicionar corridas."""

    def __init__(self, database: SQLiteDatabase):
        self.database = database

    def create_experiment(
        self,
        grain_type: str | GrainType,
        phase: str | ExperimentPhase,
        origin: str | MeasurementOrigin,
        thermal_reference_c: float,
        run_code: Optional[str] = None,
        batch_id: Optional[str] = None,
        pair_id: Optional[str] = None,
        initial_weight_g: Optional[float] = None,
        initial_moisture_percent: Optional[float] = None,
        actuator_config: Optional[dict[str, Any] | str] = None,
        nominal_power_w: Optional[float] = None,
        observations: Optional[str] = None,
        completion_criterion: Optional[str] = None,
    ) -> Experiment:
        """Crea una corrida preparada; fase y origen quedan registrados desde este momento."""
        grain_type = str(grain_type)
        phase = str(phase)
        origin = str(origin)
        if grain_type not in {item.value for item in GrainType}:
            raise ValueError("grain_type debe ser 'cafe' o 'cacao'")
        if phase not in {item.value for item in ExperimentPhase}:
            raise ValueError("phase debe ser 'antes' o 'despues'")
        if origin not in {item.value for item in MeasurementOrigin}:
            raise ValueError("origin debe ser 'real' o 'simulado'")
        if thermal_reference_c is None:
            raise ValueError("thermal_reference_c es obligatorio")

        now = utc_now()
        run_code = run_code or f"RUN-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{secrets.token_hex(3).upper()}"
        config_json = actuator_config if isinstance(actuator_config, str) else (
            json.dumps(actuator_config, ensure_ascii=False, sort_keys=True) if actuator_config is not None else None
        )
        with self.database.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO experimentos (
                    run_code, batch_id, pair_id, grain_type, phase, origin,
                    initial_weight_g, initial_moisture_percent, thermal_reference_c,
                    actuator_config_json, nominal_power_w, status, observations,
                    completion_criterion, created_at_utc, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_code, batch_id, pair_id, grain_type, phase, origin,
                    initial_weight_g, initial_moisture_percent, float(thermal_reference_c),
                    config_json, nominal_power_w, ExperimentStatus.PREPARADO.value,
                    observations, completion_criterion, now, now,
                ),
            )
            experiment_id = cursor.lastrowid
            self._insert_event(connection, Event(
                experiment_id=experiment_id,
                event_type="creada",
                description="Corrida experimental creada en estado preparado.",
                mode_to=ExperimentStatus.PREPARADO.value,
            ), now=now)
        return self.get_experiment(experiment_id)

    def get_experiment(self, experiment_id: int) -> Experiment:
        with self.database.connection() as connection:
            row = connection.execute("SELECT * FROM experimentos WHERE id = ?", (experiment_id,)).fetchone()
        if row is None:
            raise KeyError(f"No existe el experimento {experiment_id}")
        return _row_to_experiment(row)

    def get_by_run_code(self, run_code: str) -> Experiment:
        with self.database.connection() as connection:
            row = connection.execute("SELECT * FROM experimentos WHERE run_code = ?", (run_code,)).fetchone()
        if row is None:
            raise KeyError(f"No existe la corrida '{run_code}'")
        return _row_to_experiment(row)

    def list_experiments(
        self,
        grain_type: Optional[str] = None,
        phase: Optional[str] = None,
        origin: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list[Experiment]:
        clauses: list[str] = []
        parameters: list[Any] = []
        for column, value in (("grain_type", grain_type), ("phase", phase), ("origin", origin)):
            if value is not None:
                clauses.append(f"{column} = ?")
                parameters.append(str(value))
        if date_from is not None:
            clauses.append("created_at_utc >= ?")
            parameters.append(date_from)
        if date_to is not None:
            clauses.append("created_at_utc <= ?")
            parameters.append(date_to)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.database.connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM experimentos{where} ORDER BY created_at_utc DESC, id DESC", parameters
            ).fetchall()
        return [_row_to_experiment(row) for row in rows]

    def start(self, experiment_id: int) -> Experiment:
        return self._transition(experiment_id, ExperimentStatus.EJECUTANDO, {ExperimentStatus.PREPARADO}, "iniciada")

    def pause(self, experiment_id: int) -> Experiment:
        return self._transition(experiment_id, ExperimentStatus.PAUSADO, {ExperimentStatus.EJECUTANDO}, "pausada")

    def resume(self, experiment_id: int) -> Experiment:
        return self._transition(experiment_id, ExperimentStatus.EJECUTANDO, {ExperimentStatus.PAUSADO}, "reanudada")

    def finish(
        self,
        experiment_id: int,
        final_weight_g: Optional[float] = None,
        final_moisture_percent: Optional[float] = None,
        observations: Optional[str] = None,
    ) -> Experiment:
        return self._transition(
            experiment_id, ExperimentStatus.FINALIZADO, {ExperimentStatus.EJECUTANDO, ExperimentStatus.PAUSADO},
            "finalizada", final_weight_g=final_weight_g,
            final_moisture_percent=final_moisture_percent, observations=observations,
        )

    def interrupt(self, experiment_id: int, reason: str) -> Experiment:
        if not reason.strip():
            raise ValueError("Se requiere una razón para interrumpir la corrida")
        return self._transition(experiment_id, ExperimentStatus.INTERRUMPIDO, {
            ExperimentStatus.PREPARADO, ExperimentStatus.EJECUTANDO, ExperimentStatus.PAUSADO,
        }, "interrumpida", description=reason)

    def recover_interrupted_runs(self, reason: str = "La aplicación se reinició con la corrida activa.") -> int:
        """Marca como interrumpidas las corridas activas que quedaron de una ejecución previa."""
        active = self.list_experiments()
        recovered = 0
        for experiment in active:
            if experiment.status in {ExperimentStatus.EJECUTANDO.value, ExperimentStatus.PAUSADO.value}:
                self.interrupt(experiment.id, reason)
                recovered += 1
        return recovered

    def record_event(self, event: Event) -> int:
        with self.database.transaction() as connection:
            return self._insert_event(connection, event)

    def list_events(self, experiment_id: int) -> list[dict]:
        """Consulta la bitácora de eventos de una corrida en orden cronológico."""
        with self.database.connection() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM eventos WHERE experiment_id = ? ORDER BY timestamp_utc ASC, id ASC",
                    (experiment_id,),
                ).fetchall()
            ]

    def _transition(self, experiment_id: int, target: ExperimentStatus, allowed: set[ExperimentStatus], event_type: str, description: Optional[str] = None, **updates) -> Experiment:
        now = utc_now()
        with self.database.transaction() as connection:
            row = connection.execute("SELECT * FROM experimentos WHERE id = ?", (experiment_id,)).fetchone()
            if row is None:
                raise KeyError(f"No existe el experimento {experiment_id}")
            current = ExperimentStatus(row["status"])
            if current not in allowed:
                raise ValueError(f"Transición inválida: {current.value} -> {target.value}")
            fields = {"status": target.value, "updated_at_utc": now}
            if target == ExperimentStatus.EJECUTANDO and row["started_at_utc"] is None:
                fields["started_at_utc"] = now
            if target in {ExperimentStatus.FINALIZADO, ExperimentStatus.INTERRUMPIDO}:
                fields["ended_at_utc"] = now
            fields.update({key: value for key, value in updates.items() if value is not None})
            assignments = ", ".join(f"{key} = ?" for key in fields)
            connection.execute(f"UPDATE experimentos SET {assignments} WHERE id = ?", (*fields.values(), experiment_id))
            self._insert_event(connection, Event(
                experiment_id=experiment_id,
                event_type=event_type,
                description=description or f"Corrida {event_type}.",
                mode_from=current.value,
                mode_to=target.value,
            ), now=now)
        return self.get_experiment(experiment_id)

    @staticmethod
    def _insert_event(connection, event: Event, now: Optional[str] = None) -> int:
        cursor = connection.execute(
            """
            INSERT INTO eventos (experiment_id, timestamp_utc, event_type, description, mode_from, mode_to, details_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (event.experiment_id, event.timestamp_utc or now or utc_now(), event.event_type,
             event.description, event.mode_from, event.mode_to, event.details_json),
        )
        return int(cursor.lastrowid)
