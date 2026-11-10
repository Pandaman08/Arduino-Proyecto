import 'package:flutter/material.dart';

import '../../core/config/app_config.dart';
import '../../core/security/credentials.dart';
import '../../data/repositories/secado_repository.dart';
import '../../shared/widgets.dart';

class SettingsScreen extends StatefulWidget {
  final SecadoRepository repo;
  const SettingsScreen(this.repo, {super.key});
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final user = TextEditingController(), password = TextEditingController();
  bool saving = false;
  @override
  void dispose() {
    user.dispose();
    password.dispose();
    super.dispose();
  }

  Future<void> save() async {
    if (saving) return;
    if (user.text.trim().isEmpty || password.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Completa usuario y contraseña de aplicación.'),
        ),
      );
      return;
    }
    setState(() => saving = true);
    try {
      await widget.repo.saveCredentials(
        Credentials(user.text.trim(), password.text),
      );
      user.clear();
      password.clear();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Credenciales guardadas. Puedes conectar MQTT.'),
          ),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('No se pudo acceder al almacenamiento seguro.'),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final repo = widget.repo;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Panel(
          title: 'Conexión segura a EMQX',
          child: Column(
            children: [
              detailRow('Host', AppConfig.host),
              detailRow('Puerto', AppConfig.port),
              detailRow('WebSocket', AppConfig.path),
              detailRow('TLS', 'Validación del sistema habilitada'),
              detailRow('Protocolo', 'MQTT 3.1.1 · QoS 1'),
              detailRow('Keepalive', '${AppConfig.keepAlive} s'),
              detailRow('Client ID', repo.transport.clientId),
              detailRow('Nodo', repo.node),
              detailRow('Estado', repo.status),
              detailRow('Última conexión', localTime(repo.lastConnection)),
              detailRow('Último error (sanitizado)', repo.lastError),
              detailRow(
                'Mensajes recibidos / descartados',
                '${repo.received} / ${repo.discarded}',
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 12,
                runSpacing: 12,
                children: [
                  FilledButton(
                    onPressed: repo.connected || repo.status == 'Conectando'
                        ? null
                        : repo.connect,
                    child: const Text('Conectar / Reintentar'),
                  ),
                  OutlinedButton(
                    onPressed: repo.disconnect,
                    child: const Text('Desconectar'),
                  ),
                ],
              ),
            ],
          ),
        ),
        Panel(
          title: 'Autenticación de aplicación',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'Credenciales guardadas con protección del sistema Android. No utilices la cuenta administrativa de EMQX.',
              ),
              const SizedBox(height: 16),
              TextField(
                controller: user,
                obscureText: true,
                autocorrect: false,
                enableSuggestions: false,
                decoration: const InputDecoration(labelText: 'Usuario MQTT'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: password,
                obscureText: true,
                autocorrect: false,
                enableSuggestions: false,
                decoration: const InputDecoration(labelText: 'Contraseña MQTT'),
              ),
              const SizedBox(height: 12),
              FilledButton.tonal(
                onPressed: saving ? null : save,
                child: const Text('Guardar credenciales'),
              ),
              TextButton(
                onPressed: () async {
                  try {
                    await repo.clearCredentials();
                  } catch (_) {
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text(
                            'No se pudieron eliminar las credenciales.',
                          ),
                        ),
                      );
                    }
                  }
                },
                child: const Text('Eliminar credenciales del dispositivo'),
              ),
            ],
          ),
        ),
        Panel(
          title: 'Autorización de control',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                repo.controlEnabled
                    ? 'Operador · sesión habilitada'
                    : 'Monitor · solo lectura',
              ),
              const SizedBox(height: 12),
              const Text(
                'Una opción visual no concede permisos. El administrador debe configurar ACL en EMQX y verificar la cuenta antes de habilitar el despliegue de operador.',
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Habilitar control en esta sesión'),
                subtitle: Text(
                  repo.canActivateControl
                      ? 'Cuenta de operador configurada para este despliegue'
                      : 'Bloqueado: falta verificación de ACL o credencial de operador',
                ),
                value: repo.controlEnabled,
                onChanged:
                    repo.canActivateControl ? repo.activateControl : null,
              ),
            ],
          ),
        ),
        Panel(
          title: 'Suscripciones confirmadas por EMQX',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (repo.subscribed.isEmpty)
                const Text('Sin SUBACK. Verifica conexión y ACL.'),
              for (final topic in repo.subscribed)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Text(topic),
                ),
            ],
          ),
        ),
      ],
    );
  }
}
