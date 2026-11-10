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


@pytest.mark.parametrize('command', ['SP:51', 'SP:nan', 'VENT:256', 'VENT:-1', 'MODO:INVALIDO', 'SP:30\nPARAR'])
def test_bridge_strict_command_validation(command):
    serial_port = FakeSerial([])
    mqtt = FakeMqtt()
    bridge = SerialMqttBridge(serial_port, mqtt, 'secador_01')
    bridge._on_command(bridge.topics.command, json.dumps({'command': command}).encode(), 1, False)
    assert serial_port.sent == []
    assert json.loads(mqtt.published[-1][1])['accepted'] is False


def test_bridge_rejects_retained_and_deduplicates_request_id():
    serial_port = FakeSerial([])
    mqtt = FakeMqtt()
    bridge = SerialMqttBridge(serial_port, mqtt, 'secador_01')
    payload = b'{"command":"SP:30","request_id":"mobile-unique"}'
    bridge._on_command(bridge.topics.command, payload, 1, True)
    assert serial_port.sent == []
    bridge._on_command(bridge.topics.command, payload, 1, False)
    bridge._on_command(bridge.topics.command, payload, 1, False)
    assert len(serial_port.sent) == 1
    assert serial_port.sent[0].startswith('REQ,') and serial_port.sent[0].endswith(',SP:30')
    assert json.loads(mqtt.published[-1][1])['accepted'] is False


def test_bridge_does_not_invent_firmware_request_correlation():
    mqtt = FakeMqtt()
    bridge = SerialMqttBridge(FakeSerial(['ACK:MODO_CONTROL_APLICADO']), mqtt, 'secador_01')
    bridge._on_command(bridge.topics.command, b'{"command":"MODO:CONTROL","request_id":"mobile-unique"}', 1, False)
    bridge.run_once()
    assert json.loads(mqtt.published[0][1])['request_id'] == 'mobile-unique'
    assert 'request_id' not in json.loads(mqtt.published[-1][1])


def test_streamlit_connection_recovers_after_initial_failure_without_caching_none():
    from src.mqtt.streamlit_adapter import StreamlitMqttConnection
    now = [0.0]
    online = StreamlitMqttSubscriber(FakeMqtt())
    results = iter([(None, 'Error de conexión MQTT'), (online, 'conectado')])
    calls = []
    def factory():
        calls.append(True)
        return next(results)
    connection = StreamlitMqttConnection(factory=factory, clock=lambda: now[0])
    assert connection.get()[0] is None
    assert connection.get()[0] is None
    assert len(calls) == 1
    now[0] = 5.0
    assert connection.get()[0] is online
    assert connection.get()[0] is online
    assert len(calls) == 2


def test_streamlit_reconnect_stops_old_client_and_reloads_config(monkeypatch):
    import src.mqtt.streamlit_adapter as adapter
    reloads = []
    monkeypatch.setattr(adapter, 'load_dotenv', lambda **kwargs: reloads.append(kwargs))
    first = StreamlitMqttSubscriber(FakeMqtt())
    second = StreamlitMqttSubscriber(FakeMqtt())
    results = iter([(first, 'conectado'), (second, 'conectado')])
    connection = adapter.StreamlitMqttConnection(factory=lambda: next(results))
    assert connection.get()[0] is first
    assert connection.get(force=True)[0] is second
    assert first.is_connected is False
    assert reloads == [{'override': True}]


def test_dotenv_reload_requires_explicit_override(tmp_path, monkeypatch):
    from src.mqtt.config import load_dotenv
    monkeypatch.setenv('LAB11_TEST_VALUE', 'externo')
    path = tmp_path / '.env'
    path.write_text('LAB11_TEST_VALUE=local\n', encoding='utf-8')
    load_dotenv(path)
    import os
    assert os.environ['LAB11_TEST_VALUE'] == 'externo'
    load_dotenv(path, override=True)
    assert os.environ['LAB11_TEST_VALUE'] == 'local'


@pytest.mark.parametrize('cause, expected', [
    (ModuleNotFoundError("No module named 'paho'"), 'paho-mqtt'),
    (__import__('socket').gaierror(-2, 'secret-password'), 'DNS'),
    (__import__('ssl').SSLCertVerificationError(1, 'secret-password'), 'certificado TLS'),
    (TimeoutError('secret-password'), 'Tiempo agotado'),
    (ConnectionRefusedError('secret-password'), 'rechazó la conexión de red'),
    (PermissionError('secret-password'), 'permisos'),
])
def test_mqtt_diagnostic_explains_cause_without_exposing_secrets(cause, expected):
    from src.mqtt.streamlit_adapter import connection_error_message
    error = MqttConnectionError('secret-password')
    error.__cause__ = cause
    message = connection_error_message(error)
    assert expected in message
    assert 'secret-password' not in message


def test_mqtt_diagnostic_distinguishes_broker_authentication_rejection():
    from src.mqtt.streamlit_adapter import connection_error_message
    message = connection_error_message(MqttConnectionError('EMQX rechazó la conexión; código=5'))
    assert 'autenticación' in message


def test_bridge_correlates_out_of_order_firmware_ack_and_never_guesses_legacy_ack():
    mqtt, port = FakeMqtt(), FakeSerial([])
    bridge = SerialMqttBridge(port, mqtt, 'secador_01')
    for request_id, command in [('mobile1', 'MODO:CONTROL'), ('web2', 'SP:30')]:
        bridge._on_command(bridge.topics.command, json.dumps({'command': command, 'request_id': request_id}).encode(), 1, False)
    first, second = [line.split(',')[1] for line in port.sent]
    bridge._publish_serial_ack(f'ACK:SP_APLICADO_CONTROL|request_id={second}')
    ack = json.loads(mqtt.published[-1][1])
    assert (ack['request_id'], ack['command'], ack['source'], ack['phase'], ack['correlated']) == ('web2', 'SP:30', 'firmware', 'applied', True)
    bridge._publish_serial_ack('ERR:SENSOR_DHT', accepted=False)
    assert 'request_id' not in json.loads(mqtt.published[-1][1])
    bridge._publish_serial_ack(f'ACK:MODO_CONTROL_APLICADO|request_id={first}')
    assert json.loads(mqtt.published[-1][1])['request_id'] == 'mobile1'
    bridge._publish_serial_ack(f'ACK:MODO_CONTROL_APLICADO|request_id={first}')
    assert json.loads(mqtt.published[-1][1])['correlated'] is False


def test_bridge_correlated_err_status_and_expired_id(monkeypatch):
    import src.mqtt.bridge as module
    clock = [0.0]
    monkeypatch.setattr(module, 'monotonic', lambda: clock[0])
    mqtt, port = FakeMqtt(), FakeSerial([])
    bridge = SerialMqttBridge(port, mqtt, 'secador_01')
    bridge._on_command(bridge.topics.command, b'{"command":"VENT:100","request_id":"fan-request"}', 1, False)
    wire = port.sent[-1].split(',')[1]
    bridge._publish_serial_ack(f'ERR:VENT_SOLO_MONITOREO|request_id={wire}', accepted=False)
    ack = json.loads(mqtt.published[-1][1])
    assert ack['accepted'] is False and ack['request_id'] == 'fan-request' and ack['correlated'] is True
    bridge._on_command(bridge.topics.command, b'{"command":"ESTADO","request_id":"status-request"}', 1, False)
    wire = port.sent[-1].split(',')[1]
    bridge._publish_serial_ack(f'ACK:ESTADO_CONSULTADO|request_id={wire}')
    assert json.loads(mqtt.published[-1][1])['request_id'] == 'status-request'
    bridge._on_command(bridge.topics.command, b'{"command":"SP:30","request_id":"late-request"}', 1, False)
    wire = port.sent[-1].split(',')[1]
    clock[0] = 31.0
    bridge._publish_serial_ack(f'ACK:SP_APLICADO_CONTROL|request_id={wire}')
    assert 'request_id' not in json.loads(mqtt.published[-1][1])


def test_mqtt_response_published_in_callback_does_not_block_network_thread():
    from types import SimpleNamespace
    from src.mqtt.client import MqttClient
    waits = []
    result = SimpleNamespace(rc=0, wait_for_publish=lambda **kwargs: waits.append(True))
    client = MqttClient(MqttSettings())
    client._client = SimpleNamespace(publish=lambda *args, **kwargs: result,
                                    subscribe=lambda *args, **kwargs: (0, 1))
    client._connected.set()
    client.subscribe('secado/secador_01/cmd', lambda *_: client.publish('secado/secador_01/ack', '{}'))
    client._on_message(None, None, SimpleNamespace(topic='secado/secador_01/cmd', payload=b'ESTADO', qos=1, retain=False))
    assert waits == []
    client.publish('secado/secador_01/ack', '{}')
    assert waits == [True]
