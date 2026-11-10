# Laboratorio 11 · Extensión móvil MQTT y seguridad

Fecha de ejecución: **10 de noviembre de 2026**. Rama: `feature/lab11-flutter-mqtt`.
Guía consultada: `Laboratorio_11__2026.pdf`, extraída con `pdftotext` desde la carpeta académica `iOT/11`. Sus actividades son implementar las funcionalidades MQTT mediante una extensión móvil y un avance de mecanismos de seguridad. La solicitud amplía ese prototipo a una aplicación Flutter con pruebas y documentación.

## Auditoría previa

Se revisaron estructura y rama, README, `.env.example`, requisitos, `app.py`, los módulos MQTT de cliente/configuración/tópicos/mensajes/puente/adaptador/nodos virtuales, persistencia de experimentos, protocolo documentado, auditoría de fase 7, firmware y tests MQTT. La auditoría inicial conservó Streamlit, Random Forest, SQLite y broker. La actualización 1.1 del firmware y puente añade correlación a petición del usuario. No se leyó ni copió contenido secreto a los archivos móviles.

- La rama inicial era `feature/flutter-mqtt`; el árbol estaba limpio. Se creó la rama solicitada sin merge ni push.
- La base inicial pasó **40 tests Python**. La regresión con las mejoras del puente pasó **48 tests**.
- El puente publica telemetría enriquecida o CSV legado; los campos opcionales no siempre existen. Los alias `id/ts/seq/t_ideal/ventilador_pwm/led` se mantienen en Flutter.
- El único nodo físico configurado inicialmente es `secador_01`, presente en `.env.example`. Los simulados `sim1..sim4` proceden de `default_virtual_nodes()`. Otros selectores de Streamlit no demuestran por sí mismos hardware disponible.
- Los nodos virtuales publican `modo="simulacion"`, `simulado=true`, sin suscribir comandos. Flutter los interpreta y bloquea control físico.
- La consigna del firmware está entre 10 y 50 °C. VENT admite 0..255 solo en MONITOREO; `ENABLE_HEATER=0` permanece intacto.
- En la auditoría inicial, el firmware no devolvía IDs y ESTADO no tenía ACK. La actualización 1.1 descrita abajo incorpora ambas capacidades.
- SQLite requiere una corrida asociada explícitamente; no hay API móvil de histórico, experimentos ni inferencia Random Forest. No se crearon endpoints ni botones para aparentar esas capacidades.
- No se dispone de un teléfono/emulador Android ni acceso administrativo EMQX verificado. La conectividad Python observada no demuestra autorización ni funcionamiento físico.

## Tecnología y arquitectura

Flutter está expresamente incluido en la guía y permite compilar para Android con una interfaz compartida. `mqtt_client` implementa MQTT 3.1.1, QoS 1 y WSS. Se contrastaron [la documentación del paquete](https://pub.dev/documentation/mqtt_client/latest/) y [la API MqttServerClient](https://pub.dev/documentation/mqtt_client/latest/mqtt_server_client/MqttServerClient-class.html): WSS se activa con `useWebSocket` y URL `wss://`; el indicador `secure` corresponde a TCP y no se utiliza para WSS.

```text
Arduino Nano ─ USB/Serial ─ puente Python ─ WSS/TLS ─ EMQX
                                                    ├─ Flutter Android
                                                    ├─ Streamlit
                                                    └─ registrador SQLite
Nodos virtuales existentes ─ WSS/TLS ────────────────┘
```

La app tiene su propia conexión y no necesita que Streamlit esté abierto. El ordenador con el puente sí es necesario para alcanzar el Arduino por USB. El teléfono necesita acceso a Internet, no conexión USB permanente al ordenador.

Se usa `ChangeNotifier` con `ListenableBuilder` del SDK. Un repositorio inyectable concentra conexión, temporizadores, límites y comandos; el transporte y almacenamiento seguro se sustituyen por fakes en pruebas de negocio.

```text
mobile/secado_iot_app/
├── android/                 Manifest, Kotlin, Gradle, icono vectorial y política de red
├── lib/core/                Configuración fija, política de comandos, secretos y tema
├── lib/data/models/         Telemetría, estados de comandos y eventos
├── lib/data/mqtt/            Transporte WSS MQTT 3.1.1
├── lib/data/repositories/    Sesión, reconexión, validación y seguimiento
├── lib/features/            Dashboard, monitoreo, control, alertas y configuración
├── lib/shared/              Componentes visuales
├── test/                    Datos, repositorio, widgets y WSS local real
├── integration_test/        Arranque Android, pendiente de dispositivo
├── tool/verify.sh            Verificación reproducible en ruta temporal ASCII
├── pubspec.yaml / lock      Dependencias y resolución utilizada
└── README.md                Instalación, credenciales, ejecución y demostración
```

## Funcionalidades

Las cinco pantallas tienen navegación inferior y selector de nodo común. La paleta combina verde oscuro, café y crema. El Dashboard muestra conexión EMQX, actividad del nodo y origen por separado. Las mediciones opcionales ausentes dicen «No disponible»; no se generan lecturas ficticias.

Los gráficos usan tiempo real como eje horizontal, distinguen temperaturas ambiental/grano, humedad y consigna; interrumpen segmentos ante valores ausentes o intervalos mayores de 15 s. La aplicación conserva hasta 300 lecturas por nodo, 200 eventos y 100 comandos en memoria; no persiste datos experimentales ni simula consultar SQLite.

Se rechazan JSON corrupto, tipos/rangos inválidos, timestamps sin zona o fechas imposibles, nodos incompatibles y duplicados. Se acepta una secuencia menor con timestamp nuevo como posible reinicio y se registra el evento. En mensajes antiguos sin secuencia se usa el timestamp para detectar duplicados; no se inventa una secuencia cero. Se tolera hasta 2 minutos de desfase futuro al parsear, pero una lectura adelantada más de 5 s no habilita controles. Para control se requieren timestamp y recepción no retenida recientes (15 s).

Las alertas calculadas por el teléfono se etiquetan «Local». Los eventos del puente y las líneas conocidas del firmware se identifican por origen. Se omite contenido arbitrario de respuestas y detalles de excepciones para evitar revelar secretos. No se implementan notificaciones ni servicios en segundo plano. Al suspender la app se desconecta y revoca el control; la reconexión al regresar no rehabilita permisos de sesión.

## Contrato MQTT

| Tópico | Flujo | QoS / retención | Contenido |
|---|---|---|---|
| `secado/<node_id>/telemetria` | Puente o publicador → app | 1; publicación existente no retenida | Variables, timestamp, secuencia opcional, modo y origen |
| `secado/<node_id>/estado` | Puente → app | 1; estado retenido | `estado`, timestamp y datos del puente |
| `secado/<node_id>/cmd` | Operador → puente | 1, `retain=false` | `command`, `request_id` UUID |
| `secado/<node_id>/ack` | Puente → app | 1, sin retención | Aceptación de envío correlacionada o línea ACK/ERR serial |

Host fijo `cafes.duckdns.org`, puerto 443, ruta `/mqtt`, MQTT 3.1.1, keepalive inicial 60 s. Client ID `movil-` más 16 caracteres aleatorios por sesión. Se suscriben exactamente los tres tópicos de recepción de cada nodo configurado (15 tópicos); nunca `cmd` ni comodines de descubrimiento. Diagnóstico solo considera confirmadas las suscripciones con SUBACK.

## Comandos y confirmación

Lista blanca móvil: `MODO:MONITOREO`, `MODO:CONTROL`, `SP:10..50`, `VENT:0..255`, `ESTADO`, `PARAR`. Cada aplicación requiere confirmación explícita. La validez del ventilador depende del modo **reportado**, no del selector de modo deseado. Solo existe una solicitud móvil activa; se deshabilitan pulsaciones repetidas. No se controla el calefactor.

```text
Pendiente → Publicado → Aceptado por puente → Confirmado por Arduino
                         └──────── Rechazado / Error / Timeout
```

**Actualización 1.1:** el puente asocia cada solicitud MQTT a un ID serial aleatorio de 32 caracteres. Transmite `REQ,<wire_id>,<command>`. El firmware devuelve `ACK:...|request_id=<wire_id>` o `ERR:...|request_id=<wire_id>`. El puente restaura el `request_id` original, añade `command`, `source=firmware`, `correlated=true` y fase `applied` o `rejected`. La app exige coincidencia de nodo, ID y comando. El recibo `source=bridge`, `phase=forwarded` no confirma ejecución.

La correlación no depende del orden ni de que exista una sola solicitud en el puente: identifica correctamente comandos concurrentes de Android y Streamlit. ERR espontáneos de sensores no heredan ID. ACK desconocidos, duplicados o de más de 30 s no se correlacionan. El mapa está limitado a 256 entradas. Los clientes conservan timeout: Flutter 12 s y Streamlit 15 s. No se reenvían órdenes al reconectar.

ESTADO devuelve su línea de estado y un ACK transaccional adicional. Los comandos seriales legados siguen siendo compatibles. Un firmware anterior no reconoce los nuevos sobres; es necesario cargar el sketch actualizado. No se atribuye éxito a sus respuestas sin ID.

La app permite consultar ESTADO y emitir PARAR a un nodo físico configurado cuando el operador está conectado, aun sin telemetría. Para habilitar un modo sin lecturas, exige una respuesta correlacionada del dispositivo de menos de 15 s. Esto permite iniciar el Nano, que arranca con telemetría apagada. Consigna y PWM siguen requiriendo lecturas recientes; PWM exige MONITOREO reportado. La autorización y el bloqueo de simuladores se mantienen.

Streamlit también espera el ACK correlacionado antes de iniciar/pausar/reanudar corridas. Rechazo o timeout no cambian la corrida. Se evita bloquear el hilo de red paho al publicar una respuesta dentro de un callback.

El sketch conserva watchdog, rangos, sensores, salidas y `ENABLE_HEATER=0`. Una trama que desborda el buffer se descarta completa. «Confirmado por Arduino» acredita procesamiento por el manejador del dispositivo, no verificación eléctrica del actuador. Protocolo, compilación y carga: [firmware_protocol.md](firmware_protocol.md).

## Seguridad y permisos EMQX

**Las ACL no se instalaron ni se declaran verificadas.** Para crear una cuenta y configurar sus reglas, consulta [la guía de operador](emqx_operador.md). Flutter inicia como Monitor. No existe edición accidental de endpoint/TLS ni un selector visual que conceda privilegios. El control exige una compilación explícita con `MQTT_ACL_VERIFIED=true`, usuario de operador configurado, conexión autenticada con credenciales completas de esa cuenta y habilitación manual para la sesión. Estos controles locales no reemplazan las ACL del broker.

El administrador debe revisar las fuentes/reglas existentes, conservar permisos del puente y registrador, habilitar autenticación de aplicaciones y aplicar permisos mínimos. Se recomienda negar toda operación no permitida para las cuentas móviles, sin alterar arbitrariamente otras cuentas. La evaluación depende del orden y de las fuentes de autorización activas; consultar [la guía oficial de seguridad EMQX](https://docs.emqx.com/en/emqx/latest/guides/access-control/security-checklist.html).

| Cuenta de aplicación | Permitir suscripción | Permitir publicación | Denegar |
|---|---|---|---|
| Monitor móvil | `telemetria`, `estado`, `ack` de secador_01 y sim1..sim4 | Ninguna | Todo publish y tópicos fuera de esa lista |
| Operador móvil | Los mismos 15 tópicos exactos | Solo `secado/secador_01/cmd`, QoS 1, sin retain | `cmd` de simuladores/otros nodos y escritura de telemetría/ACK/estado |
| Puente físico (existente) | Su `cmd` | Sus `telemetria/estado/ack` | Mantener alcance por nodo; estado necesita retain |
| Publicador virtual (existente) | Ninguna | Solo `telemetria` de sim1..sim4 | Todos los comandos físicos |

Procedimiento pendiente para el administrador:

1. Identificar versión y esquema de autenticación/autorización de EMQX; respaldar reglas actuales. Crear cuentas de aplicación distintas de la cuenta administrativa.
2. Aplicar la tabla en el mecanismo existente (por ejemplo base interna del broker). Asegurar que ninguna regla previa o fuente alternativa permita publicaciones a cuentas Monitor.
3. Borrar mensajes retenidos de comandos antiguos usando administración autorizada y definir rechazo de retain para operadores. No probar comandos contra el Arduino de producción.
4. En banco aislado con el puerto serial desconectado, verificar que Monitor recibe los 15 tópicos y no puede publicar en `cmd`; verificar que Operador solo publica en su nodo. Con MQTT 3.1.1 un PUBACK por sí solo no prueba autorización: revisar los eventos de autorización de EMQX y que no exista entrega al suscriptor testigo.
5. Comprobar que una cuenta distinta no puede falsificar ACK/estado/telemetría, que una contraseña inválida es rechazada y que los clientes Python conservan acceso.
6. Registrar usuario, reglas, fecha, resultados y evidencia sanitizada; entonces construir la variante de operador descrita en el README móvil. Si cambian cuenta o permisos, volver a verificar.

### Matriz de mecanismos

| Mecanismo | Amenaza mitigada | Ubicación | Prueba / resultado |
|---|---|---|---|
| WSS, cadena y nombre de servidor validados | Interceptación y servidor impostor | `lib/data/mqtt/mqtt_transport.dart` | WSS local real: conexión positiva, CA desconocida y hostname incorrecto rechazados |
| Credenciales protegidas por Android | Lectura casual de secretos | `lib/core/security/credentials.dart`, Manifest | Implementado; cifrado efectivo en teléfono NO VERIFICADO |
| Sin logs MQTT ni excepciones crudas | Filtración por diagnóstico | Transporte y repositorio | Test de error sanitizado pasa |
| Solo lectura por defecto y revocación | Comando involuntario o sesión abandonada | `command_policy.dart`, repositorio, Ajustes | Tests de autorización, desconexión y simulación pasan |
| ACL en broker | Escalada de privilegios y falsificación | Configuración administrativa externa | BLOQUEADO: requiere administrador, pendiente de instalar/verificar |
| Lista blanca y rangos | Inyección de órdenes y parámetros inseguros | Política móvil y puente Python | Tests de rangos, comando multilínea y modos pasan |
| Confirmación humana y una solicitud activa | Doble pulsación y cambios accidentales | Control y repositorio | Duplicado bloqueado; diálogo implementado |
| UUID, no retain, no reenvío | Reejecución de comandos | Transporte/repositorio/puente | Test WSS inspecciona QoS1/retain=false; tests Python de retained y deduplicación pasan |
| Aceptación separada de ejecución | Falsa confirmación del actuador | Modelo y repositorio | ACK sin ID no confirma; timeout probado |
| Backoff y limpieza | Saturación/conexiones repetidas | Repositorio y transporte | Reconexión probada; límites de recursos verificados en tests |
| Límites y rechazo de datos | Agotamiento de memoria/datos engañosos | Modelos y repositorio | Tests de rangos, duplicados, timestamp y memoria pasan |
| Watchdog y calefactor deshabilitado existentes | Riesgo por pérdida de control | Firmware 1.1, protecciones conservadas | Inspección del código; protección física NO VERIFICADA |

## Validación ejecutada

Herramientas instaladas temporalmente: Flutter 3.47.9 y Dart 3.13.7 en `/tmp/lab11-flutter`, JDK 21 completo en `/tmp/lab11-jdk21`. Android SDK existente en `/home/pandaman/Android/Sdk`; Gradle resuelve sus componentes de compilación. El SDK Flutter no estaba instalado al comenzar.

La primera compilación con Java 25 falló porque esa instalación solo tenía JRE y no `javac`; se corrigió utilizando JDK 21 completo. El analizador de Flutter presenta un fallo LSP al procesar la ruta con `AÑO`; el mismo código se analizó en `/tmp/lab11-check`. El script `tool/verify.sh` reproduce ese procedimiento y recupera el APK.

| Verificación | Resultado real y alcance |
|---|---|
| `flutter pub get` | VERIFICADO: dependencias resueltas; lockfile incluido |
| `flutter analyze` | VERIFICADO en copia ASCII idéntica; sin incidencias en la ejecución de referencia |
| `flutter test` | VERIFICADO: **44 passed**; fixtures y widgets no sustituyen Android real |
| WSS local | Conexión, SUBACK, recepción, publicación QoS1 sin retain, autenticación negativa, CA desconocida y hostname incorrecto |
| Regresión `.venv/bin/python -m pytest tests/ -v` | VERIFICADO: 64 passed; inicialmente 40 passed |
| EMQX desde Python | VERIFICADO: `check_connection --timeout 5 --node-id secador_01` conectó a cafes.duckdns.org:443 sin publicar |
| EMQX desde Android | NO VERIFICADO: no dispositivo Android conectado |
| `flutter devices` | Solo Linux y Chrome; no Android |
| `integration_test/app_test.dart` | BLOQUEADO por ausencia de dispositivo/emulador; preparado, no ejecutado |
| Firmware/actuadores físicos | NO VERIFICADO; no se enviaron comandos físicos |

### Resultados finales

- `flutter analyze`: **No issues found!**, exit 0, sobre copia ASCII cuyo `lib/` y `test/` se compararon con los originales mediante `diff -qr` sin diferencias.
- `flutter test --reporter expanded`: **44 tests pasaron**, exit 0. Incluye 4 casos con transporte WSS real en loopback, validación de fechas, reconexión automática, controles, widgets de simulación, alerta crítica y error.
- `.venv/bin/python -m pytest tests/ -v`: **64 passed**, exit 0.
- `JAVA_HOME=/tmp/lab11-jdk21 ANDROID_HOME=/home/pandaman/Android/Sdk /tmp/lab11-flutter/bin/flutter build apk --debug`: **APK generado**, última compilación incremental en 10.9 s, exit 0.
- APK: `mobile/secado_iot_app/build/app/outputs/flutter-apk/app-debug.apk` (161,138,968 bytes). Es un artefacto debug local, ignorado por Git.
- SHA-256: `5cdbcf4fcdec71058797544b9564e4125f421f462b8e755ef8d98204a244e4b6`.
- `apksigner verify --verbose`: **Verifies**, firma APK v2 válida; no equivale a firma de distribución para tienda.
- `aapt2 dump badging`: paquete `pe.edu.unt.secado_iot_app`, versión `1.1.0`, mínimo Android API **24**, target **36**, permisos Internet y estado de red presentes.
- Firmware Nano compilado: 17462 bytes de programa y 1318 bytes de RAM estática. HEX local en `firmware/arduino_secado/build/arduino_secado.ino.hex`, sin cargar. Los tests nativos ejecutan el manejador del sketch y el recorrido puente → sketch → ACK.
- `git diff --check`: sin errores. No se ejecutó `integration_test` por ausencia de Android.

Comandos exactos para continuar en este equipo (los SDK de `/tmp` son temporales):

```bash
export PATH="/tmp/lab11-flutter/bin:$PATH"
export JAVA_HOME=/tmp/lab11-jdk21
export ANDROID_HOME=/home/pandaman/Android/Sdk
cd mobile/secado_iot_app
flutter devices
# Con un teléfono Android autorizado por USB:
flutter run
# Verificar y reconstruir, incluso desde la ruta con AÑO:
FLUTTER_BIN=/tmp/lab11-flutter/bin/flutter ./tool/verify.sh
```


## Criterios de aceptación

«VERIFICADO» en tests significa el alcance indicado; no implica demostración física.

| Criterio | Estado | Evidencia / alcance |
|---|---|---|
| Arranque Android sin errores | NO VERIFICADO | Widget de arranque probado; integración Android pendiente |
| Conexión MQTT WSS | VERIFICADO local / NO VERIFICADO Android-EMQX | Transporte MQTT real con fixture TLS; conexión Python a EMQX |
| Datos de publicador autorizado | NO VERIFICADO en producción | Fixture MQTT recibe payload; falta cuenta y publicador para demo Android |
| Tres variables principales | VERIFICADO | Parser y widget de mediciones |
| Gráficas automáticas | VERIFICADO en implementación | Rebuild por notificador; visualización en teléfono pendiente |
| Identificación de simulación | VERIFICADO | Parser y widget con distintivo |
| Selección de nodo válido | VERIFICADO | Lista explícita y validación de tópico/nodo |
| Comandos solo autorizados | VERIFICADO local / BLOQUEADO broker | Tests de políticas; ACL reales pendientes |
| Límites físicos y modo PWM | VERIFICADO en tests | Política móvil y tests Python de whitelist/rangos; hardware pendiente |
| Distinguir publicación, aceptación y ejecución | VERIFICADO | Estados y tests: ACK sin correlación nunca confirma; ACK 1.1 coincidente sí confirma |
| Desconexiones y errores | VERIFICADO en tests | Fakes de conexión y widget de error; backoff implementado |
| Validación TLS | VERIFICADO | WSS local real, CA desconocida y hostname incorrecto rechazados |
| No exponer credenciales | VERIFICADO por código / NO VERIFICADO almacenamiento Android | Campos ocultos, diagnóstico sanitizado, secure storage, sin secretos embebidos |
| Pruebas ejecutadas | VERIFICADO | Suite Flutter y 64 tests Python; ver resultados finales |
| Sin regresiones Python | VERIFICADO | Suite completa pytest pasa |
| Construcción y demostración reproducibles | VERIFICADO documentalmente | README, lockfile y script; instalación Android pendiente |

## Demostración y evidencias

1. Instalar SDK/JDK y ejecutar las verificaciones descritas en el [README móvil](../mobile/secado_iot_app/README.md).
2. Conectar un Android con depuración USB: `flutter devices`, `flutter run -d ID`. Ejecutar el smoke test de integración con ese ID.
3. Guardar en Android credenciales Monitor, conectar y revisar SUBACK. Sin publicar desde el móvil, ejecutar el publicador existente `python -m src.mqtt.virtual_nodes_cli --interval 2` con credenciales autorizadas en el ordenador.
4. Seleccionar sim1: comprobar distintivo, tres variables, gráficos y controles deshabilitados. Detener el publicador y observar stale tras 15 s; desconectar red y observar error/reconexión.
5. Para datos físicos, iniciar un único puente `python -m src.mqtt.bridge_cli --port /dev/ttyUSB0 --node-id secador_01`. Seleccionar el nodo físico y verificar timestamp/origen.
6. Solo tras completar ACL, usar variante Operador, habilitar sesión y confirmar una acción de banco. Comprobar el JSON/UUID, aceptación del puente y confirmación correlacionada del Arduino actualizado. Revisar físicamente el resultado sin confundirlo con el estado de la interfaz.
7. Capturar evidencias reales según [la lista preparada](evidencias/lab11/README.md). No hay capturas de teléfono ni fotografías fabricadas.

## Cumplimiento de las actividades académicas

| Actividad de la guía | Entrega | Estado |
|---|---|---|
| Extensión móvil de funcionalidades MQTT | Proyecto Android Flutter, WSS, cinco pantallas, telemetría, gráficos, control validado, alertas y diagnóstico | Implementada y probada localmente; demostración Android/hardware pendiente |
| Avance de mecanismos de seguridad | TLS comprobado, secretos en almacenamiento seguro, políticas, solo lectura, rechazo retained, deduplicación, pruebas y procedimiento ACL | Implementado en código y tests; ACL reales y verificación en dispositivo pendientes |

No se afirma cumplimiento físico integral: faltan instalación Android, prueba Android→EMQX con cuenta autorizada, permisos verificados y demostración del montaje. La correlación del procesamiento se implementó en el protocolo 1.1 y se verificó con el manejador nativo del sketch y tests de la app; falta comprobarla en el montaje físico.
