"""Registro idempotente de mediciones y consultas de telemetría."""

from typing import Optional

from .database import SQLiteDatabase
from .experiments import utc_now
from .models import Measurement


class MeasurementRepository:
    """Persiste mediciones separando estrictamente el origen real del simulado."""

    def __init__(self, database: SQLiteDatabase):
        self.database = database

    def record(self, measurement: Measurement) -> bool:
        """Registra una medición; retorna False si su clave ya existía."""
        if measurement.origin not in {"real", "simulado"}:
            raise ValueError("origin debe ser 'real' o 'simulado'")
        dedup_key = self._dedup_key(measurement)
        with self.database.transaction() as connection:
            experiment = connection.execute(
                "SELECT origin FROM experimentos WHERE id = ?", (measurement.experiment_id,)
            ).fetchone()
            if experiment is None:
                raise KeyError(f"No existe el experimento {measurement.experiment_id}")
            if experiment["origin"] != measurement.origin:
                raise ValueError("El origen de la medición no coincide con el origen del experimento")
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO mediciones (
                    experiment_id, timestamp_utc, node_id, message_id, sequence_number,
                    ambient_temperature_c, ambient_humidity_percent, grain_temperature_c,
                    reference_temperature_c, setpoint_c, focus_state, fan_pwm,
                    predicted_remaining_hours, origin, quality, dedup_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (measurement.experiment_id, measurement.timestamp_utc, measurement.node_id,
                 measurement.message_id, measurement.sequence_number,
                 measurement.ambient_temperature_c, measurement.ambient_humidity_percent,
                 measurement.grain_temperature_c, measurement.reference_temperature_c,
                 measurement.setpoint_c, measurement.focus_state, measurement.fan_pwm,
                 measurement.predicted_remaining_hours, measurement.origin, measurement.quality, dedup_key),
            )
            return cursor.rowcount == 1

    def list_for_experiment(self, experiment_id: int, quality: Optional[str] = None) -> list[dict]:
        query = "SELECT * FROM mediciones WHERE experiment_id = ?"
        parameters: list = [experiment_id]
        if quality is not None:
            query += " AND quality = ?"
            parameters.append(quality)
        query += " ORDER BY timestamp_utc ASC, id ASC"
        with self.database.connection() as connection:
            return [dict(row) for row in connection.execute(query, parameters).fetchall()]

    def count_for_experiment(self, experiment_id: int) -> int:
        with self.database.connection() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM mediciones WHERE experiment_id = ?", (experiment_id,)).fetchone()
        return int(row["count"])

    @staticmethod
    def _dedup_key(measurement: Measurement) -> str:
        if measurement.message_id:
            return f"message:{measurement.node_id or ''}:{measurement.message_id}"
        if measurement.sequence_number is not None:
            return f"sequence:{measurement.node_id or ''}:{measurement.sequence_number}"
        if not measurement.timestamp_utc:
            raise ValueError("timestamp_utc es obligatorio cuando no hay message_id ni sequence_number")
        return f"timestamp:{measurement.node_id or ''}:{measurement.timestamp_utc}"
