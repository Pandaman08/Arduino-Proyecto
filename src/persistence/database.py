"""Acceso seguro y transaccional a SQLite."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from ..config import EXPERIMENTS_DB_PATH


class SQLiteDatabase:
    """Abre una conexión corta por operación y configura SQLite para concurrencia."""

    def __init__(self, path: Optional[Path] = None, busy_timeout_ms: int = 30_000):
        self.path = Path(path or EXPERIMENTS_DB_PATH)
        self.busy_timeout_ms = busy_timeout_ms
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=self.busy_timeout_ms / 1000,
            isolation_level=None,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(f"PRAGMA busy_timeout = {int(self.busy_timeout_ms)}")
        return connection

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Ejecuta una transacción de escritura con bloqueo inmediato y rollback seguro."""
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()
