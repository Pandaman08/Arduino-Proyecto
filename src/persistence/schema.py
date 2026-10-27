"""Esquema SQLite versionado de forma aditiva."""

import sqlite3

from .database import SQLiteDatabase


SCHEMA_VERSION = 1


def initialize_schema(database: SQLiteDatabase) -> None:
    """Crea tablas e índices faltantes sin eliminar datos existentes."""
    with database.transaction() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS experimentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_code TEXT NOT NULL UNIQUE,
                batch_id TEXT,
                pair_id TEXT,
                grain_type TEXT NOT NULL CHECK (grain_type IN ('cafe', 'cacao')),
                phase TEXT NOT NULL CHECK (phase IN ('antes', 'despues')),
                origin TEXT NOT NULL CHECK (origin IN ('real', 'simulado')),
                started_at_utc TEXT,
                ended_at_utc TEXT,
                initial_weight_g REAL,
                final_weight_g REAL,
                initial_moisture_percent REAL,
                final_moisture_percent REAL,
                thermal_reference_c REAL NOT NULL,
                actuator_config_json TEXT,
                nominal_power_w REAL,
                status TEXT NOT NULL CHECK (status IN ('preparado', 'ejecutando', 'pausado', 'finalizado', 'interrumpido')),
                observations TEXT,
                completion_criterion TEXT,
                created_at_utc TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS mediciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER NOT NULL REFERENCES experimentos(id) ON DELETE CASCADE,
                timestamp_utc TEXT NOT NULL,
                node_id TEXT,
                message_id TEXT,
                sequence_number INTEGER,
                ambient_temperature_c REAL,
                ambient_humidity_percent REAL,
                grain_temperature_c REAL,
                reference_temperature_c REAL,
                setpoint_c REAL,
                focus_state TEXT,
                fan_pwm INTEGER,
                predicted_remaining_hours REAL,
                origin TEXT NOT NULL CHECK (origin IN ('real', 'simulado')),
                quality TEXT NOT NULL,
                dedup_key TEXT NOT NULL,
                UNIQUE (experiment_id, dedup_key)
            );

            CREATE TABLE IF NOT EXISTS eventos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER NOT NULL REFERENCES experimentos(id) ON DELETE CASCADE,
                timestamp_utc TEXT NOT NULL,
                event_type TEXT NOT NULL,
                description TEXT NOT NULL,
                mode_from TEXT,
                mode_to TEXT,
                details_json TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_experimentos_grain_phase_date
                ON experimentos (grain_type, phase, created_at_utc);
            CREATE INDEX IF NOT EXISTS idx_experimentos_status
                ON experimentos (status);
            CREATE INDEX IF NOT EXISTS idx_mediciones_experiment_timestamp
                ON mediciones (experiment_id, timestamp_utc);
            CREATE INDEX IF NOT EXISTS idx_eventos_experiment_timestamp
                ON eventos (experiment_id, timestamp_utc);

            CREATE TRIGGER IF NOT EXISTS prevent_started_phase_change
            BEFORE UPDATE OF phase ON experimentos
            WHEN OLD.started_at_utc IS NOT NULL OR OLD.status <> 'preparado'
            BEGIN
                SELECT RAISE(ABORT, 'La fase no puede modificarse después del inicio');
            END;

            CREATE TRIGGER IF NOT EXISTS prevent_experiment_origin_change
            BEFORE UPDATE OF origin ON experimentos
            WHEN OLD.origin <> NEW.origin
            BEGIN
                SELECT RAISE(ABORT, 'El origen del experimento es inmutable');
            END;
            """
        )
        connection.execute(
            "INSERT INTO schema_metadata(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            ("schema_version", str(SCHEMA_VERSION)),
        )
