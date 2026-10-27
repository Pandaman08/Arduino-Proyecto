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
