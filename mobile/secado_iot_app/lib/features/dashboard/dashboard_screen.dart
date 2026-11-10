import 'package:flutter/material.dart';

import '../../data/repositories/secado_repository.dart';
import '../../core/theme/app_theme.dart';
import '../../shared/widgets.dart';

class DashboardScreen extends StatelessWidget {
  final SecadoRepository repo;
  const DashboardScreen(this.repo, {super.key});
  @override
  Widget build(BuildContext context) {
    final r = repo.reading;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          padding: const EdgeInsets.all(24),
          margin: const EdgeInsets.only(bottom: 20),
          decoration: BoxDecoration(
            color: AppTheme.forest,
            borderRadius: BorderRadius.circular(24),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Row(
                children: [
                  Icon(Icons.eco_outlined, color: Color(0xFFD6C69B)),
                  SizedBox(width: 10),
                  Text(
                    'CAFÉ & CACAO',
                    style: TextStyle(
                      color: Color(0xFFD6C69B),
                      letterSpacing: 2,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              const Text(
                'Cada grado cuenta.',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 30,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Secado bajo observación · ${repo.node}',
                style: const TextStyle(color: Color(0xFFCEE0D2)),
              ),
              const SizedBox(height: 18),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  Chip(label: Text('EMQX: ${repo.status}')),
                  Chip(
                    label: Text(
                      repo.fresh
                          ? 'Nodo con actividad reciente'
                          : 'Nodo sin actividad reciente',
                    ),
                  ),
                  Chip(
                    label: Text(
                      r == null
                          ? 'Sin datos'
                          : r.simulated
                              ? 'Simulación'
                              : 'Datos reales',
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        if (r == null)
          const Notice(
            'Sin mediciones. Conecta MQTT y espera telemetría del nodo seleccionado.',
          ),
        if (r != null && !repo.fresh)
          const Notice(
            'Lecturas antiguas: comprueba la comunicación del nodo. Los valores conservan su timestamp.',
            warning: true,
          ),
        if (r != null && r.grain > 45)
          const Notice(
            'Alerta local: temperatura del grano superior a 45 °C.',
            warning: true,
          ),
        LayoutBuilder(
          builder: (context, box) {
            final width = box.maxWidth > 650
                ? (box.maxWidth - 32) / 3
                : (box.maxWidth - 16) / 2;
            return Wrap(
              spacing: 16,
              runSpacing: 16,
              children: [
                SizedBox(
                  width: width,
                  child: Metric(
                    'Temperatura ambiental',
                    display(r?.ambient, ' °C'),
                    Icons.thermostat_outlined,
                  ),
                ),
                SizedBox(
                  width: width,
                  child: Metric(
                    'Humedad relativa',
                    display(r?.humidity, ' %'),
                    Icons.water_drop_outlined,
                  ),
                ),
                SizedBox(
                  width: width,
                  child: Metric(
                    'Temperatura del grano',
                    display(r?.grain, ' °C'),
                    Icons.grain,
                    critical: (r?.grain ?? 0) > 45,
                  ),
                ),
              ],
            );
          },
        ),
        const SizedBox(height: 20),
        Panel(
          title: 'Estado reportado',
          child: Column(
            children: [
              detailRow('Consigna térmica', display(r?.setpoint, ' °C')),
              detailRow('Modo operativo', r?.mode),
              detailRow('Ventilador', display(r?.fan, ' PWM')),
              detailRow('Calefactor', r?.heater),
              detailRow(
                'Última medición (hora local)',
                localTime(r?.timestamp),
              ),
              detailRow('Secuencia', r?.sequence),
              detailRow('Estado del puente', repo.nodeStates[repo.node]),
            ],
          ),
        ),
      ],
    );
  }
}
