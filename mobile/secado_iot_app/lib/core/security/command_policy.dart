import '../config/app_config.dart';
import '../../data/models/telemetry.dart';

abstract final class CommandPolicy {
  static bool valid(String command) {
    if (['MODO:MONITOREO', 'MODO:CONTROL', 'PARAR', 'ESTADO']
        .contains(command)) {
      return true;
    }
    if (RegExp(r'^SP:\d{1,2}(\.\d)?$').hasMatch(command)) {
      final n = double.parse(command.substring(3));
      return n >= 10 && n <= 50;
    }
    if (RegExp(r'^VENT:\d{1,3}$').hasMatch(command)) {
      return int.parse(command.substring(5)) <= 255;
    }
    return false;
  }

  static bool allowed({
    required String command,
    required String node,
    required Telemetry? reading,
    required bool authorized,
    required bool connected,
    required bool fresh,
    required bool busy,
  }) {
    return valid(command) &&
        authorized &&
        connected &&
        !busy &&
        fresh &&
        AppConfig.physicalNodes.contains(node) &&
        reading != null &&
        reading.node == node &&
        !reading.simulated &&
        (!command.startsWith('VENT:') || reading.mode == 'MONITOREO');
  }
}
