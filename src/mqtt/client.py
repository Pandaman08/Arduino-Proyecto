"""Cliente MQTT paho para EMQX sobre TCP o WebSockets seguros."""

from dataclasses import dataclass
import logging
import ssl
from threading import Event, Lock
from time import monotonic
from typing import Callable, Optional
from uuid import uuid4

from .config import MqttSettings

logger = logging.getLogger(__name__)
MessageCallback = Callable[[str, bytes, int, bool], None]


class MqttConnectionError(RuntimeError):
    """La conexión MQTT no pudo establecerse o se perdió."""


class MqttNotConnectedError(MqttConnectionError):
    """Se intentó publicar o suscribir sin conexión verificada."""


@dataclass(frozen=True)
class MqttStatus:
    connected: bool
    client_id: str
    last_error: Optional[str] = None
    broker: str = ""


class MqttClient:
    """Adaptador pequeño y testeable alrededor de paho-mqtt."""

    def __init__(
        self,
        settings: MqttSettings,
        client_id: Optional[str] = None,
        client_factory=None,
    ):
        self.settings = settings
        self.client_id = client_id or f"{settings.client_id_prefix}-{uuid4().hex[:12]}"
        self._client_factory = client_factory
        self._client = None
        self._connected = Event()
        self._lock = Lock()
        self._subscriptions: dict[str, tuple[int, Optional[MessageCallback]]] = {}
        self._last_error: Optional[str] = None
        self._started = False

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

    @property
    def status(self) -> MqttStatus:
        return MqttStatus(self.is_connected, self.client_id, self._last_error, f"{self.settings.host}:{self.settings.port}")

    def start(self, wait_timeout: float = 8.0) -> MqttStatus:
        errors = self.settings.validate()
        if errors:
            raise MqttConnectionError("Configuración MQTT inválida: " + "; ".join(errors))
        if self._started and self.is_connected:
            return self.status
        if self._started and self._client is not None:
            # El loop de paho mantiene la reconexión automática; no se inicia un
            # segundo hilo de red durante una caída transitoria.
            if self._connected.wait(wait_timeout):
                return self.status
            try:
                self._client.reconnect()
            except Exception as error:
                self._last_error = str(error)
                raise MqttConnectionError(f"No fue posible reconectar a {self.settings.host}:{self.settings.port}: {error}") from error
            if self._connected.wait(wait_timeout):
                return self.status
            raise MqttConnectionError(self._last_error or "El broker no confirmó la reconexión")
        self._build_client()
        try:
            self._client.connect(self.settings.host, self.settings.port, self.settings.keepalive)
            self._started = True
            self._client.loop_start()
        except Exception as error:
            self._last_error = str(error)
            raise MqttConnectionError(f"No fue posible conectar a {self.settings.host}:{self.settings.port}: {error}") from error
        if not self._connected.wait(wait_timeout):
            message = self._last_error or "el broker no confirmó la conexión dentro del tiempo límite"
            self.stop()
            raise MqttConnectionError(message)
        return self.status

    def stop(self) -> None:
        client = self._client
        self._connected.clear()
        self._started = False
        if client is None:
            return
        try:
            client.disconnect()
        except Exception as error:
            logger.warning("Error al desconectar MQTT: %s", error)
        try:
            client.loop_stop()
        except Exception:
            pass

    def subscribe(self, topic: str, callback: Optional[MessageCallback] = None, qos: int = 1) -> None:
        if qos not in {0, 1, 2}:
            raise ValueError("QoS debe ser 0, 1 o 2")
        self._subscriptions[topic] = (qos, callback)
        if self.is_connected:
            result, _mid = self._client.subscribe(topic, qos=qos)
            if result != 0:
                raise MqttConnectionError(f"No se pudo suscribir a {topic}; rc={result}")

    def publish(self, topic: str, payload: str | bytes, qos: int = 1, retain: bool = False, timeout: float = 5.0) -> None:
        if not self.is_connected or self._client is None:
            raise MqttNotConnectedError("El cliente MQTT no tiene una conexión verificada")
        result = self._client.publish(topic, payload, qos=qos, retain=retain)
        if result.rc != 0:
            raise MqttConnectionError(f"Publicación rechazada en {topic}; rc={result.rc}")
        if qos > 0:
            result.wait_for_publish(timeout=timeout)

    def _build_client(self) -> None:
        if self._client is not None:
            return
        try:
            import paho.mqtt.client as mqtt
        except ImportError as error:
            raise MqttConnectionError("Falta la dependencia paho-mqtt; instala requirements.txt") from error
        factory = self._client_factory or mqtt.Client
        try:
            self._client = factory(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=self.client_id,
                transport=self.settings.transport,
            )
        except (TypeError, AttributeError):
            # Compatibilidad con paho-mqtt 1.x y fakes sencillos de pruebas.
            self._client = factory(client_id=self.client_id, transport=self.settings.transport)
        if self.settings.transport == "websockets" and hasattr(self._client, "ws_set_options"):
            self._client.ws_set_options(path=self.settings.ws_path)
        if self.settings.use_tls:
            self._client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
            self._client.tls_insecure_set(False)
        if self.settings.username:
            self._client.username_pw_set(self.settings.username, self.settings.password)
        if hasattr(self._client, "reconnect_delay_set"):
            self._client.reconnect_delay_set(min_delay=1, max_delay=60)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        code = getattr(reason_code, "value", reason_code)
        if code != 0:
            self._last_error = f"EMQX rechazó la conexión; código={code}"
            self._connected.clear()
            logger.error(self._last_error)
            return
        self._last_error = None
        self._connected.set()
        for topic, (qos, _callback) in self._subscriptions.items():
            result, _mid = client.subscribe(topic, qos=qos)
            if result != 0:
                logger.error("No se pudo restaurar la suscripción %s; rc=%s", topic, result)

    def _on_disconnect(self, client, userdata, *args):
        self._connected.clear()
        reason_code = args[-2] if len(args) >= 2 else (args[-1] if args else "desconocido")
        code = getattr(reason_code, "value", reason_code)
        if code not in (0, "0", None):
            self._last_error = f"Desconexión MQTT; código={code}"
            logger.warning(self._last_error)

    def _on_message(self, client, userdata, message):
        subscription = self._subscriptions.get(message.topic)
        if subscription is None:
            for filter_topic, candidate in self._subscriptions.items():
                if self._topic_matches(filter_topic, message.topic):
                    subscription = candidate
                    break
        if subscription and subscription[1]:
            try:
                subscription[1](message.topic, message.payload, message.qos, message.retain)
            except Exception:
                logger.exception("Error procesando mensaje MQTT de %s", message.topic)

    @staticmethod
    def _topic_matches(filter_topic: str, topic: str) -> bool:
        filter_parts, topic_parts = filter_topic.split("/"), topic.split("/")
        if len(filter_parts) != len(topic_parts):
            return filter_parts and filter_parts[-1] == "#" and len(topic_parts) >= len(filter_parts) - 1
        return all(filter_part in {"+", topic_part} or filter_part == "#" for filter_part, topic_part in zip(filter_parts, topic_parts))
