"""Registrador de telemetría MQTT en SQLite para experimentos explícitos."""

import logging
from typing import Optional

from ..persistence.experiments import ExperimentManager
from ..persistence.measurements import MeasurementRepository
from ..persistence.models import Event, Measurement, MeasurementOrigin
from .client import MqttClient
from .messages import parse_telemetry_payload

logger = logging.getLogger(__name__)


class MqttTelemetryRecorder:
    """Consume telemetría validada y la asocia a un experimento por nodo."""

    def __init__(
        self,
        mqtt_client: MqttClient,
        measurements: MeasurementRepository,
        experiment_manager: Optional[ExperimentManager] = None,
        experiment_by_node: Optional[dict[str, int]] = None,
    ):
        self.mqtt_client = mqtt_client
        self.measurements = measurements
        self.experiment_manager = experiment_manager
        self.experiment_by_node = experiment_by_node or {}
        self.valid_count = 0
        self.invalid_count = 0
        self.duplicate_count = 0

    def start(self, topic_filter: str = "secado/+/telemetria", wait_timeout: float = 8.0):
        self.mqtt_client.subscribe(topic_filter, self.on_message, qos=1)
        return self.mqtt_client.start(wait_timeout=wait_timeout)

    def stop(self):
        self.mqtt_client.stop()

    def on_message(self, topic: str, raw_payload: bytes, qos: int, retain: bool):
        try:
            payload = parse_telemetry_payload(raw_payload)
            experiment_id = self.experiment_by_node.get(payload.node_id)
            if experiment_id is None:
                logger.info("Telemetría %s recibida sin experimento asignado; no se persiste", payload.node_id)
                return False
            origin = MeasurementOrigin.SIMULADO if payload.simulado else MeasurementOrigin.REAL
            inserted = self.measurements.record(Measurement(
                experiment_id=experiment_id,
                timestamp_utc=payload.timestamp_utc,
                node_id=payload.node_id,
                message_id=None if payload.sequence == 0 else f"{payload.node_id}:{payload.sequence}",
                sequence_number=None if payload.sequence == 0 else payload.sequence,
                ambient_temperature_c=payload.t_amb,
                ambient_humidity_percent=payload.hum,
                grain_temperature_c=payload.t_grano,
                reference_temperature_c=payload.sp,
                setpoint_c=payload.sp,
                focus_state=payload.foco,
                fan_pwm=payload.vent,
                origin=origin,
                quality="valida",
            ))
            if inserted:
                self.valid_count += 1
            else:
                self.duplicate_count += 1
            return inserted
        except (ValueError, KeyError) as error:
            self.invalid_count += 1
            logger.warning("Telemetría MQTT descartada en %s: %s", topic, error)
            topic_parts = topic.split("/")
            node_id = topic_parts[1] if len(topic_parts) >= 3 else None
            if node_id in self.experiment_by_node:
                self._record_event(self.experiment_by_node[node_id], f"Telemetría MQTT inválida: {error}")
            return False

    def _record_event(self, experiment_id: int, description: str):
        if self.experiment_manager is not None:
            self.experiment_manager.record_event(Event(
                experiment_id=experiment_id,
                event_type="telemetria_mqtt",
                description=description,
            ))
