import 'dart:async';
import 'dart:convert';

import 'package:secado_iot_app/core/config/app_config.dart';
import 'package:secado_iot_app/core/security/credentials.dart';
import 'package:secado_iot_app/data/mqtt/mqtt_transport.dart';

class MemoryCredentials implements CredentialStore {
  Credentials value = const Credentials('operador-test', 'password-test');
  @override
  Future<Credentials> read() async => value;
  @override
  Future<void> save(Credentials credentials) async {
    value = credentials;
  }

  @override
  Future<void> clear() async {
    value = const Credentials('', '');
  }
}

class FakeTransport implements MqttTransport {
  final frames = StreamController<WireMessage>.broadcast(sync: true);
  final online = StreamController<bool>.broadcast(sync: true);
  final subs = StreamController<String>.broadcast(sync: true);
  final List<String> topics = [], sent = [];
  int attempts = 0;
  Object? failure;
  @override
  String get clientId => 'test-mobile';
  @override
  Stream<WireMessage> get messages => frames.stream;
  @override
  Stream<bool> get connections => online.stream;
  @override
  Stream<String> get subscriptions => subs.stream;
  @override
  Future<void> connect(Credentials credentials) async {
    attempts++;
    if (failure != null) throw failure!;
  }

  @override
  void subscribe(String topic) {
    topics.add(topic);
    subs.add(topic);
  }

  @override
  void publish(String topic, String payload) {
    sent.add('$topic|$payload');
  }

  @override
  Future<void> disconnect() async {}
  @override
  Future<void> dispose() async {
    await frames.close();
    await online.close();
    await subs.close();
  }
}

Map<String, dynamic> telemetry(
  DateTime time, {
  String node = 'secador_01',
  int sequence = 1,
}) =>
    {
      'node_id': node,
      'timestamp': time.toUtc().toIso8601String(),
      'sequence': sequence,
      't_amb': 28.5,
      'hum': 65.0,
      't_grano': 32.2,
      'simulado': node.startsWith('sim'),
      'modo': node.startsWith('sim') ? 'simulacion' : 'MONITOREO',
      'sp': 30.0,
      'vent': 150,
    };
WireMessage frame(
  DateTime time, {
  String node = 'secador_01',
  int sequence = 1,
}) =>
    WireMessage(
      AppConfig.topic(node, 'telemetria'),
      jsonEncode(telemetry(time, node: node, sequence: sequence)),
    );
