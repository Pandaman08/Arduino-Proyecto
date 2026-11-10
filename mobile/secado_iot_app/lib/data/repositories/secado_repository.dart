import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:uuid/uuid.dart';

import '../../core/config/app_config.dart';
import '../../core/security/command_policy.dart';
import '../../core/security/credentials.dart';
import '../models/command.dart';
import '../models/telemetry.dart';
import '../mqtt/mqtt_transport.dart';

class SecadoRepository extends ChangeNotifier {
  final MqttTransport transport;
  final CredentialStore credentials;
  final DateTime Function() now;
  final Duration commandTimeout;
  final bool aclVerified;
  final String operatorUser;
  final List<StreamSubscription<dynamic>> _listeners = [];
  final Map<String, List<Telemetry>> _history = {};
  final Map<String, DateTime> _liveReceived = {};
  final Map<String, DateTime> _deviceResponses = {};
  final Map<String, String> nodeStates = {};
  final Set<String> subscribed = {};
  final List<LocalEvent> _events = [];
  final List<CommandRecord> _commands = [];
  final Set<String> _staleNotified = {};
  Timer? _ticker, _retry;
  bool _disposed = false, _wanted = false, _connecting = false;
  int _generation = 0, _attempt = 0;
  bool connected = false, controlEnabled = false;
  String node = AppConfig.nodes.first;
  String status = 'Desconectado', username = '';
  String? lastError;
  DateTime? lastConnection;
  int received = 0, discarded = 0;

  SecadoRepository(
    this.transport,
    this.credentials, {
    DateTime Function()? clock,
    this.commandTimeout = const Duration(seconds: 12),
    this.aclVerified = AppConfig.aclVerified,
    this.operatorUser = AppConfig.operatorUser,
  }) : now = clock ?? DateTime.now {
    _listeners.add(transport.messages.listen(receive));
    _listeners.add(
      transport.connections.listen((online) {
        if (!online && connected) _lost();
      }),
    );
    _listeners.add(
      transport.subscriptions.listen((topic) {
        if (connected) {
          subscribed.add(topic);
          _notify();
        }
      }),
    );
    _ticker = Timer.periodic(const Duration(seconds: 1), (_) => tick());
  }
  List<Telemetry> get history => List.unmodifiable(_history[node] ?? []);
  List<LocalEvent> get events => List.unmodifiable(_events.reversed);
  List<CommandRecord> get commands => List.unmodifiable(_commands.reversed);
  Telemetry? get reading =>
      (_history[node]?.isNotEmpty ?? false) ? _history[node]!.last : null;
  bool get fresh {
    final r = reading;
    final live = _liveReceived[node];
    return r != null &&
        live != null &&
        now().difference(live) <= AppConfig.staleAfter &&
        now().toUtc().difference(r.timestamp) <= AppConfig.staleAfter &&
        !r.timestamp.isAfter(now().toUtc().add(const Duration(seconds: 5)));
  }

  bool get busy => _commands.any((c) => c.active);
  bool get canActivateControl =>
      connected &&
      aclVerified &&
      operatorUser.isNotEmpty &&
      username == operatorUser;
  bool canSend(String command) => CommandPolicy.allowed(
        command: command,
        node: node,
        reading: reading,
        authorized: controlEnabled,
        connected: connected &&
            [
              'telemetria',
              'estado',
              'ack',
            ].every((s) => subscribed.contains(AppConfig.topic(node, s))),
        fresh: fresh,
        busy: busy,
        deviceResponsive: _deviceResponses[node] != null &&
            now().difference(_deviceResponses[node]!) <= AppConfig.staleAfter,
      );

  void selectNode(String value) {
    if (!AppConfig.nodes.contains(value)) {
      throw ArgumentError('Nodo no configurado');
    }
    node = value;
    _notify();
  }

  void activateControl(bool enabled) {
    controlEnabled = enabled && canActivateControl;
    event(
      'Local',
      controlEnabled
          ? 'Control habilitado para cuenta con ACL declarada verificada'
          : 'Modo solo lectura',
    );
    _notify();
  }

  Future<void> saveCredentials(Credentials value) async {
    await disconnect();
    await credentials.save(value);
    event('Local', 'Credenciales guardadas en almacenamiento seguro');
    _notify();
  }

  Future<void> clearCredentials() async {
    await disconnect();
    await credentials.clear();
    username = '';
    event('Local', 'Credenciales eliminadas');
    _notify();
  }

  Future<void> connect() async {
    if (_disposed || _connecting || connected) return;
    _wanted = true;
    _retry?.cancel();
    _connecting = true;
    final generation = ++_generation;
    status = 'Conectando';
    _notify();
    try {
      final secret = await credentials.read();
      if (!_wanted || generation != _generation || _disposed) return;
      username = secret.complete ? secret.username : '';
      // Anonymous connections can monitor only, never unlock control.
      await transport.connect(secret);
      if (!_wanted || generation != _generation || _disposed) {
        await transport.disconnect();
        return;
      }
      connected = true;
      status = 'Conectado';
      lastConnection = now();
      lastError = null;
      _attempt = 0;
      subscribed.clear();
      for (final n in AppConfig.nodes) {
        for (final suffix in ['telemetria', 'estado', 'ack']) {
          transport.subscribe(AppConfig.topic(n, suffix));
        }
      }
      event('Local', 'Conexión WSS establecida; esperando SUBACK de EMQX');
    } catch (_) {
      if (generation != _generation || _disposed) return;
      await transport.disconnect();
      connected = false;
      controlEnabled = false;
      subscribed.clear();
      // Never display raw exceptions: websocket errors can contain authentication material.
      lastError =
          'Conexión fallida: compruebe red, certificado, autenticación y ACL';
      status = 'Error de conexión';
      event('Local', lastError!, critical: true);
      _scheduleRetry();
    } finally {
      _connecting = false;
      _notify();
    }
  }

  void _scheduleRetry() {
    if (!_wanted || _disposed) return;
    _retry?.cancel();
    final seconds = min(60, 1 << min(_attempt++, 6));
    _retry = Timer(Duration(seconds: seconds), connect);
  }

  void _failPending(String detail) {
    for (final c in _commands.where((c) => c.active)) {
      c.stage = CommandStage.error;
      c.detail = detail;
      event('Local', '${c.command}: $detail', critical: true);
    }
  }

  void _lost() {
    connected = false;
    controlEnabled = false;
    _liveReceived.clear();
    _deviceResponses.clear();
    subscribed.clear();
    status = 'Comunicación perdida';
    _failPending('Resultado desconocido tras desconexión; no se reenvía');
    event('Local', 'Pérdida de comunicación MQTT', critical: true);
    _scheduleRetry();
    _notify();
  }

  Future<void> disconnect() async {
    _wanted = false;
    ++_generation;
    _retry?.cancel();
    _retry = null;
    connected = false;
    controlEnabled = false;
    subscribed.clear();
    _liveReceived.clear();
    _deviceResponses.clear();
    _failPending('Desconectado; resultado desconocido');
    await transport.disconnect();
    status = 'Desconectado';
    _notify();
  }

  void receive(WireMessage message) {
    if (!connected || _disposed) return;
    received++;
    try {
      if (message.payload.length > 16384) {
        throw const FormatException('Mensaje demasiado grande');
      }
      final parts = message.topic.split('/');
      if (parts.length != 3 ||
          parts[0] != 'secado' ||
          !AppConfig.nodes.contains(parts[1])) {
        throw const FormatException('Tópico inválido');
      }
      final n = parts[1];
      if (parts[2] == 'telemetria') {
        final value = Telemetry.parse(message.payload, n, now: now());
        final rows = _history.putIfAbsent(n, () => []);
        if (rows.isNotEmpty) {
          final previous = rows.last;
          if (!value.timestamp.isAfter(previous.timestamp) ||
              (previous.sequence != null &&
                  value.sequence != null &&
                  value.sequence == previous.sequence)) {
            throw const FormatException('Lectura duplicada o fuera de orden');
          }
          // A lower sequence with newer timestamp is a node restart, not a duplicate.
          if (previous.sequence != null &&
              value.sequence != null &&
              value.sequence! < previous.sequence!) {
            event(
              'Local',
              '$n: secuencia reiniciada; posible reinicio del nodo',
            );
          }
          if (previous.simulated != value.simulated) {
            rows.clear();
            event('Local', '$n: cambio de origen; historial separado');
          }
        }
        rows.add(value);
        if (rows.length > AppConfig.historyLimit) rows.removeAt(0);
        if (!message.retained) _liveReceived[n] = now();
        _staleNotified.remove(n);
        if (value.grain > 45) {
          event(
            'Local · $n',
            'Temperatura crítica del grano: ${value.grain} °C',
            critical: true,
          );
        }
      } else if (parts[2] == 'ack' || parts[2] == 'estado') {
        final data = jsonDecode(message.payload);
        if (data is! Map<String, dynamic> ||
            (data['node_id'] != null && data['node_id'] != n)) {
          throw const FormatException('Respuesta inválida');
        }
        if (parts[2] == 'estado') {
          if (data['estado'] is! String) {
            throw const FormatException('Estado inválido');
          }
          nodeStates[n] = _safeText(data['estado']);
          event('Puente · $n', nodeStates[n]!);
        } else if (!message.retained) {
          _ack(n, data);
        }
      } else {
        throw const FormatException('Tópico inesperado');
      }
    } catch (_) {
      discarded++;
      event('Local', 'Lectura o mensaje inválido descartado', critical: true);
    }
    _notify();
  }

  String _safeText(Object? value) {
    const known = {
      'online',
      'offline',
      'ready',
      'ACK:PARAR_APLICADO',
      'ACK:MODO_MONITOREO_APLICADO',
      'ACK:MODO_CONTROL_APLICADO',
      'ACK:ACTUADOR_FIJO_APLICADO',
      'ACK:SP_ACEPTADO_SIN_CAMBIO_ACTUADORES',
      'ACK:SP_APLICADO_CONTROL',
      'ACK:VENT_FIJO_APLICADO',
      'ACK:LCD_APLICADO',
      'ACK:ESTADO_CONSULTADO',
      'ERR:REQUEST_ID_INVALIDO',
      'ERR:SP_FUERA_DE_RANGO',
      'ERR:VENT_SOLO_MONITOREO',
      'ERR:VENT_FUERA_DE_RANGO',
      'ERR:COMANDO_INVALIDO',
      'ERR:SENSOR_DHT',
      'ERR:SENSOR_DS18B20',
      'ERR:WATCHDOG_CONTROL',
      'ERR:COMANDO_DEMASIADO_LARGO',
    };
    if (value is String && known.contains(value.trim())) {
      return value.trim();
    }
    if (value is String &&
        RegExp(r'^ESTADO,modo=(MONITOREO|CONTROL),activo=[01],sp=\d{1,2}\.\d,foco=(NA|0|1),vent=\d{1,3},seq=\d{1,10}$')
            .hasMatch(value)) {
      return value;
    }
    return 'Evento recibido (contenido omitido)';
  }

  void _ack(String n, Map<String, dynamic> data) {
    if (data['accepted'] is! bool || data['message'] is! String) {
      throw const FormatException('ACK inválido');
    }
    final text = data['message'] as String;
    final firmware = text.startsWith('ACK:') || text.startsWith('ERR:');
    final correlated =
        firmware && data['source'] == 'firmware' && data['correlated'] == true;
    if (firmware &&
        ((text.startsWith('ACK:') && data['accepted'] != true) ||
            (text.startsWith('ERR:') && data['accepted'] != false))) {
      throw const FormatException('Confirmación inconsistente');
    }
    event(
      '${firmware ? 'Firmware' : 'Puente'} · $n',
      firmware
          ? '${_safeText(text)} · ${correlated ? 'respuesta correlacionada' : 'sin correlación garantizada'}'
          : 'Respuesta de envío del puente',
      critical: data['accepted'] == false,
    );
    final id = data['request_id'];
    final matching = _commands.where(
      (c) => c.active && c.node == n && c.id == id,
    );
    if (matching.isEmpty) return;
    final command = matching.first;
    if (firmware && (!correlated || data['command'] != command.command)) {
      return;
    }
    if (data['accepted'] == false) {
      command.stage = CommandStage.rejected;
      command.detail = 'Rechazado por ${firmware ? 'firmware' : 'puente'}';
    } else if (correlated && data['phase'] == 'applied') {
      _deviceResponses[n] = now();
      command.stage = CommandStage.confirmed;
      command.detail =
          'El Arduino confirmó el procesamiento de este comando. La actuación física requiere verificación del montaje.';
      if (command.command.startsWith('MODO:')) {
        event('Firmware · $n',
            'Cambio de modo confirmado: ${command.command.substring(5)}');
      }
    } else if (!firmware) {
      command.stage = CommandStage.bridgeAccepted;
      command.detail =
          'Enviado al Arduino. Esperando respuesta correlacionada del firmware.';
    }
    // Legacy ACKs, unrelated IDs and telemetry never confirm a transaction.
  }

  CommandRecord send(String command) {
    if (!canSend(command)) {
      throw StateError(
        'Control bloqueado: permisos, conexión, modo o telemetría',
      );
    }
    final record = CommandRecord(const Uuid().v4(), node, command, now());
    _commands.add(record);
    if (_commands.length > 100) _commands.removeAt(0);
    _notify();
    try {
      transport.publish(
        AppConfig.topic(node, 'cmd'),
        jsonEncode({'command': command, 'request_id': record.id}),
      );
      record.stage = CommandStage.published;
      record.detail =
          'Esperando aceptación del puente; publicación no prueba ejecución';
      event('Local', '$node · $command · Publicado · ${record.id}');
    } catch (_) {
      record.stage = CommandStage.error;
      record.detail = 'Error de publicación; no se reenvía';
      event('Local', record.detail, critical: true);
    }
    _notify();
    return record;
  }

  void tick() {
    if (_disposed) return;
    for (final c in _commands.where((c) => c.active)) {
      if (now().difference(c.created) >= commandTimeout) {
        c.stage = CommandStage.timeout;
        c.detail =
            'Sin confirmación correlacionada del Arduino; ejecución desconocida';
        event(
          'Local',
          '${c.command}: tiempo de espera agotado',
          critical: true,
        );
      }
    }
    if (reading != null && !fresh && _staleNotified.add(node)) {
      event('Local · $node', 'Telemetría desactualizada', critical: true);
    }
    _notify();
  }

  void event(String source, String message, {bool critical = false}) {
    _events.add(LocalEvent(now(), source, message, critical: critical));
    if (_events.length > AppConfig.eventLimit) _events.removeAt(0);
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    _wanted = false;
    ++_generation;
    _ticker?.cancel();
    _retry?.cancel();
    for (final listener in _listeners) {
      unawaited(listener.cancel());
    }
    unawaited(transport.dispose());
    super.dispose();
  }
}
