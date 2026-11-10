import 'dart:convert';

import '../../core/config/app_config.dart';

class Telemetry {
  final String node;
  final DateTime timestamp;
  final int? sequence;
  final double ambient, humidity, grain;
  final double? setpoint;
  final int? fan;
  final String? mode, heater, version;
  final bool simulated;
  const Telemetry({
    required this.node,
    required this.timestamp,
    required this.sequence,
    required this.ambient,
    required this.humidity,
    required this.grain,
    required this.simulated,
    this.setpoint,
    this.fan,
    this.mode,
    this.heater,
    this.version,
  });

  factory Telemetry.parse(String raw, String topicNode, {DateTime? now}) {
    final map = jsonDecode(raw);
    if (map is! Map<String, dynamic>) {
      throw const FormatException('Objeto requerido');
    }
    final node = map['node_id'] ?? map['id'];
    if (node != topicNode || !AppConfig.nodes.contains(node)) {
      throw const FormatException('Nodo incompatible con tópico');
    }
    final ts = map['timestamp'] ?? map['ts'];
    if (ts is! String || !RegExp(r'(Z|[+-]\d{2}:\d{2})$').hasMatch(ts)) {
      throw const FormatException('Timestamp sin zona horaria');
    }
    final match = RegExp(
            r'^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,9})?(Z|[+-](\d{2}):(\d{2}))$')
        .firstMatch(ts);
    if (match == null) {
      throw const FormatException('Timestamp ISO-8601 inválido');
    }
    final year = int.parse(match[1]!),
        month = int.parse(match[2]!),
        day = int.parse(match[3]!);
    final date = DateTime.utc(year, month, day);
    if (date.year != year ||
        date.month != month ||
        date.day != day ||
        int.parse(match[4]!) > 23 ||
        int.parse(match[5]!) > 59 ||
        int.parse(match[6]!) > 59 ||
        (match[8] != null &&
            (int.parse(match[8]!) > 23 || int.parse(match[9]!) > 59))) {
      throw const FormatException('Fecha u hora fuera de rango');
    }
    final time = DateTime.tryParse(ts)?.toUtc();
    if (time == null ||
        time.isAfter(
          (now ?? DateTime.now()).toUtc().add(const Duration(minutes: 2)),
        )) {
      throw const FormatException('Timestamp inválido o futuro');
    }
    double number(String key, double low, double high, [Object? alias]) {
      final value = map[key] ?? alias;
      if (value is! num || !value.isFinite || value < low || value > high) {
        throw FormatException('Rango o tipo inválido: $key');
      }
      return value.toDouble();
    }

    int? integer(Object? value, int max) {
      if (value == null) return null;
      if (value is! int || value < 0 || value > max) {
        throw const FormatException('Entero inválido');
      }
      return value;
    }

    final sim = map['simulado'] ?? AppConfig.simulatedNodes.contains(node);
    if (sim is! bool || (AppConfig.simulatedNodes.contains(node) && !sim)) {
      throw const FormatException('Origen inválido');
    }
    final mode = map['modo'];
    if (mode != null &&
        (mode is! String ||
            !['MONITOREO', 'CONTROL', 'simulacion'].contains(mode))) {
      throw const FormatException('Modo inválido');
    }
    final heater = map['foco'] ?? map['led'];
    if (heater != null && (heater is! String || heater.length > 32)) {
      throw const FormatException('Estado calefactor inválido');
    }
    final version = map['version'];
    if (version != null && (version is! String || version.length > 24)) {
      throw const FormatException('Versión inválida');
    }
    return Telemetry(
      node: node,
      timestamp: time,
      sequence: integer(map['sequence'] ?? map['seq'], 0x7fffffffffffffff),
      ambient: number('t_amb', -10, 80),
      humidity: number('hum', 0, 100),
      grain: number('t_grano', -10, 85),
      simulated: sim,
      setpoint: (map['sp'] ?? map['t_ideal']) == null
          ? null
          : number('sp', 10, 50, map['t_ideal']),
      fan: integer(map['vent'] ?? map['ventilador_pwm'], 255),
      mode: mode,
      heater: heater == 'NA' ? null : heater,
      version: version,
    );
  }
}
