"""Adaptador opcional no bloqueante para mostrar estado MQTT en Streamlit."""

from collections import deque
from threading import Lock
from time import monotonic
import re
import socket
import ssl
import os
import json
from typing import Optional

from .client import MqttClient, MqttConnectionError
from .config import MqttSettings, load_dotenv
from .messages import parse_telemetry_payload
from .topics import MqttTopics


class StreamlitMqttSubscriber:
    def __init__(self, client: MqttClient, max_messages: int = 100):
        self.client = client
        self.messages = deque(maxlen=max_messages)
        self._lock = Lock()

    def start(self, topic_filter: Optional[str] = None) -> None:
        topic_filter = topic_filter or MqttTopics("nodo1").telemetry_subscription
        self.client.subscribe(topic_filter, self._on_message, qos=1)
        self.client.subscribe("secado/+/ack", self._on_message, qos=1)
        self.client.subscribe("secado/+/estado", self._on_message, qos=1)
        self.client.start()

    def poll(self) -> list[dict]:
        with self._lock:
            values = list(self.messages)
            self.messages.clear()
        return values

    def stop(self):
        self.client.stop()

    @property
    def is_connected(self) -> bool:
        return self.client.is_connected

    @property
    def last_error(self) -> Optional[str]:
        return self.client.status.last_error

    def publish_command(self, node_id: str, command: str, request_id: Optional[str] = None) -> None:
        """Publica un comando; el éxito visual solo se confirma al recibir ACK."""
        payload = {"command": command}
        if request_id:
            payload["request_id"] = request_id
        self.client.publish(
            MqttTopics(node_id).command,
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            qos=1,
        )

    def _on_message(self, topic: str, payload: bytes, qos: int, retain: bool):
        try:
            if topic.endswith("/telemetria"):
                message = parse_telemetry_payload(payload).to_dict()
            else:
                message = json.loads(payload.decode("utf-8"))
                if not isinstance(message, dict):
                    return
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            return
        message["_topic"] = topic
        message["_retained"] = retain
        with self._lock:
            self.messages.append(message)


def connection_error_message(error: Exception) -> str:
    """Explica la causa conocida sin mostrar excepciones que puedan contener secretos."""
    root = error
    while root.__cause__ is not None:
        root = root.__cause__
    if isinstance(root, ImportError):
        return ("Falta una dependencia MQTT en el Python que ejecuta Streamlit (paho-mqtt). "
                "Inicia con .venv/bin/python -m streamlit run app.py.")
    if isinstance(root, socket.gaierror):
        return "Error MQTT de DNS: este proceso no puede resolver el nombre del broker."
    if isinstance(root, ssl.SSLCertVerificationError):
        return "Error MQTT de certificado TLS: revisa la cadena de confianza y la fecha del equipo."
    if isinstance(root, ssl.SSLError):
        return "Error MQTT durante la negociación TLS con el broker."
    if isinstance(root, TimeoutError):
        return "Tiempo agotado al conectar con MQTT: revisa acceso de red y puerto del broker."
    if isinstance(root, ConnectionRefusedError):
        return "El servidor rechazó la conexión de red al puerto MQTT configurado."
    if isinstance(root, PermissionError):
        return "Este proceso no tiene permisos para acceder a la red o configuración MQTT."
    if isinstance(root, ValueError):
        return "Configuración MQTT inválida: revisa puerto, transporte, ruta y keepalive en .env."
    code = re.search(r"código=(\d+)", str(error))
    if code and code.group(1) in {"4", "5"}:
        return "EMQX rechazó la autenticación o autorización de esta cuenta MQTT."
    return f"Error de conexión MQTT ({type(error).__name__}): revisa red, TLS y credenciales."


def create_optional_streamlit_subscriber() -> tuple[Optional[StreamlitMqttSubscriber], str]:
    """Solo conecta si MQTT_STREAMLIT_ENABLED=true; por defecto no toca el broker."""
    # El indicador debe poder configurarse en el .env local antes de consultar
    # os.environ; MqttSettings.from_env() lo carga después, demasiado tarde.
    load_dotenv()
    if os.getenv("MQTT_STREAMLIT_ENABLED", "false").lower() not in {"1", "true", "yes", "on"}:
        return None, "deshabilitado (MQTT_STREAMLIT_ENABLED no está activo)"
    settings = MqttSettings.from_env()
    subscriber = StreamlitMqttSubscriber(MqttClient(settings))
    try:
        subscriber.start()
    except (MqttConnectionError, OSError, ValueError) as error:
        subscriber.stop()
        return None, connection_error_message(error)
    return subscriber, "conectado"


class StreamlitMqttConnection:
    """Recurso cacheable que puede recuperarse de un primer intento fallido."""

    def __init__(self, factory=None, clock=monotonic, retry_interval: float = 5.0):
        self._factory = factory or create_optional_streamlit_subscriber
        self._clock = clock
        self._retry_interval = retry_interval
        self._next_attempt = 0.0
        self._lock = Lock()
        self.subscriber = None
        self.message = "Pendiente de conexión"

    def get(self, *, force: bool = False):
        with self._lock:
            if force:
                # Acción explícita del usuario: releer la configuración local.
                load_dotenv(override=True)
            elif self.subscriber is not None and self.subscriber.is_connected:
                return self.subscriber, "Conectado"
            elif self._clock() < self._next_attempt:
                message = self.message if self.subscriber is None else "MQTT desconectado; esperando reintento."
                return self.subscriber, message
            if self.subscriber is not None:
                self.subscriber.stop()
                self.subscriber = None
            self.subscriber, self.message = self._factory()
            self._next_attempt = self._clock() + self._retry_interval
            return self.subscriber, self.message
