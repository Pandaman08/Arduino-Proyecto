# Resultados observados · 2026-11-10 · Protocolo 1.1

- Rama: feature/lab11-flutter-mqtt.
- Flutter 3.47.9 / Dart 3.13.7 / JDK 21.0.13.
- flutter analyze: exit 0, No issues found!, copia ASCII idéntica.
- flutter test: exit 0, 44 pruebas pasan.
- pytest tests/ -q: exit 0, 64 pruebas pasan.
- Pruebas nativas: el manejador real del sketch corre sobre dobles de IO; correlación, ERR espontáneo, compatibilidad legada y desbordamiento verificados. No es hardware.
- AppTest: una corrida no inicia con aceptación del puente, ACK ajeno o retenido. Inicia con confirmación correlacionada. Rechazo y timeout no alteran la corrida.
- flutter build apk --debug: exit 0, APK 1.1.0+2 generado (última compilación 10.9 s).
- APK: mobile/secado_iot_app/build/app/outputs/flutter-apk/app-debug.apk
- APK SHA-256: 5cdbcf4fcdec71058797544b9564e4125f421f462b8e755ef8d98204a244e4b6
- aapt2: versionCode 2, versionName 1.1.0, minSdk 24, targetSdk 36.
- Arduino CLI: compilación Nano Old Bootloader exit 0; AVR core 1.8.8, DHT 1.4.7, Adafruit Unified Sensor 1.1.15, OneWire 2.3.8, DallasTemperature 4.0.6, LiquidCrystal I2C 1.1.2.
- Memoria firmware: 17462 bytes de programa (56 %), 1318 bytes de RAM estática (64 %), 730 bytes para variables locales.
- HEX: firmware/arduino_secado/build/arduino_secado.ino.hex (artefacto local ignorado por Git).
- HEX SHA-256: b50fb023894d2801f9f6af1e30ea873498d78f6de6c1f5adbdfd088d7cb4518a
- Sin puerto ttyUSB/ttyACM disponible. No se cargó firmware ni se probaron actuadores.
- APK de entrega en solo lectura; ACL reales y cuenta operador no verificadas administrativamente.
- Las pruebas automatizadas no envían comandos al broker de producción.

Esta es una transcripción resumida de salidas observadas. Procedimiento y límites: [informe](../../lab11_mobile.md), [firmware](../../firmware_protocol.md) y [operador](../../emqx_operador.md).
