"""Pruebas locales MQTT/Serial sin contactar el broker remoto ni accionar hardware."""

import json

import pytest
import serial

from src.hardware.serial_manager import parse_telemetry_frame, parse_telemetry_line
from src.mqtt.bridge import SerialMqttBridge
from src.mqtt.client import MqttConnectionError
from src.mqtt.config import MqttSettings
from src.mqtt.messages import TelemetryPayload, parse_telemetry_payload
from src.mqtt.recorder import MqttTelemetryRecorder
from src.mqtt.streamlit_adapter import StreamlitMqttSubscriber
from src.mqtt.topics import MqttTopics
from src.mqtt.virtual_nodes import VirtualNode, VirtualNodePublisher
from src.persistence import ExperimentManager, MeasurementRepository, SQLiteDatabase, initialize_schema
from src.persistence.models import ExperimentPhase, GrainType, MeasurementOrigin


class FakeSerial:
    def __init__(self, lines):
        self.lines = iter(lines)
        self.sent = []
        self.open = True

    def is_open(self):
        return self.open

    def read_line(self):
        return next(self.lines, None)

    def send_command(self, command):
        if not self.open:
            raise OSError("USB desconectado")
        self.sent.append(command)

    def close(self):
        self.open = False


class FakeMqtt:
    def __init__(self):
        self.published = []
        self.subscriptions = []
        self.is_connected = True

    def subscribe(self, topic, callback=None, qos=1):
        self.subscriptions.append((topic, callback, qos))

    def publish(self, topic, payload, qos=1, retain=False):
        self.published.append((topic, payload, qos, retain))

    def start(self, wait_timeout=8.0):
        return None

    def stop(self):
        self.is_connected = False


class OfflineMqtt(FakeMqtt):
    def publish(self, topic, payload, qos=1, retain=False):
        raise MqttConnectionError("internet desconectado")


def test_settings_and_topics_match_emqx_contract(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("MQTT_HOST=broker.example\nMQTT_PORT=443\nMQTT_TRANSPORT=websockets\nMQTT_WS_PATH=/mqtt\nMQTT_USE_TLS=true\n", encoding="utf-8")
    settings = MqttSettings.from_env(dotenv)
    topics = MqttTopics("nodo1")
    assert settings.host == "broker.example"
    assert settings.port == 443
    assert settings.transport == "websockets"
    assert settings.validate() == []
    assert topics.telemetry == "secado/nodo1/telemetria"
    assert topics.state == "secado/nodo1/estado"
    assert topics.command == "secado/nodo1/cmd"
    assert topics.ack == "secado/nodo1/ack"
    assert topics.telemetry_subscription == "secado/+/telemetria"


def test_json_contract_and_current_csv_protocol_are_compatible():
    reading = parse_telemetry_line("28.5,65.0,26.2")
    payload = TelemetryPayload.from_reading("nodo1", 4, reading, simulado=False)
    decoded = parse_telemetry_payload(payload.to_json())
    assert decoded.node_id == "nodo1"
    assert decoded.sequence == 4
    assert decoded.t_amb == 28.5
    assert decoded.hum == 65.0
    assert decoded.t_grano == 26.2
    assert decoded.simulado is False
    with pytest.raises(ValueError):
        parse_telemetry_payload(json.dumps({"node_id": "nodo1", "simulado": False}))


def test_updated_firmware_frame_is_validated_and_legacy_csv_remains_supported():
    frame = parse_telemetry_frame("TEL,15,28.50,65.00,31.20,30.00,CONTROL,NA,255")
    assert frame.sequence == 15
    assert frame.mode == "CONTROL"
    assert frame.heater_state is None
    assert frame.fan_pwm == 255
    legacy = parse_telemetry_frame("28.5,65.0,26.2")
    assert legacy.sequence is None
    with pytest.raises(ValueError):
        parse_telemetry_frame("TEL,16,28.5,65,31,55,CONTROL,NA,0")


def test_existing_emqx_payload_aliases_are_read_without_inventing_fields():
    payload = parse_telemetry_payload(json.dumps({
        "id": "secador_01", "ts": "2026-10-27T02:11:53.815Z",
        "t_amb": 24.23, "hum": 51.03, "t_grano": 37.94,
        "t_ideal": 38.0, "led": "V", "ventilador_pwm": 0,
    }))
    assert payload.node_id == "secador_01"
    assert payload.sequence == 0  # El productor existente no reporta secuencia.
    assert payload.simulado is False
    assert payload.sp == 38.0
    assert payload.foco == "V"
    assert payload.vent == 0


def test_streamlit_subscriber_keeps_telemetry_ack_and_state_messages():
    subscriber = StreamlitMqttSubscriber(FakeMqtt())
    subscriber._on_message("secado/nodo1/telemetria", json.dumps({
        "node_id": "nodo1", "timestamp": "2026-10-27T02:11:53Z",
        "sequence": 1, "t_amb": 24, "hum": 50, "t_grano": 30, "simulado": False,
    }).encode(), 1, False)
    subscriber._on_message("secado/nodo1/ack", b'{"accepted":true,"request_id":"abc"}', 1, False)
    subscriber._on_message("secado/nodo1/estado", b'{"estado":"online"}', 1, False)
    messages = subscriber.poll()
    assert len(messages) == 3
    assert any(item.get("accepted") is True for item in messages)
    assert any(item.get("estado") == "online" for item in messages)


def test_bridge_publishes_valid_csv_and_persists_only_with_explicit_experiment(tmp_path):
    database = SQLiteDatabase(tmp_path / "experimentos.db")
    initialize_schema(database)
    manager = ExperimentManager(database)
    experiment = manager.create_experiment(
        grain_type=GrainType.CAFE, phase=ExperimentPhase.DESPUES,
        origin=MeasurementOrigin.REAL, thermal_reference_c=23.0,
    )
    bridge = SerialMqttBridge(
        FakeSerial(["28.5,65.0,26.2"]), FakeMqtt(), "nodo1",
        measurement_repository=MeasurementRepository(database),
        experiment_manager=manager, experiment_id=experiment.id,
    )
    payload = bridge.run_once()
    assert payload is not None
    assert bridge.mqtt_client.published[0][0] == "secado/nodo1/telemetria"
    assert parse_telemetry_payload(bridge.mqtt_client.published[0][1]).simulado is False
    assert MeasurementRepository(database).count_for_experiment(experiment.id) == 1


def test_bridge_publishes_enriched_firmware_frame_without_inventing_heater(tmp_path):
    database = SQLiteDatabase(tmp_path / "experimentos.db")
    initialize_schema(database)
    manager = ExperimentManager(database)
    experiment = manager.create_experiment(
        grain_type=GrainType.CAFE, phase=ExperimentPhase.DESPUES,
        origin=MeasurementOrigin.REAL, thermal_reference_c=30.0,
    )
    mqtt = FakeMqtt()
    bridge = SerialMqttBridge(
        FakeSerial(["TEL,7,28.5,65.0,31.2,30.0,CONTROL,NA,255"]), mqtt, "nodo1",
        measurement_repository=MeasurementRepository(database), experiment_id=experiment.id,
    )
    payload = bridge.run_once()
    assert payload.sequence == 7
    assert payload.modo == "CONTROL"
    assert payload.vent == 255
    assert payload.foco is None
    assert MeasurementRepository(database).count_for_experiment(experiment.id) == 1


def test_bridge_rejects_unauthorized_command_and_accepts_firmware_command():
    serial = FakeSerial([])
    mqtt = FakeMqtt()
    bridge = SerialMqttBridge(serial, mqtt, "nodo1")
    bridge._on_command("secado/nodo1/cmd", b"FORMAT_DISK", 1, False)
    bridge._on_command("secado/nodo1/cmd", b"P", 1, False)
    bridge._on_command("secado/nodo1/cmd", b"MODO:CONTROL", 1, False)
    bridge._on_command("secado/nodo1/cmd", b"SP:30", 1, False)
    assert serial.sent == ["P", "MODO:CONTROL", "SP:30"]
    acknowledgements = [json.loads(item[1]) for item in mqtt.published]
    assert acknowledgements[0]["accepted"] is False
    assert acknowledgements[1]["accepted"] is True


def test_bridge_forwards_real_firmware_ack_without_inventing_actuator_values():
    mqtt = FakeMqtt()
    bridge = SerialMqttBridge(FakeSerial(["ACK: LED Verde Encendido"]), mqtt, "secador_01")
    assert bridge.run_once() is None
    topic, raw_payload, _qos, _retain = mqtt.published[0]
    assert topic == "secado/secador_01/ack"
    ack = json.loads(raw_payload)
    assert ack["message"] == "ACK: LED Verde Encendido"
    assert "vent" not in ack
    assert "foco" not in ack


def test_mqtt_recorder_associates_origin_and_avoids_duplicate_messages(tmp_path):
    database = SQLiteDatabase(tmp_path / "experimentos.db")
    initialize_schema(database)
    manager = ExperimentManager(database)
    experiment = manager.create_experiment(
        grain_type=GrainType.CAFE, phase=ExperimentPhase.ANTES,
        origin=MeasurementOrigin.SIMULADO, thermal_reference_c=23.0,
    )
    recorder = MqttTelemetryRecorder(
        FakeMqtt(), MeasurementRepository(database), manager, {"sim1": experiment.id}
    )
    payload = TelemetryPayload.from_reading("sim1", 1, parse_telemetry_line("28.5,65.0,26.2"), True)
    assert recorder.on_message("secado/sim1/telemetria", payload.to_json().encode(), 1, False) is True
    assert recorder.on_message("secado/sim1/telemetria", payload.to_json().encode(), 1, False) is False
    assert recorder.valid_count == 1
    assert recorder.duplicate_count == 1
    assert MeasurementRepository(database).count_for_experiment(experiment.id) == 1


def test_bridge_persists_before_publish_when_internet_is_lost(tmp_path):
    database = SQLiteDatabase(tmp_path / "experimentos.db")
    initialize_schema(database)
    manager = ExperimentManager(database)
    experiment = manager.create_experiment(
        grain_type=GrainType.CAFE, phase=ExperimentPhase.DESPUES,
        origin=MeasurementOrigin.REAL, thermal_reference_c=23.0,
    )
    bridge = SerialMqttBridge(
        FakeSerial(["28.5,65.0,26.2"]), OfflineMqtt(), "secador_01",
        measurement_repository=MeasurementRepository(database), experiment_id=experiment.id,
    )
    with pytest.raises(MqttConnectionError):
        bridge.run_once()
    assert MeasurementRepository(database).count_for_experiment(experiment.id) == 1


def test_bridge_reports_usb_disconnect_without_fabricating_measurements():
    fake_serial = FakeSerial([])
    fake_serial.open = False
    bridge = SerialMqttBridge(fake_serial, FakeMqtt(), "secador_01")
    with pytest.raises(serial.SerialException, match="puerto serie"):
        bridge.run_once()


def test_virtual_nodes_are_reproducible_separate_and_never_subscribe_commands():
    first = VirtualNodePublisher(FakeMqtt(), [VirtualNode("sim1", seed=10001), VirtualNode("sim2", seed=10002)])
    second = VirtualNodePublisher(FakeMqtt(), [VirtualNode("sim1", seed=10001), VirtualNode("sim2", seed=10002)])
    first_payloads = first.publish_once()
    second_payloads = second.publish_once()
    assert [payload.to_dict() | {"timestamp": "fixed"} for payload in first_payloads] == [payload.to_dict() | {"timestamp": "fixed"} for payload in second_payloads]
    assert all(payload.simulado for payload in first_payloads)
    assert [topic for topic, *_ in first.mqtt_client.published] == ["secado/sim1/telemetria", "secado/sim2/telemetria"]
    assert first.mqtt_client.subscriptions == []
