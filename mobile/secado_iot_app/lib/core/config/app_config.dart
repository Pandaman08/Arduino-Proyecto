/// Public deployment settings only. Secrets are entered on the device.
abstract final class AppConfig {
  static const host = 'cafes.duckdns.org';
  static const port = 443;
  static const path = '/mqtt';
  static const endpoint = 'wss://$host$path';
  static const keepAlive = int.fromEnvironment(
    'MQTT_KEEPALIVE',
    defaultValue: 60,
  );
  // Enable only AFTER the administrator verifies this user's broker ACL.
  // This build gate is defense in depth; EMQX must enforce authorization.
  static const operatorUser = String.fromEnvironment('MQTT_OPERATOR_USER');
  static const aclVerified = bool.fromEnvironment('MQTT_ACL_VERIFIED');
  static const physicalNodes = ['secador_01'];
  static const simulatedNodes = ['sim1', 'sim2', 'sim3', 'sim4'];
  static const nodes = [...physicalNodes, ...simulatedNodes];
  static const historyLimit = 300;
  static const eventLimit = 200;
  static const staleAfter = Duration(seconds: 15);
  static String topic(String node, String suffix) {
    if (!nodes.contains(node) ||
        !['telemetria', 'estado', 'ack', 'cmd'].contains(suffix)) {
      throw ArgumentError('Tópico no autorizado');
    }
    return 'secado/$node/$suffix';
  }
}
