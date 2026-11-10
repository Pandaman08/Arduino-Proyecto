# Auditoría final de Fase 7

## Arquitectura verificada

- Arduino Nano usa Serial USB; el firmware conserva sensores, LEDs, ventilador,
  LCD y modos MONITOREO/CONTROL.
- `src/mqtt/bridge.py` es el único puente físico Serial ↔ EMQX.
- `src/mqtt/recorder.py` persiste telemetría válida solo cuando existe una
  corrida explícitamente asignada.
- `src/persistence/` mantiene SQLite con WAL, claves foráneas, deduplicación y
  recuperación de corridas activas.
- `app.py` consume MQTT con un recurso cacheado, consulta SQLite y separa datos
  simulados de datos reales.
- `src/analysis/` calcula indicadores, comparaciones, pruebas estadísticas y
  reportes.

## Verificaciones realizadas

| Flujo | Evidencia |
|---|---|
| Serial/CSV | Tests de parseo y pruebas del puente con `FakeSerial`. |
| Control MQTT | Tests de comandos permitidos, ACK/ERR y separación del puerto. |
| Persistencia | Tests SQLite de estados, duplicados, origen y recuperación. |
| Indicadores | Tests de masa, duración, intervalos irregulares, energía y faltantes. |
| Estadística | Tests pareados por `pair_id`, independientes y muestras insuficientes. |
| Streamlit | AppTest de las seis secciones sin excepciones. |
| Exportación | CSV, Excel, PDF y PNG generados correctamente en el entorno virtual. |
| EMQX | Conexión TLS/WSS real verificada en `cafes.duckdns.org:443` con tópico de prueba `secado/fase7_audit/test`; no se enviaron comandos de control. |

La verificación EMQX no valida el hardware Arduino ni la autorización final de
producción. La conexión observada fue anónima porque no había credenciales de
aplicación configuradas en el entorno; se conserva la advertencia y no se
incluyen credenciales en el repositorio.

## Random Forest

El modelo actual usa dataset sintético local, con tres variables de entrada y
`Tiempo_Restante_Horas` como objetivo. La advertencia de incompatibilidad de
scikit-learn se resolvió detectando `InconsistentVersionWarning` y reentrenando
el artefacto local con la versión activa. La evaluación actual es de demostración
y no tiene validez agronómica hasta disponer de etiquetas reales.

Para datos reales se exige `run_id` en `train_from_labeled_runs`, de modo que la
separación de entrenamiento y prueba pueda hacerse por corrida/lote y no por
filas mezcladas temporalmente.

## Pendientes físicos y académicos

- Confirmar sensores y conexiones del montaje real.
- Validar el control del ventilador con una carga protegida.
- Confirmar si existe calefactor y medir su potencia real antes de habilitarlo.
- Ejecutar corridas ANTES/DESPUÉS reales con criterios equivalentes y `pair_id`.
- Registrar humedad interna mediante medición independiente; no inferirla desde
  pérdida de peso.
- Sustituir el dataset sintético por datos reales etiquetados antes de extraer
  conclusiones académicas.
