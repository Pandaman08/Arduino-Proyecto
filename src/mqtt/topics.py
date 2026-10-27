"""Convención de tópicos MQTT del proyecto."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MqttTopics:
    node_id: str
    prefix: str = "secado"

    @property
    def telemetry(self) -> str:
        return f"{self.prefix}/{self.node_id}/telemetria"

    @property
    def state(self) -> str:
        return f"{self.prefix}/{self.node_id}/estado"

    @property
    def command(self) -> str:
        return f"{self.prefix}/{self.node_id}/cmd"

    @property
    def ack(self) -> str:
        return f"{self.prefix}/{self.node_id}/ack"

    @property
    def test(self) -> str:
        return f"{self.prefix}/{self.node_id}/test"

    @property
    def telemetry_subscription(self) -> str:
        return f"{self.prefix}/+/telemetria"
