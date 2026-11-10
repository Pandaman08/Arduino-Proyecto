# Evidencias del Laboratorio 11

No se incluyen capturas de teléfono ni fotografías de hardware: no se ha conectado un dispositivo de demostración.
Tomar manualmente y guardar aquí, sin mostrar credenciales:

| Archivo previsto | Descripción y requisito |
|---|---|
| `01-dashboard-real.png` | Teléfono recibiendo telemetría física; nodo, timestamp y «Datos reales» visibles. |
| `02-monitoreo.png` | Evolución temporal y comparación de consigna con grano. |
| `03-simulacion.png` | sim1 con distintivo «Simulación» y controles bloqueados. |
| `04-comando.png` | Operador autorizado: publicación y aceptación del puente; ejecución sin correlación visible. |
| `05-alertas.png` | Alerta local crítica usando publicador de laboratorio, sin presentar el dato como físico. |
| `06-diagnostico.png` | WSS/TLS, SUBACK y contadores; nunca contraseñas. |
| `07-acl-monitor.png` | Regla EMQX y evidencia de publicación denegada al monitor en un nodo de banco desconectado del Arduino. |
| `08-acl-operador.png` | Cuenta operador restringida y prueba autorizada en banco. |

Registrar fecha, nodo, origen, versión de la app y entorno para cada evidencia.
Los tests WSS usan claves públicas de prueba en `mobile/secado_iot_app/test/fixtures/`; no son credenciales de EMQX.
