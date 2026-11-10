import 'package:flutter/material.dart';

import '../../data/models/telemetry.dart';
import '../../data/repositories/secado_repository.dart';
import '../../shared/widgets.dart';
import '../../core/theme/app_theme.dart';

class MonitoringScreen extends StatelessWidget {
  final SecadoRepository repo;
  const MonitoringScreen(this.repo, {super.key});
  @override
  Widget build(BuildContext context) {
    final rows = repo.history;
    final interval = rows.length < 2
        ? null
        : rows.last.timestamp
                .difference(rows[rows.length - 2].timestamp)
                .inMilliseconds /
            1000;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Notice(
          'Historial de esta sesión · hasta 300 lecturas por nodo. Los cortes mayores de 15 s se muestran como discontinuidades.',
        ),
        if (!repo.connected)
          const Notice(
            'MQTT desconectado. Las gráficas muestran únicamente lecturas recibidas anteriormente.',
            warning: true,
          ),
        if (rows.isEmpty)
          const Panel(
            title: 'Esperando telemetría',
            child: Text('Sin datos para graficar.'),
          ),
        if (rows.isNotEmpty) ...[
          Panel(
            title: 'Temperatura ambiental · °C',
            child: TimeChart(
              rows: rows,
              values: [(t) => t.ambient],
              colors: const [AppTheme.coffee],
            ),
          ),
          Panel(
            title: 'Grano y consigna · °C',
            child: Column(
              children: [
                TimeChart(
                  rows: rows,
                  values: [(t) => t.grain, (t) => t.setpoint],
                  colors: const [AppTheme.forest, Colors.orange],
                ),
                const Wrap(
                  spacing: 20,
                  children: [
                    Text('● Grano', style: TextStyle(color: AppTheme.forest)),
                    Text('● Consigna', style: TextStyle(color: Colors.orange)),
                  ],
                ),
              ],
            ),
          ),
          Panel(
            title: 'Humedad relativa · %',
            child: TimeChart(
              rows: rows,
              values: [(t) => t.humidity],
              colors: const [Colors.blueGrey],
            ),
          ),
        ],
        Panel(
          title: 'Ventana de observación',
          child: Column(
            children: [
              detailRow('Lecturas en memoria', rows.length),
              detailRow('Último intervalo', display(interval, ' s')),
              detailRow('Desde', localTime(rows.firstOrNull?.timestamp)),
              detailRow('Hasta', localTime(rows.lastOrNull?.timestamp)),
              detailRow(
                'Actividad',
                repo.fresh ? 'Reciente' : 'Sin datos recientes',
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class TimeChart extends StatelessWidget {
  final List<Telemetry> rows;
  final List<double? Function(Telemetry)> values;
  final List<Color> colors;
  const TimeChart({
    super.key,
    required this.rows,
    required this.values,
    required this.colors,
  });
  @override
  Widget build(BuildContext context) {
    final all = rows
        .expand((r) => values.map((v) => v(r)))
        .whereType<double>()
        .toList();
    if (all.isEmpty) return const Text('Sin valores disponibles');
    final low = all.reduce((a, b) => a < b ? a : b).floorToDouble() - 1;
    final high = all.reduce((a, b) => a > b ? a : b).ceilToDouble() + 1;
    return Column(
      children: [
        Row(
          children: [
            Text(high.toStringAsFixed(0)),
            const Spacer(),
            const Text('Escala temporal real'),
          ],
        ),
        SizedBox(
          height: 150,
          width: double.infinity,
          child: CustomPaint(
            painter: _TimePainter(rows, values, colors, low, high),
          ),
        ),
        Row(
          children: [
            Text(low.toStringAsFixed(0)),
            const Spacer(),
            Text('${rows.length} lecturas'),
          ],
        ),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(localTime(rows.first.timestamp).split(' ').last),
            Text(localTime(rows.last.timestamp).split(' ').last),
          ],
        ),
      ],
    );
  }
}

class _TimePainter extends CustomPainter {
  final List<Telemetry> rows;
  final List<double? Function(Telemetry)> values;
  final List<Color> colors;
  final double low, high;
  _TimePainter(this.rows, this.values, this.colors, this.low, this.high);
  @override
  void paint(Canvas canvas, Size size) {
    final grid = Paint()
      ..color = const Color(0xFFE1E5DD)
      ..strokeWidth = 1;
    for (var i = 0; i < 4; i++) {
      final y = size.height * i / 3;
      canvas.drawLine(Offset(0, y), Offset(size.width, y), grid);
    }
    final start = rows.first.timestamp.millisecondsSinceEpoch;
    final span = (rows.last.timestamp.millisecondsSinceEpoch - start).clamp(
      1,
      1 << 62,
    );
    for (var series = 0; series < values.length; series++) {
      final paint = Paint()
        ..color = colors[series]
        ..strokeWidth = 2.5
        ..style = PaintingStyle.stroke;
      Offset? previous;
      Telemetry? last;
      for (final row in rows) {
        final value = values[series](row);
        if (value == null) {
          previous = null;
          last = null;
          continue;
        }
        final point = Offset(
          (row.timestamp.millisecondsSinceEpoch - start) / span * size.width,
          size.height * (1 - (value - low) / (high - low)),
        );
        if (previous != null &&
            last != null &&
            row.timestamp.difference(last.timestamp) <=
                const Duration(seconds: 15)) {
          canvas.drawLine(previous, point, paint);
        }
        canvas.drawCircle(point, 2, Paint()..color = colors[series]);
        previous = point;
        last = row;
      }
    }
  }

  @override
  bool shouldRepaint(covariant _TimePainter oldDelegate) => true;
}
