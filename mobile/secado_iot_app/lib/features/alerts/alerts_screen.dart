import 'package:flutter/material.dart';

import '../../data/repositories/secado_repository.dart';
import '../../shared/widgets.dart';

class AlertsScreen extends StatelessWidget {
  final SecadoRepository repo;
  const AlertsScreen(this.repo, {super.key});
  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Notice(
            'Eventos locales de esta sesión · máximo 200. Las alertas de mediciones se calculan en el teléfono. No hay notificaciones en segundo plano.',
          ),
          Panel(
            title: 'Alertas y eventos',
            child: Column(
              children: [
                if (repo.events.isEmpty) const Text('Sin eventos registrados.'),
                for (final event in repo.events)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: Icon(
                      event.critical
                          ? Icons.warning_amber_rounded
                          : Icons.info_outline,
                      color: event.critical
                          ? Colors.deepOrange
                          : Colors.green.shade800,
                    ),
                    title: Text(event.message),
                    subtitle:
                        Text('${event.source} · ${localTime(event.time)}'),
                  ),
              ],
            ),
          ),
        ],
      );
}
