# Secado IoT · Café y Cacao

Aplicación Android Flutter del Laboratorio 11. Se conecta directamente al broker EMQX existente por WSS; Streamlit puede permanecer cerrado. El puente Python debe ejecutarse para recibir datos o controlar el Arduino por USB/Serial.

## Preparación

Se utiliza Flutter **3.47.9**, Dart **3.13.7**, Android SDK y un **JDK completo** (21 recomendado; debe existir `javac`). Instala Flutter desde [la guía oficial](https://docs.flutter.dev/install) o clona la versión usada:

```bash
git clone --depth 1 --branch 3.47.9 https://github.com/flutter/flutter.git /tmp/flutter-lab11
export PATH="/tmp/flutter-lab11/bin:$PATH"
# Cambiar estas rutas por la instalación local:
export JAVA_HOME=/ruta/al/jdk-21
export ANDROID_HOME="$HOME/Android/Sdk"
flutter doctor -v
flutter doctor --android-licenses
```

El SDK temporal instalado durante esta entrega está en `/tmp/lab11-flutter`; desaparece al limpiar `/tmp` o reiniciar. No se modificó el PATH permanente.

Desde la raíz del repositorio:

```bash
cd mobile/secado_iot_app
flutter pub get
flutter analyze
flutter test
flutter build apk --debug
flutter devices
flutter run -d ID_DEL_TELEFONO
```

Activa Opciones de desarrollador → Depuración USB, conecta el teléfono y acepta su autorización RSA. USB se usa para instalar y depurar la app; después basta Wi-Fi o datos móviles para alcanzar EMQX. Arduino sigue conectado al ordenador que ejecuta el puente.

En Flutter 3.47.9 el analizador LSP falla con esta ruta que contiene `AÑO`. Para ejecutar las mismas verificaciones en una copia temporal ASCII y recuperar el APK:

```bash
FLUTTER_BIN=/tmp/lab11-flutter/bin/flutter ./tool/verify.sh
```

El script resuelve dependencias, analiza, prueba y compila; no contacta EMQX ni transmite comandos físicos. Para una instalación fuera de este equipo, coloca el repositorio en una ruta ASCII o usa el script. Resultado esperado: `build/app/outputs/flutter-apk/app-debug.apk`. El resultado real de la entrega se registra en [el informe](../../docs/lab11_mobile.md).

## Conexión y seguridad

1. Abre **Ajustes**, introduce credenciales de aplicación MQTT y pulsa **Guardar credenciales**. Los dos campos están ocultos; nunca se precargan secretos en pantalla.
2. Pulsa **Conectar / Reintentar**. Si el broker permite conexión anónima, puede monitorizarse sin guardar credenciales; el control permanece bloqueado.
3. Comprueba los SUBACK en diagnóstico. Selecciona `secador_01` o uno de `sim1..sim4`.
4. El distintivo de origen y la actividad del nodo son independientes del estado de conexión al broker.

Configuración fija: `wss://cafes.duckdns.org/mqtt`, puerto 443, MQTT 3.1.1, QoS 1, certificado y nombre del servidor validados por Dart. Keepalive inicial 60 s, configurable al construir con `--dart-define=MQTT_KEEPALIVE=60`. No hay opción para desactivar TLS.

Los secretos se guardan usando `flutter_secure_storage` con Android EncryptedSharedPreferences. Se deshabilitan copias de seguridad Android. **Eliminar credenciales** desconecta y borra el almacenamiento seguro. No se incluyen claves de producción ni datos de `.env` en el APK.

### Operador

La app inicia siempre en solo lectura. Una selección visual no concede autorización MQTT. El administrador debe completar la matriz de [ACL y pruebas](../../docs/lab11_mobile.md) antes de construir una variante para operador:

```bash
flutter build apk --debug \
  --dart-define=MQTT_ACL_VERIFIED=true \
  --dart-define=MQTT_OPERATOR_USER=USUARIO_DE_APLICACION_VERIFICADO
```

`MQTT_OPERATOR_USER` es un identificador de despliegue, no una contraseña. Las credenciales se introducen exclusivamente en el teléfono. Tras conectar con esa cuenta, habilita el control **para esta sesión** en Ajustes. Una desconexión o suspensión lo revoca. No uses esa opción hasta probar los permisos reales de EMQX. Las ACL son la frontera de autorización; el parámetro de compilación no prueba ni instala permisos.

Para incorporar otro nodo físico, el administrador debe verificarlo y editar explícitamente `AppConfig.physicalNodes`, ampliar ACL y volver a construir. No se descubren ni se aceptan identificadores arbitrarios.

## Monitoreo y control

- Dashboard con temperaturas ambiental y del grano, humedad, consigna y actuadores únicamente cuando fueron reportados.
- Gráficas con timestamps reales, puntos y discontinuidades mayores a 15 s; la consigna ausente interrumpe su serie.
- Hasta 300 lecturas por nodo, 200 eventos y 100 comandos en memoria de sesión. No se consulta SQLite ni se promete historial remoto.
- Alertas locales: grano >45 °C, desconexión, datos antiguos, mensajes inválidos y timeout. Los eventos del puente y firmware se identifican por separado.
- Los comandos requieren datos no retenidos recientes, SUBACK de los tres tópicos, nodo físico, autorización, confirmación explícita y ninguna solicitud activa.
- `SP:10..50`, `VENT:0..255` solo en MONITOREO **reportado**, `MODO:MONITOREO`, `MODO:CONTROL`, `ESTADO`, `PARAR`. Cambiar un slider no publica.
- No se controla calefacción; `ENABLE_HEATER=0` permanece sin cambios.
- Suspender la app cierra MQTT; al regresar se puede reconectar, siempre en solo lectura. No hay servicio ni notificaciones en segundo plano.

### Confirmaciones

El JSON conserva `{ "command": "MODO:CONTROL", "request_id": "UUID" }` y se publica en `secado/<nodo>/cmd`, QoS 1 y `retain=false`.

El puente responde con `request_id` al **enviar** al Arduino. El firmware actual responde `ACK:...` / `ERR:...` sin ese identificador. La app presenta esas respuestas como eventos sin correlación garantizada y mantiene el comando en **Aceptado por puente** hasta agotar 12 s sin confirmación correlacionada. No afirma **Confirmado por Arduino**. `ESTADO` responde en el tópico de estado y tampoco confirma una solicitud particular. No se reenvían solicitudes tras desconexión, timeout o reinicio.

Serializar solo los comandos del móvil no soluciona las respuestas tardías ni la concurrencia con Streamlit. Para garantizar correlación se necesita un protocolo transaccional que el firmware pueda devolver, o una única autoridad con exclusión y recuperación formal; queda fuera de esta entrega para conservar el firmware.

## Demostración

En el ordenador, con las credenciales del publicador configuradas localmente:

```bash
source .venv/bin/activate
python -m src.mqtt.virtual_nodes_cli --interval 2
# Alternativa con hardware (un solo dueño del puerto USB):
python -m src.mqtt.bridge_cli --port /dev/ttyUSB0 --node-id secador_01
```

En Android selecciona `sim1` para simulación explícita; los controles físicos estarán bloqueados. Para hardware usa `secador_01`, verifica recepción reciente y habilita operador solo con ACL comprobada. No presentes una simulación como validación física.

## Pruebas

```bash
flutter test --reporter expanded
# Solo en un dispositivo conectado; no publica comandos:
flutter test integration_test/app_test.dart -d ID_DEL_TELEFONO
# Regresión Python desde la raíz:
.venv/bin/python -m pytest tests/ -v
```

`test/wss_transport_test.dart` usa un servidor WSS efímero ligado a loopback y un fixture MQTT 3.1.1 para comprobar tráfico real, autenticación y rechazo TLS. Su certificado/clave son públicos de prueba; la confianza positiva solo existe dentro del test. Los fakes de repositorio prueban estados y reglas de negocio. Ninguna prueba automatizada envía comandos a producción.

Separación de código: `core` configura tema y seguridad; `data/models` valida contratos; `data/mqtt` encapsula MQTT; `data/repositories` administra conexión, backoff y estado; `features` contiene las cinco pantallas; `shared` reúne componentes. Se utiliza `ChangeNotifier` con `ListenableBuilder` del SDK: un solo repositorio inyectable, sin agregar una dependencia de estado innecesaria.
