"""Puente independiente Arduino Nano (USB/Serial) ↔ MQTT."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from threading import Event
from typing import Optional

import serial

from ..hardware.serial_manager import SerialManager, parse_telemetry_frame
from ..persistence.experiments import ExperimentManager
from ..persistence.measurements import MeasurementRepository
from ..persistence.models import Event as ExperimentEvent, Measurement, MeasurementOrigin
from .client import MqttClient, MqttConnectionError
from .messages import TelemetryPayload, utc_timestamp
from .topics import MqttTopics

logger = logging.getLogger(__name__)


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class BridgeStatus:
    serial_connected: bool
    mqtt_connected: bool
    node_id: str
    sequence: int
    last_error: Optional[str] = None


class SerialMqttBridge:
    """Servicio sin dependencia de Streamlit; solo persiste si recibe un experimento explícito."""

    ALLOWED_COMMANDS = {"V", "A", "R", "1", "2", "0", "I", "P", "PARAR", "ESTADO"}

    def __init__(
        self,
        serial_manager: SerialManager,
        mqtt_client: MqttClient,
        node_id: str,
        measurement_repository: Optional[MeasurementRepository] = None,
        experiment_manager: Optional[ExperimentManager] = None,
        experiment_id: Optional[int] = None,
        simulated: bool = False,
    ):
        self.serial_manager = serial_manager
        self.mqtt_client = mqtt_client
        self.node_id = node_id
        self.topics = MqttTopics(node_id)
        self.measurement_repository = measurement_repository
        self.experiment_manager = experiment_manager
        self.experiment_id = experiment_id
        self.simulated = simulated
        self.sequence = 0
        self.last_error: Optional[str] = None
        self._stop_event = Event()

    def start(self, connect_serial: bool = True, wait_timeout: float = 8.0) -> BridgeStatus:
        if self.simulated:
            raise ValueError("El puente físico no puede marcarse como simulado; use VirtualNodePublisher")
        if connect_serial:
            self.serial_manager.connect()
        self.mqtt_client.subscribe(self.topics.command, self._on_command, qos=1)
        self.mqtt_client.start(wait_timeout=wait_timeout)
        self.publish_state("online")
        return self.status

    def stop(self) -> None:
        self._stop_event.set()
        try:
            self.publish_state("offline")
        except Exception:
            pass
        self.mqtt_client.stop()
        self.serial_manager.close()

    @property
    def status(self) -> BridgeStatus:
        return BridgeStatus(self.serial_manager.is_open(), self.mqtt_client.is_connected, self.node_id, self.sequence, self.last_error)

    def run_once(self) -> Optional[TelemetryPayload]:
        """Lee y publica como máximo una trama CSV válida."""
        if not self.serial_manager.is_open():
            raise serial.SerialException("El puerto serie no está abierto")
        raw_line = self.serial_manager.read_line()
        if not raw_line:
            return None
        if raw_line.startswith("ACK"):
            self._publish_serial_ack(raw_line)
            return None
        if raw_line.startswith("ERR"):
            self._publish_serial_ack(raw_line, accepted=False)
            return None
        if raw_line.startswith("SISTEMA"):
            self.publish_state("ready")
            return None
        if raw_line.startswith("ESTADO"):
            self.publish_state(raw_line)
            return None
        frame = parse_telemetry_frame(raw_line)
        if frame is None:
            return None
        if frame.sequence is not None:
            self.sequence = max(self.sequence, frame.sequence)
        else:
            self.sequence += 1
        payload = TelemetryPayload.from_reading(
            self.node_id, self.sequence, frame.reading, simulado=False,
            sp=frame.setpoint, foco=frame.heater_state,
            vent=frame.fan_pwm, modo=frame.mode,
        )
        # Primero se conserva localmente: una caída de Internet no debe perder la medición.
        self._persist(payload)
        self.mqtt_client.publish(self.topics.telemetry, payload.to_json(), qos=1)
        return payload

    def run_forever(self, stop_event: Optional[Event] = None, reconnect_delay: float = 5.0) -> None:
        """Bucle del servicio con tolerancia a desconexión USB; no debe ejecutarse dentro de Streamlit."""
        stop_event = stop_event or self._stop_event
        while not stop_event.is_set():
            try:
                if not self.mqtt_client.is_connected:
                    self.mqtt_client.start()
                if not self.serial_manager.is_open():
                    self.serial_manager.connect()
                self.run_once()
            except (serial.SerialException, OSError, MqttConnectionError) as error:
                self.last_error = str(error)
                logger.error("Puente %s: %s", self.node_id, error)
                self._record_event("error_puente", str(error))
                self.serial_manager.close()
                stop_event.wait(reconnect_delay)
            except ValueError as error:
                # Una trama inválida no detiene el servicio ni se publica ni se persiste.
                self.last_error = str(error)
                logger.warning("Trama serial descartada: %s", error)
                self._record_event("lectura_invalida", str(error))

    def publish_state(self, state: str) -> None:
        payload = {"node_id": self.node_id, "timestamp": utc_timestamp(), "estado": state, "simulado": False, "version": "1.0"}
        self.mqtt_client.publish(self.topics.state, json.dumps(payload, separators=(",", ":")), qos=1, retain=True)

    def _on_command(self, topic: str, raw_payload: bytes, qos: int, retain: bool) -> None:
        """Acepta texto de firmware o JSON {command: ...}; nunca ejecuta comandos no autorizados."""
        try:
            decoded = raw_payload.decode("utf-8").strip()
            request_id = None
            if decoded.startswith("{"):
                command_payload = json.loads(decoded)
                command = str(command_payload.get("command", ""))
                request_id = command_payload.get("request_id")
            else:
                command = decoded
            command = command.rstrip("\n")
            upper_command = command.upper()
            allowed = (
                upper_command in self.ALLOWED_COMMANDS
                or upper_command.startswith(("T:", "D:", "SP:", "VENT:", "MODO:"))
            )
            if not allowed or len(command) > 40:
                self._publish_ack(command, False, "comando no autorizado", request_id)
                return
            if not self.serial_manager.is_open():
                self._publish_ack(command, False, "Arduino desconectado", request_id)
                return
            self.serial_manager.send_command(command)
            self._publish_ack(command, True, "comando enviado al Arduino", request_id)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
            self._publish_ack("", False, f"payload inválido: {error}", None)
        except (serial.SerialException, OSError) as error:
            self._publish_ack("", False, f"error serial: {error}", None)
            self.serial_manager.close()

    def _publish_ack(self, command: str, accepted: bool, message: str, request_id: Optional[str]) -> None:
        payload = {"node_id": self.node_id, "timestamp": utc_timestamp(), "command": command, "accepted": accepted, "message": message, "simulado": False, "version": "1.0"}
        if request_id is not None:
            payload["request_id"] = request_id
        try:
            self.mqtt_client.publish(self.topics.ack, json.dumps(payload, separators=(",", ":")), qos=1)
        except MqttConnectionError as error:
            logger.error("No se pudo publicar ACK: %s", error)
        self._record_event("comando", message)

    def _publish_serial_ack(self, raw_line: str, accepted: bool = True) -> None:
        """Reenvía la confirmación textual real del firmware, sin inferir actuadores."""
        payload = {
            "node_id": self.node_id,
            "timestamp": utc_timestamp(),
            "accepted": accepted,
            "message": raw_line,
            "simulado": False,
            "version": "1.0",
        }
        try:
            self.mqtt_client.publish(self.topics.ack, json.dumps(payload, separators=(",", ":")), qos=1)
        except MqttConnectionError as error:
            logger.error("No se pudo publicar ACK del firmware: %s", error)

    def _persist(self, payload: TelemetryPayload) -> None:
        if self.measurement_repository is None or self.experiment_id is None:
            return
        inserted = self.measurement_repository.record(Measurement(
            experiment_id=self.experiment_id,
            timestamp_utc=payload.timestamp_utc,
            node_id=payload.node_id,
            sequence_number=payload.sequence,
            ambient_temperature_c=payload.t_amb,
            ambient_humidity_percent=payload.hum,
            grain_temperature_c=payload.t_grano,
            setpoint_c=payload.sp,
            focus_state=payload.foco,
            fan_pwm=payload.vent,
            origin=MeasurementOrigin.REAL,
            quality="valida",
        ))
        if not inserted:
            logger.info("Medición duplicada ignorada: %s/%s", payload.node_id, payload.sequence)

    def _record_event(self, event_type: str, description: str) -> None:
        if self.experiment_manager is not None and self.experiment_id is not None:
            try:
                self.experiment_manager.record_event(ExperimentEvent(
                    experiment_id=self.experiment_id,
                    event_type=event_type,
                    description=description,
                ))
            except Exception:
                logger.exception("No se pudo registrar el evento de puente")
