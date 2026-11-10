"""Consultas de lectura para historial y comparación en la interfaz."""

from typing import Optional

from .database import SQLiteDatabase


class HistoryRepository:
    def __init__(self, database: SQLiteDatabase):
        self.database = database

    def measurements(
        self,
        experiment_id: Optional[int] = None,
        grain_type: Optional[str] = None,
        phase: Optional[str] = None,
        origin: Optional[str] = None,
        node_id: Optional[str] = None,
        batch_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list[dict]:
        clauses, params = [], []
        for column, value in (
            ("m.experiment_id", experiment_id), ("e.grain_type", grain_type),
            ("e.phase", phase), ("m.origin", origin), ("m.node_id", node_id),
            ("e.batch_id", batch_id),
        ):
            if value not in (None, "", "Todos"):
                clauses.append(f"{column} = ?")
                params.append(value)
        if date_from:
            clauses.append("m.timestamp_utc >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("m.timestamp_utc < ?")
            params.append(date_to + "T23:59:59Z")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"""
            SELECT m.*, e.run_code, e.grain_type, e.phase, e.batch_id,
                   e.origin AS experiment_origin
            FROM mediciones m JOIN experimentos e ON e.id = m.experiment_id
            {where} ORDER BY m.timestamp_utc ASC, m.id ASC
        """
        with self.database.connection() as connection:
            return [dict(row) for row in connection.execute(query, params).fetchall()]

    def devices(self) -> list[str]:
        with self.database.connection() as connection:
            rows = connection.execute(
                "SELECT DISTINCT node_id FROM mediciones WHERE node_id IS NOT NULL ORDER BY node_id"
            ).fetchall()
        return [row[0] for row in rows]

    def experiment_summary(self, experiment_ids: list[int]) -> list[dict]:
        if not experiment_ids:
            return []
        marks = ",".join("?" for _ in experiment_ids)
        with self.database.connection() as connection:
            rows = connection.execute(f"""
                SELECT e.*, COUNT(m.id) AS measurement_count,
                       MIN(m.timestamp_utc) AS first_measurement,
                       MAX(m.timestamp_utc) AS last_measurement
                FROM experimentos e LEFT JOIN mediciones m ON m.experiment_id = e.id
                WHERE e.id IN ({marks}) GROUP BY e.id ORDER BY e.id
            """, experiment_ids).fetchall()
        return [dict(row) for row in rows]
