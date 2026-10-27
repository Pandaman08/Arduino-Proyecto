"""Control no bloqueante del proceso externo Serial ↔ MQTT desde Streamlit."""

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


class BridgeProcessManager:
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.port: Optional[str] = None
        self.node_id: Optional[str] = None
        self.last_error: Optional[str] = None

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self, port: str, node_id: str, baudrate: int = 9600) -> bool:
        if self.running:
            return True
        self.last_error = None
        if not Path(port).exists():
            self.last_error = f"el puerto serial no existe: {port}"
            return False
        command = [
            sys.executable, "-m", "src.mqtt.bridge_cli",
            "--port", port, "--baudrate", str(baudrate), "--node-id", node_id,
        ]
        try:
            self.process = subprocess.Popen(
                command,
                cwd=Path(__file__).resolve().parents[2],
                env=os.environ.copy(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as error:
            self.process = None
            self.last_error = str(error)
            return False
        time.sleep(0.25)
        if self.process.poll() is not None:
            self.last_error = f"el proceso terminó al iniciar (código {self.process.returncode})"
            self.process = None
            return False
        self.port, self.node_id = port, node_id
        return True

    def stop(self) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None

    def status(self) -> str:
        if self.running:
            return f"activo · {self.node_id} · {self.port}"
        if self.last_error:
            return f"error: {self.last_error}"
        return "detenido"
