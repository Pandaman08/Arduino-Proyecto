"""Configuración MQTT cargada desde variables de entorno o un archivo .env local."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import os


def load_dotenv(path: Optional[Path] = None) -> None:
    """Carga pares simples KEY=VALUE sin sobrescribir el entorno existente."""
    dotenv_path = Path(path or ".env")
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "si", "sí"}


@dataclass(frozen=True)
class MqttSettings:
    host: str = "cafes.duckdns.org"
    port: int = 443
    transport: str = "websockets"
    ws_path: str = "/mqtt"
    use_tls: bool = True
    username: str = ""
    password: str = ""
    keepalive: int = 60
    client_id_prefix: str = "arduino-proyecto"

    @classmethod
    def from_env(cls, dotenv_path: Optional[Path] = None) -> "MqttSettings":
        load_dotenv(dotenv_path)
        return cls(
            host=os.getenv("MQTT_HOST", cls.host),
            port=int(os.getenv("MQTT_PORT", str(cls.port))),
            transport=os.getenv("MQTT_TRANSPORT", cls.transport),
            ws_path=os.getenv("MQTT_WS_PATH", cls.ws_path),
            use_tls=_bool_env("MQTT_USE_TLS", cls.use_tls),
            username=os.getenv("MQTT_USERNAME", ""),
            password=os.getenv("MQTT_PASSWORD", ""),
            keepalive=int(os.getenv("MQTT_KEEPALIVE", str(cls.keepalive))),
            client_id_prefix=os.getenv("MQTT_CLIENT_ID_PREFIX", cls.client_id_prefix),
        )

    @property
    def credentials_configured(self) -> bool:
        return bool(self.username and self.password)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.host.strip():
            errors.append("MQTT_HOST está vacío")
        if not 1 <= self.port <= 65535:
            errors.append("MQTT_PORT debe estar entre 1 y 65535")
        if self.transport not in {"tcp", "websockets"}:
            errors.append("MQTT_TRANSPORT debe ser 'tcp' o 'websockets'")
        if self.transport == "websockets" and not self.ws_path.startswith("/"):
            errors.append("MQTT_WS_PATH debe comenzar con '/'")
        if self.keepalive <= 0:
            errors.append("MQTT_KEEPALIVE debe ser positivo")
        return errors
