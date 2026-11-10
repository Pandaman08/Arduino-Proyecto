import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:secado_iot_app/core/security/credentials.dart';
import 'package:secado_iot_app/data/mqtt/mqtt_transport.dart';

/// Minimal MQTT 3.1.1 wire fixture, bound to loopback only. No production broker.
class LocalBroker {
  final HttpServer server;
  final bool rejectAuth;
  final List<List<int>> packets = [];
  final List<WebSocket> sockets = [];
  LocalBroker(this.server, this.rejectAuth);
  Uri get endpoint => Uri.parse('wss://localhost:${server.port}/mqtt');
  static Future<LocalBroker> start(
      {bool rejectAuth = false, String fixture = 'localhost'}) async {
    final tls = SecurityContext()
      ..useCertificateChain('test/fixtures/$fixture-cert.pem')
      ..usePrivateKey('test/fixtures/$fixture-key.pem');
    final server =
        await HttpServer.bindSecure(InternetAddress.loopbackIPv4, 0, tls);
    final broker = LocalBroker(server, rejectAuth);
    server.listen((request) async {
      try {
        final socket = await WebSocketTransformer.upgrade(request,
            protocolSelector: (protocols) =>
                protocols.contains('mqtt') ? 'mqtt' : null);
        broker.sockets.add(socket);
        socket.listen((dynamic event) {
          final data = List<int>.from(event as List);
          broker.packets.add(data);
          var offset = 1, remaining = 0, multiplier = 1, digit = 0;
          do {
            digit = data[offset++];
            remaining += (digit & 127) * multiplier;
            multiplier *= 128;
          } while ((digit & 128) != 0);
          final body = data.sublist(offset, offset + remaining);
          switch (data[0] >> 4) {
            case 1:
              socket.add([0x20, 2, 0, rejectAuth ? 5 : 0]);
            case 8:
              socket.add([0x90, 3, body[0], body[1], 1]);
            case 3:
              final length = body[0] * 256 + body[1];
              socket.add([0x40, 2, body[length + 2], body[length + 3]]);
            case 12:
              socket.add([0xd0, 0]);
          }
        }, onError: (Object _) {});
      } catch (_) {/* TLS failure is expected in the negative test. */}
    });
    return broker;
  }

  Future<void> close() async {
    for (final socket in sockets) {
      await socket.close();
    }
    await server.close(force: true);
  }
}

class TrustedFixtureHttp extends HttpOverrides {
  final SecurityContext trust;
  TrustedFixtureHttp(this.trust);
  @override
  HttpClient createHttpClient(SecurityContext? context) =>
      super.createHttpClient(trust);
}

void main() {
  // These are real IO tests; ensure widget binding doesn't replace HttpClient.
  test('rechaza certificado autofirmado sin desactivar TLS', () async {
    final broker = await LocalBroker.start();
    final wire = WssMqttTransport.localTest('tls-negative', broker.endpoint);
    try {
      await expectLater(
          wire.connect(const Credentials('', '')), throwsA(anything));
      expect(broker.packets, isEmpty);
    } finally {
      await wire.dispose();
      await broker.close();
    }
  });

  test('rechaza hostname incorrecto aunque la CA sea confiable', () async {
    final broker = await LocalBroker.start(fixture: 'wrong-host');
    final wire =
        WssMqttTransport.localTest('hostname-negative', broker.endpoint);
    final context = SecurityContext(withTrustedRoots: true)
      ..setTrustedCertificates('test/fixtures/wrong-host-cert.pem');
    try {
      await HttpOverrides.runWithHttpOverrides(() async {
        await expectLater(
            wire.connect(const Credentials('', '')), throwsA(anything));
      }, TrustedFixtureHttp(context));
      expect(broker.packets, isEmpty);
    } finally {
      await wire.dispose();
      await broker.close();
    }
  });

  Future<void> trusted(Future<void> Function() action) {
    final context = SecurityContext(withTrustedRoots: true)
      ..setTrustedCertificates('test/fixtures/localhost-cert.pem');
    return HttpOverrides.runWithHttpOverrides(
        action, TrustedFixtureHttp(context));
  }

  test('WSS MQTT 3.1.1, SUBACK, telemetría y publicación QoS1 sin retain',
      () async {
    final broker = await LocalBroker.start();
    final wire = WssMqttTransport.localTest('positive-local', broker.endpoint);
    try {
      await trusted(() async {
        await wire.connect(const Credentials('fixture', 'fixture'));
        final subscribed = wire.subscriptions.first;
        wire.subscribe('secado/secador_01/telemetria');
        expect(await subscribed.timeout(const Duration(seconds: 3)),
            'secado/secador_01/telemetria');
        final incoming = wire.messages.first;
        final topic = utf8.encode('secado/secador_01/telemetria');
        final payload = utf8.encode('{"t_grano":32.2}');
        final body = [0, topic.length, ...topic, ...payload];
        broker.sockets.last.add([0x30, body.length, ...body]);
        expect((await incoming.timeout(const Duration(seconds: 3))).payload,
            '{"t_grano":32.2}');
        wire.publish('secado/secador_01/cmd',
            '{"command":"ESTADO","request_id":"fixture"}');
        await Future<void>.delayed(const Duration(milliseconds: 80));
        final packet = broker.packets.firstWhere((p) => p[0] >> 4 == 3);
        expect(packet[0] & 1, 0);
        expect((packet[0] >> 1) & 3, 1);
        final connect = broker.packets.first;
        expect(connect, containsAllInOrder([77, 81, 84, 84, 4]));
        await wire.disconnect();
      });
    } finally {
      await wire.dispose();
      await broker.close();
    }
  });
  test('rechazo real CONNACK de autenticación', () async {
    final broker = await LocalBroker.start(rejectAuth: true);
    final wire = WssMqttTransport.localTest('auth-negative', broker.endpoint);
    try {
      await trusted(() async {
        await expectLater(
            wire.connect(const Credentials('bad', 'bad')), throwsA(anything));
      });
      expect(broker.packets.first[0] >> 4, 1);
    } finally {
      await wire.dispose();
      await broker.close();
    }
  });
}
