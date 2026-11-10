"""Bloqueo entre procesos para impedir que Streamlit y el puente compartan un puerto."""

from pathlib import Path
import hashlib
import os
import sys

from ..config import DATA_DIR


class SerialPortInUseError(RuntimeError):
    pass


class SerialPortLease:
    def __init__(self, port: str):
        safe_name = hashlib.sha256(port.encode("utf-8")).hexdigest()[:16]
        self.path = DATA_DIR / f".serial-{safe_name}.lock"
        self._handle = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a+")
        try:
            if os.name == "nt":
                import msvcrt
                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError) as error:
            self._handle.close()
            self._handle = None
            raise SerialPortInUseError(f"El puerto {self.path.name} ya está siendo usado por otro proceso") from error

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt
                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
            self._handle = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
