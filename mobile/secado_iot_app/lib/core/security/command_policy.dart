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
    bool deviceResponsive = false,
  }) {
    if (!valid(command) ||
        !authorized ||
        !connected ||
        busy ||
        !AppConfig.physicalNodes.contains(node) ||
        reading?.simulated == true ||
        (reading != null && reading.node != node)) {
      return false;
    }
    // Status and safe stop must work when telemetry is off. Startup requires
    // a fresh, correlated response from this Arduino before enabling a mode.
    if (command == 'ESTADO' || command == 'PARAR') {
      return true;
    }
    if (command.startsWith('MODO:') && deviceResponsive) {
      return true;
    }
    return fresh &&
        reading != null &&
        (!command.startsWith('VENT:') || reading.mode == 'MONITOREO');
  }
}
