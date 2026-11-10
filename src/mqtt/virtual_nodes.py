"""Nodos virtuales reproducibles para pruebas MQTT sin Arduino físico."""

from dataclasses import dataclass
import random
from threading import Event
from typing import Iterable, Optional

from .client import MqttClient
from .messages import TelemetryPayload
from .topics import MqttTopics
from ..hardware.serial_manager import TelemetryReading


@dataclass
class VirtualNode:
    node_id: str
    seed: int
    sequence: int = 0
    ideal_temperature: float = 23.0

    def __post_init__(self):
        self._random = random.Random(self.seed)
        self._grain_temperature = self.ideal_temperature + 4.0

    def next_payload(self) -> TelemetryPayload:
        self.sequence += 1
        ambient = round(self._random.uniform(24.0, 32.0), 1)
        humidity = round(self._random.uniform(50.0, 78.0), 1)
        self._grain_temperature = round(self._grain_temperature - 0.2 + self._random.uniform(-0.3, 0.3), 1)
        reading = TelemetryReading(ambient, humidity, self._grain_temperature)
        return TelemetryPayload.from_reading(
            node_id=self.node_id,
            sequence=self.sequence,
            reading=reading,
            simulado=True,
            timestamp_utc=None,
            sp=self.ideal_temperature,
            modo="simulacion",
        )


class VirtualNodePublisher:
    """Publica varios nodos simulados; no suscribe cmd ni conoce el puerto serial."""

    def __init__(self, mqtt_client: MqttClient, nodes: Iterable[VirtualNode]):
        self.mqtt_client = mqtt_client
        self.nodes = list(nodes)

    def start(self, wait_timeout: float = 8.0):
        return self.mqtt_client.start(wait_timeout=wait_timeout)

    def publish_once(self) -> list[TelemetryPayload]:
        payloads = []
        for node in self.nodes:
            payload = node.next_payload()
            self.mqtt_client.publish(MqttTopics(node.node_id).telemetry, payload.to_json(), qos=1)
            payloads.append(payload)
        return payloads

    def stop(self):
        self.mqtt_client.stop()

    def run_forever(self, interval_seconds: float = 2.0, stop_event: Optional[Event] = None):
        stop_event = stop_event or Event()
        while not stop_event.is_set():
            self.publish_once()
            stop_event.wait(interval_seconds)


def default_virtual_nodes() -> list[VirtualNode]:
    return [VirtualNode(f"sim{index}", seed=10_000 + index) for index in range(1, 5)]
