import 'package:flutter/material.dart';

import '../core/theme/app_theme.dart';

String display(Object? value, [String unit = '']) => value == null
    ? 'No disponible'
    : '${value is double ? value.toStringAsFixed(1) : value}$unit';
String localTime(DateTime? time) =>
    time == null ? 'No disponible' : time.toLocal().toString().split('.').first;

class Panel extends StatelessWidget {
  final String title;
  final Widget child;
  const Panel({super.key, required this.title, required this.child});
  @override
  Widget build(BuildContext context) => Card(
        elevation: 0,
        margin: const EdgeInsets.only(bottom: 16),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(22),
          side: const BorderSide(color: Color(0xFFE4E4D9)),
        ),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: Theme.of(context)
                    .textTheme
                    .titleMedium
                    ?.copyWith(fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 16),
              child,
            ],
          ),
        ),
      );
}

class Notice extends StatelessWidget {
  final String text;
  final bool warning;
  const Notice(this.text, {super.key, this.warning = false});
  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        margin: const EdgeInsets.only(bottom: 16),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: warning ? const Color(0xFFFFE9D6) : const Color(0xFFE3EDE5),
          borderRadius: BorderRadius.circular(16),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(
              warning ? Icons.warning_amber_rounded : Icons.info_outline,
              color: warning ? Colors.deepOrange.shade800 : AppTheme.forest,
            ),
            const SizedBox(width: 12),
            Expanded(child: Text(text)),
          ],
        ),
      );
}

class Metric extends StatelessWidget {
  final String label, value;
  final IconData icon;
  final bool critical;
  const Metric(
    this.label,
    this.value,
    this.icon, {
    super.key,
    this.critical = false,
  });
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          color: critical ? const Color(0xFFFFE3DD) : Colors.white,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: const Color(0xFFE4E4D9)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: critical ? Colors.red.shade800 : AppTheme.coffee),
            const SizedBox(height: 14),
            Text(
              value,
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    color: critical ? Colors.red.shade800 : AppTheme.forest,
                    fontWeight: FontWeight.w700,
                  ),
            ),
            const SizedBox(height: 6),
            Text(label),
          ],
        ),
      );
}

Widget detailRow(String name, Object? value) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(child: Text(name)),
          const SizedBox(width: 12),
          Flexible(
            child: Text(
              display(value),
              textAlign: TextAlign.end,
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
