import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:uuid/uuid.dart';

import 'core/config/app_config.dart';
import 'core/security/credentials.dart';
import 'core/theme/app_theme.dart';
import 'data/mqtt/mqtt_transport.dart';
import 'data/repositories/secado_repository.dart';
import 'features/dashboard/dashboard_screen.dart';
import 'features/monitoring/monitoring_screen.dart';
import 'features/control/control_screen.dart';
import 'features/alerts/alerts_screen.dart';
import 'features/settings/settings_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  final id = 'movil-${const Uuid().v4().replaceAll('-', '').substring(0, 16)}';
  runApp(
    SecadoApp(
      repository: SecadoRepository(
        WssMqttTransport(id),
        SecureCredentialStore(),
      ),
    ),
  );
}

class SecadoApp extends StatelessWidget {
  final SecadoRepository repository;
  const SecadoApp({super.key, required this.repository});
  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'Secado IoT · Café y Cacao',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.light,
        locale: const Locale('es'),
        supportedLocales: const [Locale('es')],
        localizationsDelegates: GlobalMaterialLocalizations.delegates,
        home: SecadoHome(repository: repository),
      );
}

class SecadoHome extends StatefulWidget {
  final SecadoRepository repository;
  const SecadoHome({super.key, required this.repository});
  @override
  State<SecadoHome> createState() => _SecadoHomeState();
}

class _SecadoHomeState extends State<SecadoHome> with WidgetsBindingObserver {
  int page = 0;
  bool _resumeConnection = false;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    widget.repository.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.detached) {
      _resumeConnection = widget.repository.connected;
      unawaited(widget.repository.disconnect());
    } else if (state == AppLifecycleState.resumed && _resumeConnection) {
      _resumeConnection = false;
      unawaited(widget.repository.connect());
    }
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: widget.repository,
        builder: (context, _) {
          final repo = widget.repository;
          final screens = [
            DashboardScreen(repo),
            MonitoringScreen(repo),
            ControlScreen(repo),
            AlertsScreen(repo),
            SettingsScreen(repo),
          ];
          const titles = [
            'Vista general',
            'Monitoreo en vivo',
            'Control del secador',
            'Alertas y eventos',
            'Configuración MQTT',
          ];
          return Scaffold(
            appBar: AppBar(
              title: const Text(
                'Secado IoT',
                style: TextStyle(fontWeight: FontWeight.w700),
              ),
              actions: [
                Padding(
                  padding: const EdgeInsets.only(right: 20),
                  child: Row(
                    children: [
                      Icon(
                        Icons.circle,
                        size: 10,
                        color: repo.connected ? Colors.green : Colors.grey,
                      ),
                      const SizedBox(width: 6),
                      Text(repo.connected ? 'EMQX conectado' : 'Sin conexión'),
                    ],
                  ),
                ),
              ],
            ),
            body: SafeArea(
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 1000),
                  child: Column(
                    children: [
                      Padding(
                        padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
                        child: Row(
                          children: [
                            Expanded(
                              child: Text(
                                titles[page],
                                style: Theme.of(context).textTheme.titleLarge,
                              ),
                            ),
                            const SizedBox(width: 12),
                            DropdownButton<String>(
                              value: repo.node,
                              underline: const SizedBox.shrink(),
                              items: AppConfig.nodes
                                  .map(
                                    (n) => DropdownMenuItem(
                                        value: n, child: Text(n)),
                                  )
                                  .toList(),
                              onChanged: (n) {
                                if (n != null) repo.selectNode(n);
                              },
                            ),
                          ],
                        ),
                      ),
                      Expanded(
                        child: SingleChildScrollView(
                          key: ValueKey(page),
                          padding: const EdgeInsets.symmetric(
                            horizontal: 20,
                            vertical: 4,
                          ),
                          child: screens[page],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            bottomNavigationBar: NavigationBar(
              selectedIndex: page,
              onDestinationSelected: (value) => setState(() => page = value),
              labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
              destinations: const [
                NavigationDestination(
                  icon: Icon(Icons.dashboard_outlined),
                  label: 'Inicio',
                ),
                NavigationDestination(
                  icon: Icon(Icons.show_chart),
                  label: 'Monitoreo',
                ),
                NavigationDestination(icon: Icon(Icons.tune), label: 'Control'),
                NavigationDestination(
                  icon: Icon(Icons.notifications_outlined),
                  label: 'Alertas',
                ),
                NavigationDestination(
                  icon: Icon(Icons.settings_outlined),
                  label: 'Ajustes',
                ),
              ],
            ),
          );
        },
      );
}
