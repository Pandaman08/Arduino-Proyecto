import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:secado_iot_app/core/security/command_policy.dart';
import 'package:secado_iot_app/data/models/command.dart';
import 'package:secado_iot_app/data/mqtt/mqtt_transport.dart';
import 'package:secado_iot_app/data/repositories/secado_repository.dart';

import 'fakes.dart';

void main() {
  late FakeTransport wire;
  late SecadoRepository repo;
  late DateTime clock;
  setUp(() {
    clock = DateTime.utc(2026, 11, 10, 10);
    wire = FakeTransport();
    repo = SecadoRepository(
      wire,
      MemoryCredentials(),
      clock: () => clock,
      aclVerified: true,
      operatorUser: 'operador-test',
    );
  });
  tearDown(() => repo.dispose());
  Future<void> operator() async {
    await repo.connect();
    repo.receive(frame(clock));
    repo.activateControl(true);
  }

  test('conexión, suscripciones exactas y solo lectura inicial', () async {
    await repo.connect();
    expect(repo.connected, true);
    expect(repo.controlEnabled, false);
    expect(wire.topics.length, 15);
    expect(wire.topics, contains('secado/secador_01/ack'));
    expect(wire.topics.any((t) => t.endsWith('/cmd')), false);
    await repo.disconnect();
    expect(repo.connected, false);
  });
  test('autenticación rechazada y error sanitizado', () async {
    wire.failure = StateError('password-test');
    await repo.connect();
    expect(repo.connected, false);
    expect(repo.lastError, isNot(contains('password-test')));
    expect(repo.canSend('PARAR'), false);
  });
  test('recuperación, sin reenvío y control revocado', () async {
    await operator();
    final c = repo.send('SP:30.0');
    wire.online.add(false);
    expect(c.stage, CommandStage.error);
    expect(repo.controlEnabled, false);
    await repo.connect();
    expect(repo.connected, true);
    expect(wire.sent.length, 1);
    expect(repo.canSend('PARAR'), false);
  });
  test('lista blanca y límites', () {
    for (final c in [
      'SP:10',
      'SP:50.0',
      'VENT:0',
      'VENT:255',
      'ESTADO',
      'PARAR',
      'MODO:CONTROL',
    ]) {
      expect(CommandPolicy.valid(c), true);
    }
    for (final c in [
      'SP:51',
      'SP:9.9',
      'SP:NaN',
      'VENT:256',
      'VENT:-1',
      'VENT:1.5',
      'D:hola',
      'MODO:CONTROL\nPARAR',
    ]) {
      expect(CommandPolicy.valid(c), false);
    }
  });
  test('bloqueo sin autorización y en simulación', () async {
    await repo.connect();
    repo.receive(frame(clock));
    expect(() => repo.send('PARAR'), throwsStateError);
    repo.activateControl(true);
    repo.selectNode('sim1');
    repo.receive(frame(clock, node: 'sim1'));
    expect(() => repo.send('PARAR'), throwsStateError);
    expect(wire.sent, isEmpty);
  });
  test('PWM bloqueado por modo reportado', () async {
    await operator();
    repo.receive(
      WireMessage(
        'secado/secador_01/telemetria',
        jsonEncode(
          telemetry(clock.add(const Duration(seconds: 1)), sequence: 2)
            ..['modo'] = 'CONTROL',
        ),
      ),
    );
    expect(repo.canSend('VENT:150'), false);
    expect(repo.canSend('SP:30.0'), true);
  });
  test(
    'publicación, duplicación, aceptación no es confirmación y timeout',
    () async {
      await operator();
      final c = repo.send('MODO:CONTROL');
      expect(c.stage, CommandStage.published);
      expect(() => repo.send('PARAR'), throwsStateError);
      repo.receive(
        WireMessage(
          'secado/secador_01/ack',
          jsonEncode({
            'accepted': true,
            'request_id': c.id,
            'message': 'comando enviado al Arduino',
          }),
        ),
      );
      expect(c.stage, CommandStage.bridgeAccepted);
      repo.receive(
        const WireMessage(
          'secado/secador_01/ack',
          '{"accepted":true,"message":"ACK:MODO_CONTROL_APLICADO"}',
        ),
      );
      expect(c.stage, CommandStage.bridgeAccepted);
      clock = clock.add(const Duration(seconds: 13));
      repo.tick();
      expect(c.stage, CommandStage.timeout);
      expect(wire.sent.length, 1);
    },
  );
  test('rechazo correlacionado y ACK retenido ignorado', () async {
    await operator();
    final c = repo.send('PARAR');
    final payload = jsonEncode({
      'accepted': false,
      'request_id': c.id,
      'message': 'rechazado',
    });
    repo.receive(WireMessage('secado/secador_01/ack', payload, retained: true));
    expect(c.stage, CommandStage.published);
    repo.receive(WireMessage('secado/secador_01/ack', payload));
    expect(c.stage, CommandStage.rejected);
  });
  test('duplicados, secuencia reiniciada y lecturas antiguas', () async {
    await operator();
    repo.receive(frame(clock));
    expect(repo.discarded, 1);
    clock = clock.add(const Duration(seconds: 2));
    repo.receive(frame(clock, sequence: 0));
    expect(repo.history.length, 2);
    clock = clock.add(const Duration(seconds: 20));
    repo.tick();
    expect(repo.fresh, false);
    expect(repo.canSend('SP:30.0'), false);
    expect(repo.canSend('PARAR'), true);
    expect(repo.events.any((e) => e.message.contains('desactualizada')), true);
  });
  test('retained no habilita control', () async {
    await repo.connect();
    repo.activateControl(true);
    repo.receive(
      WireMessage(
        'secado/secador_01/telemetria',
        jsonEncode(telemetry(clock)),
        retained: true,
      ),
    );
    expect(repo.fresh, false);
    expect(repo.canSend('SP:30.0'), false);
    expect(repo.canSend('ESTADO'), true);
  });
  test('memoria acotada y alerta local', () async {
    await repo.connect();
    for (var i = 0; i < 310; i++) {
      clock = clock.add(const Duration(seconds: 1));
      repo.receive(
        WireMessage(
          'secado/secador_01/telemetria',
          jsonEncode(telemetry(clock, sequence: i)..['t_grano'] = 46),
        ),
      );
    }
    expect(repo.history.length, 300);
    expect(repo.events.length, 200);
    expect(repo.events.first.source, contains('Local'));
  });
  test('reconexión automática con backoff y cancelación al desconectar',
      () async {
    await repo.connect();
    wire.online.add(false);
    await Future<void>.delayed(const Duration(milliseconds: 1150));
    expect(wire.attempts, 2);
    expect(repo.connected, true);
    wire.online.add(false);
    await repo.disconnect();
    await Future<void>.delayed(const Duration(milliseconds: 1150));
    expect(wire.attempts, 2);
  });
  test('cuenta sin ACL verificada no habilita control', () async {
    final monitor = SecadoRepository(FakeTransport(), MemoryCredentials());
    try {
      await monitor.connect();
      monitor.activateControl(true);
      expect(monitor.controlEnabled, false);
    } finally {
      monitor.dispose();
    }
  });
  test(
      'confirmación de Arduino correlacionada, sin degradación por envío tardío',
      () async {
    await operator();
    final c = repo.send('MODO:CONTROL');
    repo.receive(WireMessage(
        'secado/secador_01/ack',
        jsonEncode({
          'accepted': true,
          'request_id': c.id,
          'command': c.command,
          'message': 'ACK:MODO_CONTROL_APLICADO',
          'source': 'firmware',
          'correlated': true,
          'phase': 'applied',
        })));
    expect(c.stage, CommandStage.confirmed);
    repo.receive(WireMessage(
        'secado/secador_01/ack',
        jsonEncode({
          'accepted': true,
          'request_id': c.id,
          'message': 'comando enviado al Arduino',
          'source': 'bridge',
          'phase': 'forwarded',
        })));
    expect(c.stage, CommandStage.confirmed);
    expect(
        repo.events.any((e) => e.message.contains('Cambio de modo confirmado')),
        true);
  });
  test('ID ajeno, comando distinto y ACK legado no confirman', () async {
    await operator();
    final c = repo.send('SP:30.0');
    for (final change in [
      {'request_id': 'otra-solicitud'},
      {'command': 'SP:31.0'},
      {'correlated': false},
    ]) {
      repo.receive(WireMessage(
          'secado/secador_01/ack',
          jsonEncode({
            'accepted': true,
            'request_id': c.id,
            'command': c.command,
            'message': 'ACK:SP_APLICADO_CONTROL',
            'source': 'firmware',
            'correlated': true,
            'phase': 'applied',
            ...change,
          })));
      expect(c.stage, CommandStage.published);
    }
  });
  test('ERR correlacionado rechaza; una confirmación vencida no altera timeout',
      () async {
    await operator();
    final c = repo.send('VENT:100');
    repo.receive(WireMessage(
        'secado/secador_01/ack',
        jsonEncode({
          'accepted': false,
          'request_id': c.id,
          'command': c.command,
          'message': 'ERR:VENT_SOLO_MONITOREO',
          'source': 'firmware',
          'correlated': true,
          'phase': 'rejected',
        })));
    expect(c.stage, CommandStage.rejected);
    final next = repo.send('ESTADO');
    clock = clock.add(const Duration(seconds: 13));
    repo.tick();
    repo.receive(WireMessage(
        'secado/secador_01/ack',
        jsonEncode({
          'accepted': true,
          'request_id': next.id,
          'command': next.command,
          'message': 'ACK:ESTADO_CONSULTADO',
          'source': 'firmware',
          'correlated': true,
          'phase': 'applied',
        })));
    expect(next.stage, CommandStage.timeout);
  });
  test(
      'arranque sin telemetría requiere consulta correlacionada del dispositivo',
      () async {
    await repo.connect();
    repo.activateControl(true);
    expect(repo.canSend('MODO:MONITOREO'), false);
    expect(repo.canSend('SP:30.0'), false);
    expect(repo.canSend('PARAR'), true);
    final c = repo.send('ESTADO');
    repo.receive(WireMessage(
        'secado/secador_01/ack',
        jsonEncode({
          'accepted': true,
          'request_id': c.id,
          'command': 'ESTADO',
          'message': 'ACK:ESTADO_CONSULTADO',
          'source': 'firmware',
          'correlated': true,
          'phase': 'applied',
        })));
    expect(repo.canSend('MODO:MONITOREO'), true);
    expect(repo.canSend('VENT:100'), false);
    await repo.disconnect();
    await repo.connect();
    repo.activateControl(true);
    expect(repo.canSend('MODO:MONITOREO'), false);
  });
}
