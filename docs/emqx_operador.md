# Crear y verificar una cuenta de operador MQTT

Una cuenta que conecta al broker no es necesariamente operador. La cuenta administrativa del Dashboard y los usuarios MQTT son identidades distintas. No se necesita superusuario MQTT para operar el secador.

## Comprobar una cuenta existente

En el Dashboard administrativo de tu instalación, busca el **Client ID** que muestra la app en Ajustes. Revisa su username y las reglas efectivas de autorización de esa cuenta. Conexión exitosa o un PUBACK no prueban permiso de control. No compartas contraseñas por el chat ni las incluyas en Git.

## Crear la cuenta

Necesitas acceso administrativo al broker; una cuenta MQTT normal no puede crear usuarios. Abre el Dashboard mediante la URL administrativa ya configurada por tu equipo, que es distinta de `/mqtt`.

1. En **Access Control → Authentication**, revisa el autenticador existente. Si usa contraseña y **Built-in Database**, abre su gestión de usuarios. Si usa otra fuente, crea allí la identidad.
2. Si todavía no hay autenticador, configura **Password-Based → Built-in Database** con identificación por **username**. Conserva acceso del puente, publicadores y registrador antes de activar cambios.
3. Crea `secado_operador`, con una contraseña propia y **Superuser desactivado**. Crea también `secado_monitor` si necesitas una cuenta separada de observación. No crees un usuario del Dashboard como sustituto de un cliente MQTT.

Referencia: [autenticación con base interna de EMQX](https://docs.emqx.com/en/emqx/latest/guides/access-control/authn/mnesia.html). Los rótulos concretos pueden variar según la versión instalada.

## Asignar permisos

En **Access Control → Authorization**, revisa las fuentes actuales. Para la fuente **Built-in Database**, abre **Permissions → Username** y configura reglas para `secado_operador` en este orden:

| Acción | Tópico | Permiso |
|---|---|---|
| Publish | `secado/secador_01/cmd` | Allow, QoS 1, retain=false |
| Subscribe | `secado/secador_01/telemetria`, `estado`, `ack` | Allow, QoS 1; un tópico completo por regla |
| Subscribe | Los mismos sufijos para cada nodo `sim1..sim4` | Allow, QoS 1; sin publicación de comandos |
| Publish & Subscribe | `#` | Deny, al final, solo para esta cuenta |

Hay ejemplos completos, sin contraseñas: [operador](emqx/operador.rules.example.json) y [monitor](emqx/monitor.rules.example.json). Son cuerpos de reglas por usuario para adaptar al Dashboard o a la API de tu versión; no se aplican automáticamente. El monitor recibe los mismos 15 tópicos y no puede publicar.

Revisa reglas anteriores, caché y fuentes alternativas para que ninguna conceda acceso adicional. Conserva las reglas del puente: necesita suscribir `cmd` y publicar telemetría, ACK y estado; el estado retenido sigue siendo válido para esa cuenta. Documentación de [permisos por usuario en EMQX](https://docs.emqx.com/en/emqx/latest/guides/access-control/authz/mnesia.html).

## Verificar antes de habilitar Android

Realiza las pruebas en banco, con el puente físico detenido o el Arduino desconectado:

- Operador recibe telemetría/estado/ACK y puede publicar en su `cmd`; confirma entrega con un suscriptor testigo y consulta los eventos de autorización del broker.
- Monitor no puede publicar comandos. Operador no puede escribir telemetría/ACK, publicar con retain ni mandar a otro nodo.
- Usuario sin permiso y contraseña incorrecta se rechazan según su caso. Un PUBACK MQTT 3.1.1 por sí solo no demuestra autorización.
- Puente y publicadores existentes siguen funcionando con sus propias credenciales.

Después de verificar y registrar las ACL, construye la variante de operador:

```bash
cd mobile/secado_iot_app
flutter build apk --debug \
  --dart-define=MQTT_ACL_VERIFIED=true \
  --dart-define=MQTT_OPERATOR_USER=secado_operador
```

Estos parámetros no conceden permisos en EMQX. El usuario debe coincidir con la cuenta verificada. Instala ese APK, introduce sus credenciales en **Ajustes**, conecta y activa **Habilitar control en esta sesión**. Las contraseñas nunca se pasan al compilador.

El APK de esta entrega conserva solo lectura porque no se ha accedido a tu administración EMQX ni verificado esas ACL. Su soporte de confirmación 1.1 funciona también en una futura compilación de operador.
