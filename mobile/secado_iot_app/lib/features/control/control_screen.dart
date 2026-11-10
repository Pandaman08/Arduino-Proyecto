import 'package:flutter/material.dart';

import '../../data/repositories/secado_repository.dart';
import '../../shared/widgets.dart';

class ControlScreen extends StatefulWidget {
  final SecadoRepository repo;
  const ControlScreen(this.repo, {super.key});
  @override
  State<ControlScreen> createState() => _ControlScreenState();
}

class _ControlScreenState extends State<ControlScreen> {
  String mode = 'MONITOREO';
  double setpoint = 30, pwm = 0;
  bool _confirming = false;
  Future<void> apply(String command) async {
    if (_confirming || !widget.repo.canSend(command)) return;
    _confirming = true;
    final target = widget.repo.node;
    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Confirmar comando'),
        content: Text(
          'Enviar $command a $target. Puede modificar el funcionamiento del secador. La ejecución requiere respuesta del dispositivo.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Enviar'),
          ),
        ],
      ),
    );
    _confirming = false;
    if (!mounted || accepted != true) return;
    try {
      if (widget.repo.node != target) {
        throw StateError('El nodo seleccionado cambió');
      }
      widget.repo.send(command);
    } catch (_) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'El comando se bloqueó: verifica permisos, conexión y lecturas recientes.',
          ),
        ),
      );
    }
  }

  Widget button(String label, String command) => FilledButton.tonal(
        onPressed: widget.repo.canSend(command) ? () => apply(command) : null,
        child: Text(label),
      );
  @override
  Widget build(BuildContext context) {
    final repo = widget.repo;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Notice(
          repo.controlEnabled
              ? 'Control habilitado para la cuenta configurada. EMQX aplica los permisos efectivos.'
              : 'Modo solo lectura. El control requiere credenciales de operador y ACL verificadas en el despliegue.',
          warning: !repo.controlEnabled,
        ),
        if (repo.reading?.simulated == true || repo.node.startsWith('sim'))
          const Notice('Nodo simulado: controles físicos deshabilitados.'),
        if (repo.reading == null || !repo.fresh)
          const Notice(
              'Para arrancar sin telemetría, consulta ESTADO y espera la confirmación del Arduino; después aplica un modo. PARAR permanece disponible para un operador conectado.'),
        const Notice(
          'La aceptación del puente indica envío. La confirmación requiere la respuesta correlacionada del Arduino con firmware 1.1. Con firmware anterior la ejecución queda sin confirmar.',
        ),
        Panel(
          title: 'Modo operativo',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('Reportado: ${display(repo.reading?.mode)}'),
              const SizedBox(height: 14),
              SegmentedButton<String>(
                segments: const [
                  ButtonSegment(value: 'MONITOREO', label: Text('MONITOREO')),
                  ButtonSegment(value: 'CONTROL', label: Text('CONTROL')),
                ],
                selected: {mode},
                onSelectionChanged: (value) =>
                    setState(() => mode = value.first),
              ),
              const SizedBox(height: 12),
              button('Aplicar modo', 'MODO:$mode'),
            ],
          ),
        ),
        Panel(
          title: 'Consigna térmica · 10 a 50 °C',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                '${setpoint.toStringAsFixed(1)} °C',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              Slider(
                value: setpoint,
                min: 10,
                max: 50,
                divisions: 400,
                label: setpoint.toStringAsFixed(1),
                onChanged: (value) => setState(() => setpoint = value),
              ),
              button('Aplicar consigna', 'SP:${setpoint.toStringAsFixed(1)}'),
            ],
          ),
        ),
        Panel(
          title: 'Ventilador · PWM 0 a 255',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('${pwm.round()} PWM'),
              Slider(
                value: pwm,
                min: 0,
                max: 255,
                divisions: 255,
                onChanged: repo.reading?.mode == 'MONITOREO'
                    ? (value) => setState(() => pwm = value)
                    : null,
              ),
              const Text('El modo reportado debe ser MONITOREO.'),
              const SizedBox(height: 12),
              button('Aplicar ventilador', 'VENT:${pwm.round()}'),
            ],
          ),
        ),
        Panel(
          title: 'Operaciones',
          child: Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              button('Consultar estado', 'ESTADO'),
              button('PARAR', 'PARAR'),
            ],
          ),
        ),
        const Text('Calefactor deshabilitado en firmware (ENABLE_HEATER=0).'),
        const SizedBox(height: 16),
        Panel(
          title: 'Seguimiento de comandos',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (repo.commands.isEmpty)
                const Text('Todavía no se enviaron comandos.'),
              for (final c in repo.commands.take(20))
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text('${c.command} · ${c.stage.label}'),
                  subtitle: Text(
                    '${c.node} · ${localTime(c.created)}\n${c.detail}\n${c.id}',
                  ),
                  isThreeLine: true,
                ),
            ],
          ),
        ),
      ],
    );
  }
}
