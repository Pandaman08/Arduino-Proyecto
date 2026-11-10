enum CommandStage {
  pending('Pendiente'),
  published('Publicado'),
  bridgeAccepted('Aceptado por puente'),
  confirmed('Confirmado por Arduino'),
  rejected('Rechazado'),
  error('Error'),
  timeout('Tiempo agotado');

  final String label;
  const CommandStage(this.label);
}

class CommandRecord {
  final String id, node, command;
  final DateTime created;
  CommandStage stage = CommandStage.pending;
  String detail = 'Esperando publicación';
  CommandRecord(this.id, this.node, this.command, this.created);
  bool get active => [
        CommandStage.pending,
        CommandStage.published,
        CommandStage.bridgeAccepted,
      ].contains(stage);
}

class LocalEvent {
  final DateTime time;
  final String source, message;
  final bool critical;
  LocalEvent(this.time, this.source, this.message, {this.critical = false});
}
