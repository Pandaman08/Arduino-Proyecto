import 'dart:convert';
import 'package:secado_iot_app/data/mqtt/mqtt_transport.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:secado_iot_app/main.dart';
import 'package:secado_iot_app/data/repositories/secado_repository.dart';

import 'fakes.dart';

void main() {
  testWidgets('dashboard sin datos y navegación por cinco pantallas', (
    tester,
  ) async {
    final repo = SecadoRepository(FakeTransport(), MemoryCredentials());
    await tester.pumpWidget(SecadoApp(repository: repo));
    expect(find.text('Sin datos'), findsOneWidget);
    for (final label in [
      'Monitoreo',
      'Control',
      'Alertas',
      'Ajustes',
      'Inicio',
    ]) {
      await tester.tap(find.widgetWithText(NavigationDestination, label));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    }
    await tester.pumpWidget(const SizedBox());
  });
  testWidgets('mediciones y simulación visibles', (tester) async {
    final repo = SecadoRepository(FakeTransport(), MemoryCredentials());
    await repo.connect();
    repo.selectNode('sim1');
    repo.receive(frame(DateTime.now().toUtc(), node: 'sim1'));
    await tester.pumpWidget(SecadoApp(repository: repo));
    expect(find.text('Simulación'), findsOneWidget);
    expect(find.text('28.5 °C'), findsOneWidget);
    await tester.tap(find.widgetWithText(NavigationDestination, 'Control'));
    await tester.pumpAndSettle();
    expect(
      find.text('Nodo simulado: controles físicos deshabilitados.'),
      findsOneWidget,
    );
    await tester.pumpWidget(const SizedBox());
  });
  testWidgets('alerta crítica local visible', (tester) async {
    final repo = SecadoRepository(FakeTransport(), MemoryCredentials());
    await repo.connect();
    repo.receive(WireMessage('secado/secador_01/telemetria',
        jsonEncode(telemetry(DateTime.now().toUtc())..['t_grano'] = 46)));
    await tester.pumpWidget(SecadoApp(repository: repo));
    expect(find.text('Alerta local: temperatura del grano superior a 45 °C.'),
        findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
  testWidgets('error MQTT visible y control en solo lectura', (tester) async {
    final wire = FakeTransport()..failure = StateError('credencial de prueba');
    final repo = SecadoRepository(wire, MemoryCredentials());
    await repo.connect();
    await tester.pumpWidget(SecadoApp(repository: repo));
    expect(find.text('EMQX: Error de conexión'), findsOneWidget);
    await tester.tap(find.widgetWithText(NavigationDestination, 'Control'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Modo solo lectura.'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
}
