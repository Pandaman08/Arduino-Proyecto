import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:mqtt_client/mqtt_client.dart';
import 'package:mqtt_client/mqtt_server_client.dart';

import '../../core/config/app_config.dart';
import '../../core/security/credentials.dart';

class WireMessage {
  final String topic, payload;
  final bool retained;
  const WireMessage(this.topic, this.payload, {this.retained = false});
}

abstract interface class MqttTransport {
  Stream<WireMessage> get messages;
  Stream<bool> get connections;
  Stream<String> get subscriptions;
  String get clientId;
  Future<void> connect(Credentials credentials);
  void subscribe(String topic);
  void publish(String topic, String payload);
  Future<void> disconnect();
  Future<void> dispose();
}

/// WSS uses Dart's default trusted certificate chain and hostname validation.
/// Never install an onBadCertificate override or set secure=true (TCP only).
class WssMqttTransport implements MqttTransport {
  @override
  final String clientId;
  MqttServerClient? _client;
  StreamSubscription<dynamic>? _updates;
  final _messages = StreamController<WireMessage>.broadcast();
  final _connections = StreamController<bool>.broadcast();
  final _subscriptions = StreamController<String>.broadcast();
  final String _endpoint;
  final int _port;
  WssMqttTransport(this.clientId)
      : _endpoint = AppConfig.endpoint,
        _port = AppConfig.port;

  @visibleForTesting
  WssMqttTransport.localTest(this.clientId, Uri endpoint)
      : _endpoint = endpoint.toString(),
        _port = endpoint.port {
    if (endpoint.scheme != 'wss' || endpoint.host != 'localhost') {
      throw ArgumentError('Solo WSS local para pruebas');
    }
  }
  @override
  Stream<WireMessage> get messages => _messages.stream;
  @override
  Stream<bool> get connections => _connections.stream;
  @override
  Stream<String> get subscriptions => _subscriptions.stream;
  @override
  Future<void> connect(Credentials credentials) async {
    await disconnect();
    final client = MqttServerClient.withPort(_endpoint, clientId, _port,
        maxConnectionAttempts: 1)
      ..useWebSocket = true
      ..websocketProtocols = ['mqtt']
      ..keepAlivePeriod = AppConfig.keepAlive > 0 ? AppConfig.keepAlive : 60
      ..connectTimeoutPeriod = 10000
      ..connectionTimeout = 10000
      ..autoReconnect = false
      ..setProtocolV311()
      ..logging(on: false);
    _client = client;
    client.connectionMessage =
        MqttConnectMessage().withClientIdentifier(clientId).startClean();
    client.onDisconnected = () {
      if (!_connections.isClosed) _connections.add(false);
    };
    client.onSubscribed = (topic) {
      if (!_subscriptions.isClosed) _subscriptions.add(topic);
    };
    try {
      await client.connect(
        credentials.username.isEmpty ? null : credentials.username,
        credentials.password.isEmpty ? null : credentials.password,
      );
      if (client.connectionStatus?.state != MqttConnectionState.connected) {
        throw StateError('Conexión o autenticación rechazada');
      }
      _updates = client.updates?.listen((batch) {
        for (final item in batch) {
          final message = item.payload;
          if (message is MqttPublishMessage) {
            // Bound input before JSON decoding; malformed payloads are counted by repository.
            final bytes = message.payload.message;
            _messages.add(
              WireMessage(
                item.topic,
                bytes.length > 16384
                    ? ''
                    : MqttPublishPayload.bytesToStringAsString(bytes),
                retained: message.header?.retain ?? false,
              ),
            );
          }
        }
      });
      _connections.add(true);
    } catch (_) {
      client.disconnect();
      rethrow;
    }
  }

  @override
  void subscribe(String topic) {
    if (_client?.subscribe(topic, MqttQos.atLeastOnce) == null) {
      throw StateError('Suscripción rechazada');
    }
  }

  @override
  void publish(String topic, String payload) {
    if (_client?.connectionStatus?.state != MqttConnectionState.connected) {
      throw StateError('Sin conexión');
    }
    _client!.publishMessage(
      topic,
      MqttQos.atLeastOnce,
      (MqttClientPayloadBuilder()..addString(payload)).payload!,
      retain: false,
    );
  }

  @override
  Future<void> disconnect() async {
    await _updates?.cancel();
    _updates = null;
    _client?.onDisconnected = null;
    _client?.disconnect();
    _client = null;
  }

  @override
  Future<void> dispose() async {
    await disconnect();
    await _messages.close();
    await _connections.close();
    await _subscriptions.close();
  }
}
