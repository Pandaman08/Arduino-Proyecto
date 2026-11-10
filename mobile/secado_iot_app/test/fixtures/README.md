Certificado y clave PÚBLICOS de prueba para el servidor WSS efímero en localhost.
No son credenciales de aplicación ni deben usarse fuera de los tests.
El certificado es autofirmado: la aplicación de producción debe rechazarlo.
La prueba positiva confía explícitamente en esta CA solo dentro de HttpOverrides.runZoned.
Regenerar si caduca:

```bash
openssl req -x509 -newkey rsa:2048 -nodes -keyout localhost-key.pem -out localhost-cert.pem -days 3650 -subj '/CN=localhost' -addext 'subjectAltName=DNS:localhost'
```
