import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:secado_iot_app/data/models/telemetry.dart';

import 'fakes.dart';

void main() {
  final time = DateTime.utc(2026, 11, 10, 10);
  Telemetry parse(Map<String, dynamic> map) =>
      Telemetry.parse(jsonEncode(map), 'secador_01', now: time);
  test('parseo y campos ausentes no inventados', () {
    final map = telemetry(time)
      ..remove('sp')
      ..remove('vent')
      ..remove('modo')
      ..remove('sequence');
    final r = parse(map);
    expect(r.ambient, 28.5);
    expect(r.fan, isNull);
    expect(r.setpoint, isNull);
    expect(r.mode, isNull);
    expect(r.sequence, isNull);
    expect(r.heater, isNull);
  });
  test('aliases reales del proyecto', () {
    final r = parse({
      'id': 'secador_01',
      'ts': time.toIso8601String(),
      'seq': 3,
      't_amb': 24,
      'hum': 60,
      't_grano': 30,
      't_ideal': 31,
      'ventilador_pwm': 100,
      'led': 'NA',
    });
    expect(r.setpoint, 31);
    expect(r.fan, 100);
    expect(r.sequence, 3);
    expect(r.heater, isNull);
  });
  test('JSON corrupto y tipo raíz', () {
    for (final raw in ['{', '[]', 'null']) {
      expect(() => Telemetry.parse(raw, 'secador_01'), throwsFormatException);
    }
  });
  for (final change in <Map<String, dynamic>>[
    {'t_amb': 81},
    {'t_grano': -11},
    {'hum': 101},
    {'hum': '65'},
    {'sequence': 1.2},
    {'sp': 51},
    {'vent': 256},
    {'simulado': 'false'},
    {'modo': 1},
    {'timestamp': 'ayer'},
    {'timestamp': '2026-02-30T10:00:00Z'},
    {'timestamp': '2026-11-10T25:00:00Z'},
    {'timestamp': '2026-11-10T10:00:00'},
    {'timestamp': '2026-11-11T10:00:00Z'},
    {'node_id': 'otro'},
  ]) {
    test('rechaza campo inválido $change', () {
      expect(
        () => parse(telemetry(time)..addAll(change)),
        throwsFormatException,
      );
    });
  }
  test('origen simulado explícito y consistencia', () {
    expect(
      Telemetry.parse(
        jsonEncode(telemetry(time, node: 'sim1')),
        'sim1',
        now: time,
      ).simulated,
      true,
    );
    expect(
      () => Telemetry.parse(
        jsonEncode(telemetry(time, node: 'sim1')..['simulado'] = false),
        'sim1',
        now: time,
      ),
      throwsFormatException,
    );
  });
}
