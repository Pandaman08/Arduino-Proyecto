"""Executes the actual sketch's command handler on host IO doubles; no hardware."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest
from src.mqtt.bridge import SerialMqttBridge


@pytest.fixture(scope='module')
def firmware_binary(tmp_path_factory):
    compiler = shutil.which('g++')
    if compiler is None:
        pytest.skip('g++ is required for native firmware behavior tests')
    root = Path(__file__).resolve().parent
    output = tmp_path_factory.mktemp('firmware') / 'firmware-test'
    subprocess.run([compiler, '-std=c++17', '-I', str(root / 'firmware_stubs'),
                    str(root / 'firmware_stubs/harness.cpp'), '-o', str(output)], check=True, capture_output=True)
    return output


def test_actual_firmware_echoes_id_preserves_legacy_and_does_not_tag_sensor_errors(firmware_binary):
    commands = ['MODO:MONITOREO', 'REQ,mobile-1,MODO:CONTROL', 'REQ,fan-2,VENT:100',
                'REQ,status-3,ESTADO', 'REQ,range-4,SP:51', 'REQ,bad/id,PARAR',
                'X'*96+'PARAR', 'REQ,final,ESTADO', 'TEST:SENSOR_ERR']
    result = subprocess.run([firmware_binary], input='\n'.join(commands)+'\n', text=True, capture_output=True, check=True)
    lines = result.stdout.splitlines()
    assert lines[0] == 'ACK:MODO_MONITOREO_APLICADO'
    assert 'ACK:MODO_CONTROL_APLICADO|request_id=mobile-1' in lines
    assert 'ERR:VENT_SOLO_MONITOREO|request_id=fan-2' in lines
    assert 'ACK:ESTADO_CONSULTADO|request_id=status-3' in lines
    assert 'ERR:SP_FUERA_DE_RANGO|request_id=range-4' in lines
    assert 'ERR:REQUEST_ID_INVALIDO' in lines
    assert 'ERR:COMANDO_DEMASIADO_LARGO' in lines
    assert 'ACK:PARAR_APLICADO' not in result.stdout
    assert sum(line.startswith('ESTADO,modo=CONTROL,activo=1') for line in lines) == 2
    assert lines[-1] == 'ERR:SENSOR_DHT'


def test_bridge_to_actual_firmware_to_correlated_mqtt_ack(firmware_binary):
    class SerialHarness:
        def __init__(self):
            self.process = subprocess.Popen([firmware_binary], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        def is_open(self): return True
        def send_command(self, command):
            self.process.stdin.write(command+'\n')
            self.process.stdin.flush()
        def read_line(self): return self.process.stdout.readline().strip()
    class MqttSink:
        def __init__(self): self.messages = []
        def publish(self, topic, payload, **kwargs): self.messages.append(json.loads(payload))
    port, mqtt = SerialHarness(), MqttSink()
    try:
        bridge = SerialMqttBridge(port, mqtt, 'secador_01')
        bridge._on_command(bridge.topics.command, b'{"command":"MODO:CONTROL","request_id":"phone-original-id"}', 1, False)
        assert mqtt.messages[-1]['source'] == 'bridge'
        bridge.run_once()
        ack = mqtt.messages[-1]
        assert (ack['request_id'], ack['command'], ack['phase'], ack['correlated']) == ('phone-original-id', 'MODO:CONTROL', 'applied', True)
    finally:
        port.process.stdin.close()
        port.process.wait(timeout=3)
        port.process.stdout.close()
