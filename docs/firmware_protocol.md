# Protocolo del firmware Arduino Nano

El firmware conserva el mapeo existente: DHT22 en D2, DS18B20 en D3, LEDs en
D4/D6/D5, ventilador PWM en D9 y LCD I2C en `0x27` usando A4/A5. El soporte de
relé está desactivado (`ENABLE_HEATER=0`) hasta confirmar físicamente el
hardware; no debe conectarse una carga de red eléctrica para estas pruebas.

## Modos

- `MODO:MONITOREO` o `MODO:ANTES`: activa la línea base. El PWM queda fijo y
  `SP` no modifica los actuadores.
- `MODO:CONTROL` o `MODO:DESPUES`: habilita el control del ventilador con
  histéresis. El sistema actual solo puede enfriar; no se afirma que pueda
  alcanzar una temperatura superior sin calefactor.
- `PARAR`: detiene la telemetría y lleva las salidas a estado seguro.
- `ESTADO`: responde con el modo, actividad, consigna y salidas actuales.

## Comandos

| Comando | Resultado |
|---|---|
| `SP:10..50` | Acepta una consigna válida. En MONITOREO no cambia actuadores. También se acepta `T:` por compatibilidad. |
| `VENT:0..255` | Fija el ventilador solo en MONITOREO. |
| `V`, `A`, `R`, `1`, `2`, `0` | Alias heredados para salidas fijas/LEDs. |
| `D:texto` | Muestra texto en LCD. |

Los comandos aceptados responden `ACK:...`; los inválidos o inseguros responden
`ERR:...`. El puente Python reenvía esas respuestas por el tópico `ack`.

## Telemetría

La trama nueva es:

```text
TEL,seq,t_amb,hum,t_grano,sp,modo,foco,vent
```

Con el relé desactivado, `foco` se reporta como `NA`, no como un valor
inventado. El puente también acepta el CSV legado de tres campos.

## Seguridad

El arranque deja telemetría y actuadores apagados. Se validan sensores, rango de
consigna y temperatura máxima de grano; ante sobretemperatura, sensor inválido
o pérdida del watchdog de control se desactivan las salidas peligrosas. El
watchdog no depende de Internet y el ciclo serial no usa esperas largas ni
`readStringUntil`.

La verificación física pendiente incluye confirmar si el sensor instalado es
DHT22 o DHT21, dirección del LCD, resistencia/pull-up del DS18B20, etapa de
potencia del ventilador, polaridad de LEDs y ausencia/autorización de un relé
de calefactor.

## Extensión transaccional 1.1

Actualización solicitada para correlacionar comandos sin cambiar sensores, salidas,
watchdog ni `ENABLE_HEATER=0`.

```text
MQTT: {"command":"MODO:CONTROL","request_id":"uuid-del-movil"}
Serial enviado por puente: REQ,<wire_id>,MODO:CONTROL
Serial devuelto por Nano: ACK:MODO_CONTROL_APLICADO|request_id=<wire_id>
```

El puente genera un `wire_id` aleatorio de 32 caracteres y conserva una asociación
acotada con el `request_id` MQTT y el comando. No confunde solicitudes concurrentes
de Android y Streamlit ni respuestas fuera de orden. IDs desconocidos, ya usados o
mayores de 30 s no confirman una solicitud. El caché tiene un máximo de 256 entradas
y no es una garantía de ejecución exactamente una vez después de reinicios.

La respuesta MQTT añade `source="firmware"`, `correlated=true`, `phase="applied"`
(o `"rejected"`), `request_id` original y `command`. La aceptación de envío usa
`source="bridge"`, `phase="forwarded"` y no constituye confirmación del Arduino.
La app exige coincidencia de nodo, ID y comando, y rechaza respuestas retenidas.

`REQ,<wire_id>,ESTADO` emite la línea ESTADO existente y después
`ACK:ESTADO_CONSULTADO|request_id=<wire_id>`. Los errores de sensores/watchdog se
siguen emitiendo sin identificador: nunca se atribuyen al comando anterior.

Los comandos seriales antiguos siguen aceptándose y sus respuestas no cambian.
Un firmware anterior no reconoce REQ: hay que cargar el nuevo sketch para obtener
confirmaciones correlacionadas; la app no inventa confirmación cuando falta.
El buffer es de 96 bytes, ID de hasta 36 caracteres alfanuméricos/guion y comando
de hasta 40 caracteres. Una trama desbordada se descarta completa hasta fin de
línea, incluyendo su cola, para evitar interpretar fragmentos como comandos.

Confirmado por Arduino significa que su manejador procesó la orden; no acredita
por sí mismo que el motor, cableado o etapa de potencia hayan actuado físicamente.

## Compilación y carga

Dependencias de biblioteca: DHT sensor library (y Adafruit Unified Sensor),
OneWire, DallasTemperature, LiquidCrystal I2C. En Arduino IDE abre
`firmware/arduino_secado/arduino_secado.ino`, selecciona Arduino Nano, el procesador
correspondiente al bootloader instalado y su puerto. Detén primero el puente para
liberar el puerto; sube el sketch y después reinicia el puente actualizado.

Compilación verificada con Arduino AVR core 1.8.8 y Nano ATmega328P Old Bootloader:

```bash
arduino-cli compile --fqbn arduino:avr:nano:cpu=atmega328old firmware/arduino_secado
```

En este entorno se usaron `/tmp/lab11-arduino-bin/arduino-cli` y
`--config-file /tmp/lab11-arduino.yaml`, con bibliotecas temporales.
Resultado: 17462 bytes de programa (56 %) y 1318 bytes de RAM estática (64 %),
730 bytes disponibles para variables locales. Son cifras de compilación; la
estabilidad de memoria dinámica y la operación real deben validarse en el Nano.

No se cargó el firmware en hardware: no había puerto ttyUSB/ttyACM disponible.
Los tests nativos ejecutan el sketch con dobles de IO e incluyen un recorrido
puente → manejador del sketch → ACK MQTT; no sustituyen la prueba física.
