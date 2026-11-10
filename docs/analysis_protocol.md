# Fase 6: indicadores y análisis

Los indicadores se calculan en `src/analysis/indicators.py` sobre mediciones
SQLite ordenadas por `timestamp_utc`. Los intervalos entre lecturas se usan como
ponderación, por lo que una lectura no representa automáticamente un minuto
completo.

- Duración: `ended_at - started_at`, únicamente para corridas finalizadas con
  `completion_criterion` registrado.
- Pérdida de masa: `(peso_inicial - peso_final) / peso_inicial * 100`.
- Error térmico: promedio ponderado de `abs(t_grano - referencia)`.
- Tiempo en rango: tiempo con `abs(t_grano - referencia) <= 0.8 °C` dividido
  entre el tiempo válido.
- Humedad y temperatura promedio: promedio ponderado por duración válida.
- Energía: estimación `potencia_nominal * factor_de_actuador * tiempo`; el PWM
  del ventilador no se presenta como potencia medida.
- Error del Random Forest: compara `predicted_remaining_hours` con el tiempo
  real hasta `ended_at_utc`; sin finalización real queda no disponible.

Las comparaciones pareadas usan exclusivamente `pair_id`. Las independientes
no emparejan por orden de filas. Se reportan media, mediana, desviación estándar,
diferencia, cambio porcentual y dirección. Las pruebas incluyen t pareada,
Wilcoxon, Welch y Mann-Whitney según el diseño y el tamaño disponible; Shapiro
se calcula sobre diferencias pareadas cuando hay al menos tres valores no
constantes.

Un p-valor no se transforma automáticamente en una afirmación de mejora. Con
muestras pequeñas se muestran limitaciones y estadísticas descriptivas. Los
experimentos `simulado` se excluyen del análisis real por defecto y solo se
incluyen si el usuario activa la demostración.
