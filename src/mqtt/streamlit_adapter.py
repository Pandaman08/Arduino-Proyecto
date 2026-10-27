"""Adaptador opcional no bloqueante para mostrar estado MQTT en Streamlit."""

from collections import deque
from threading import Lock
import os
import json
from typing import Optional

from .client import MqttClient, MqttConnectionError
from .config import MqttSettings
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
        with self._lock:
            self.messages.append(message)


def create_optional_streamlit_subscriber() -> tuple[Optional[StreamlitMqttSubscriber], str]:
    """Solo conecta si MQTT_STREAMLIT_ENABLED=true; por defecto no toca el broker."""
    if os.getenv("MQTT_STREAMLIT_ENABLED", "false").lower() not in {"1", "true", "yes", "on"}:
        return None, "deshabilitado (MQTT_STREAMLIT_ENABLED no está activo)"
    settings = MqttSettings.from_env()
    subscriber = StreamlitMqttSubscriber(MqttClient(settings))
    try:
        subscriber.start()
    except MqttConnectionError as error:
        return None, f"error: {error}"
    return subscriber, "conectado"
