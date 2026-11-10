import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:secado_iot_app/main.dart' as app;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('arranque Android sin publicar comandos', (tester) async {
    app.main();
    await tester.pumpAndSettle();
    expect(find.text('Secado IoT'), findsOneWidget);
    expect(find.byType(NavigationBar), findsOneWidget);
    await tester.tap(find.widgetWithText(NavigationDestination, 'Ajustes'));
    await tester.pumpAndSettle();
    expect(find.text('Conexión segura a EMQX'), findsOneWidget);
  });
}
