"""Plataforma Streamlit de monitoreo y experimentación IoT.

Streamlit no abre el puerto serial: el puente independiente se encarga de
Arduino y esta interfaz consume MQTT o ejecuta una demostración explícita.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd
import streamlit as st

from src.analysis import calculate_experiment_indicators, compare_experiments, statistical_tests
from src.analysis.reports import comparison_pdf, dataframe_csv, dataframe_excel, line_chart_png
from src.config import CRITICAL_GRAIN_OVERHEAT_THRESHOLD, MODEL_PATH
from src.hardware.serial_manager import generate_simulated_telemetry
from src.ml.model_manager import load_or_train_predictor
from src.persistence import (
    ExperimentManager, ExperimentPhase, ExperimentStatus, GrainType,
    HistoryRepository, MeasurementOrigin, initialize_database,
)
from src.mqtt.streamlit_adapter import create_optional_streamlit_subscriber
from src.services.monitoring import TelemetryProcessor
from src.ui import CUSTOM_CSS, render_footer, render_header


st.set_page_config(page_title="Secado IoT | Café y Cacao", page_icon="☕", layout="wide")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


@st.cache_resource(show_spinner="Inicializando base de datos...")
def get_database():
    return initialize_database(recover_interrupted=True)


@st.cache_resource(show_spinner="Cargando Random Forest...")
def get_predictor():
    return load_or_train_predictor()


@st.cache_resource(show_spinner="Preparando consumidor MQTT...")
def get_mqtt():
    return create_optional_streamlit_subscriber()


database = get_database()
manager = ExperimentManager(database)
history_repo = HistoryRepository(database)
predictor, model_eval = get_predictor()
mqtt_subscriber, mqtt_status = get_mqtt()
processor = TelemetryProcessor(predictor)


def init_state() -> None:
    defaults: dict[str, Any] = {
        "page": "Dashboard general", "demo_mode": False, "selected_node": "secador_01",
        "telemetry": [], "last_ack": None, "last_state": None, "last_error": None,
        "invalid_messages": 0, "pending_command": None, "sim_sequence": 0,
        "sim_grain": 28.5, "current_experiment_id": None, "command_log": [],
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def poll_mqtt() -> None:
    if mqtt_subscriber is None:
        return
    for message in mqtt_subscriber.poll():
        topic = message.pop("_topic", "")
        if topic.endswith("/ack"):
            st.session_state.last_ack = message
            st.session_state.command_log.append({"timestamp": message.get("timestamp", utc_now()), **message})
            pending = st.session_state.pending_command
            if pending and message.get("accepted") and pending.get("request_id") == message.get("request_id"):
                if pending["action"] == "start":
                    try:
                        manager.start(pending["experiment_id"])
                        st.session_state.current_experiment_id = pending["experiment_id"]
                    except (KeyError, ValueError) as error:
                        st.session_state.last_error = str(error)
                elif pending["action"] == "pause":
                    try:
                        manager.pause(pending["experiment_id"])
                    except (KeyError, ValueError) as error:
                        st.session_state.last_error = str(error)
                elif pending["action"] == "resume":
                    try:
                        manager.resume(pending["experiment_id"])
                    except (KeyError, ValueError) as error:
                        st.session_state.last_error = str(error)
                st.session_state.pending_command = None
        elif topic.endswith("/estado"):
            st.session_state.last_state = message
        elif topic.endswith("/telemetria"):
            message["_received_at"] = utc_now()
            st.session_state.telemetry.append(message)
            st.session_state.telemetry = st.session_state.telemetry[-300:]
            st.session_state.selected_node = message.get("node_id", st.session_state.selected_node)


def publish_command(command: str, action: Optional[str] = None, experiment_id: Optional[int] = None) -> bool:
    if mqtt_subscriber is None or not mqtt_subscriber.is_connected:
        st.warning("MQTT no está conectado. Activa MQTT_STREAMLIT_ENABLED y verifica EMQX.")
        return False
    request_id = uuid.uuid4().hex[:12]
    try:
        mqtt_subscriber.publish_command(st.session_state.selected_node, command, request_id)
    except Exception as error:
        st.session_state.last_error = str(error)
        st.error(f"No se pudo enviar el comando: {error}")
        return False
    st.session_state.pending_command = {"request_id": request_id, "command": command, "action": action, "experiment_id": experiment_id}
    return True


def demo_reading() -> None:
    current = st.session_state.telemetry[-1] if st.session_state.telemetry else None
    previous = float(current.get("t_grano", st.session_state.sim_grain)) if current else st.session_state.sim_grain
    reading = generate_simulated_telemetry(23.0, previous)
    st.session_state.sim_sequence += 1
    st.session_state.sim_grain = reading.temp_grano
    payload = {
        "node_id": "sim1", "timestamp": utc_now(), "sequence": st.session_state.sim_sequence,
        "t_amb": reading.temp_ambiente, "hum": reading.humedad_ambiente,
        "t_grano": reading.temp_grano, "sp": 23.0, "modo": "MONITOREO",
        "simulado": True, "version": "1.0",
    }
    st.session_state.telemetry.append(payload)
    st.session_state.telemetry = st.session_state.telemetry[-300:]


def current_frame() -> Optional[dict]:
    node = st.session_state.selected_node
    candidates = [item for item in st.session_state.telemetry if item.get("node_id") == node]
    return candidates[-1] if candidates else (st.session_state.telemetry[-1] if st.session_state.telemetry else None)


def frame_df() -> pd.DataFrame:
    rows = [item for item in st.session_state.telemetry if "t_grano" in item]
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    return df.sort_values("timestamp")


def metric_value(value: Any, suffix: str = "") -> str:
    return "No disponible" if value is None else f"{value}{suffix}"


def render_sidebar() -> None:
    st.sidebar.title("☕ Secado IoT")
    st.sidebar.caption("Plataforma de monitoreo experimental")
    st.sidebar.radio("Sección", [
        "Dashboard general", "Gestión de experimentos", "Control de hardware",
        "Historial", "Comparación ANTES/DESPUÉS", "IA y diagnóstico",
    ], key="page")
    st.sidebar.divider()
    st.sidebar.selectbox("Nodo", ["secador_01", "secador_02", "secador_03", "secador_04", "secador_05", "sim1", "sim2", "sim3", "sim4"], key="selected_node")
    st.sidebar.checkbox("Modo demostración (datos simulados)", key="demo_mode")
    mqtt_online = bool(mqtt_subscriber and mqtt_subscriber.is_connected)
    st.sidebar.markdown(f"**EMQX:** {'🟢 Conectado' if mqtt_online else '🔴 No disponible'}")
    st.sidebar.caption(mqtt_status if mqtt_subscriber is not None else "Deshabilitado por configuración")
    if st.sidebar.button("Actualizar", width="stretch"):
        st.rerun()


def render_dashboard() -> None:
    st.header("Dashboard general")
    frame = current_frame()
    if st.session_state.demo_mode:
        if st.button("▶ Generar lectura simulada", type="primary"):
            demo_reading(); st.rerun()
        st.info("Modo demostración activo: los datos están etiquetados como simulados y no son mediciones experimentales reales.")
    cols = st.columns(4)
    cols[0].metric("EMQX", "Conectado" if mqtt_subscriber and mqtt_subscriber.is_connected else "No disponible")
    cols[1].metric("Puente Python", "Activo" if mqtt_subscriber and mqtt_subscriber.is_connected else "No disponible")
    cols[2].metric("Arduino Nano", "Telemetría recibida" if frame and not frame.get("simulado") else "No disponible")
    cols[3].metric("Nodo", st.session_state.selected_node)
    cols = st.columns(4)
    cols[0].metric("Temp. ambiente", metric_value(frame.get("t_amb") if frame else None, " °C"))
    cols[1].metric("Humedad ambiente", metric_value(frame.get("hum") if frame else None, " %"))
    cols[2].metric("Temp. grano", metric_value(frame.get("t_grano") if frame else None, " °C"))
    cols[3].metric("Setpoint", metric_value(frame.get("sp") if frame else None, " °C"))
    active = None
    if st.session_state.current_experiment_id:
        try:
            active = manager.get_experiment(st.session_state.current_experiment_id)
        except KeyError:
            active = None
    if active:
        st.caption(f"Corrida actual: **{active.run_code}** | Grano: {active.grain_type} | Fase: {active.phase.upper()} | Estado: {active.status}")
    predicted = None
    if frame:
        try:
            predicted = predictor.predict(float(frame["t_amb"]), float(frame["hum"]), float(frame["t_grano"]))
        except (KeyError, TypeError, ValueError, RuntimeError):
            predicted = None
    elapsed = None
    if active and active.started_at_utc:
        try:
            elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(active.started_at_utc.replace("Z", "+00:00"))).total_seconds() / 3600
        except ValueError:
            elapsed = None
    cols = st.columns(4)
    cols[0].metric("Ventilador", metric_value(frame.get("vent") if frame else None, " PWM"))
    cols[1].metric("Calefactor", metric_value(frame.get("foco") if frame else None))
    cols[2].metric("Tiempo transcurrido", metric_value(round(elapsed, 2) if elapsed is not None else None, " h"))
    cols[3].metric("Predicción restante", metric_value(round(predicted, 2) if predicted is not None else None, " h"))
    if frame:
        origin = "SIMULADO" if frame.get("simulado") else "REAL"
        st.caption(f"Origen de la última lectura: **{origin}** | Modo: {frame.get('modo', 'No disponible')} | Secuencia: {frame.get('sequence', 'No disponible')}")
        if frame.get("t_grano", 0) > CRITICAL_GRAIN_OVERHEAT_THRESHOLD:
            st.error("Alerta: temperatura del grano por encima del límite crítico.")
    else:
        st.info("No hay telemetría disponible.")
    df = frame_df()
    if not df.empty:
        st.subheader("Telemetría en tiempo real")
        chart = df.set_index("timestamp")
        c1, c2 = st.columns(2)
        c1.line_chart(chart[["t_amb", "t_grano"]].rename(columns={"t_amb": "Ambiente °C", "t_grano": "Grano °C"}))
        c2.line_chart(chart[["hum"]].rename(columns={"hum": "Humedad %"}))
        if "sp" in chart:
            st.line_chart(chart[["t_grano", "sp"]].rename(columns={"t_grano": "Grano °C", "sp": "Setpoint °C"}))


def render_experiments() -> None:
    st.header("Gestión de experimentos")
    with st.form("experiment_form"):
        c1, c2, c3 = st.columns(3)
        run_code = c1.text_input("Código de corrida")
        grain = c2.selectbox("Tipo de grano", [GrainType.CAFE.value, GrainType.CACAO.value])
        phase = c3.selectbox("Fase", [ExperimentPhase.ANTES.value, ExperimentPhase.DESPUES.value])
        batch = c1.text_input("Lote")
        pair = c2.text_input("Pareja experimental (opcional)")
        origin = c3.selectbox("Origen", [MeasurementOrigin.REAL.value, MeasurementOrigin.SIMULADO.value])
        weight = c1.number_input("Peso inicial (g)", min_value=0.0, value=0.0)
        moisture = c2.number_input("Humedad inicial (%)", min_value=0.0, max_value=100.0, value=0.0)
        reference = c3.number_input("Referencia térmica (°C)", value=23.0)
        actuators = st.text_input("Configuración inicial de actuadores", value="ventilador:0; calefactor:no disponible")
        observations = st.text_area("Observaciones")
        submitted = st.form_submit_button("Crear corrida", type="primary")
    if submitted:
        try:
            experiment = manager.create_experiment(
                grain_type=grain, phase=phase, origin=origin, thermal_reference_c=reference,
                run_code=run_code or None, batch_id=batch or None, pair_id=pair or None,
                initial_weight_g=weight or None, initial_moisture_percent=moisture or None,
                actuator_config={"configuracion": actuators}, observations=observations or None,
            )
            st.success(f"Corrida {experiment.run_code} creada en estado preparado.")
        except (ValueError, OSError) as error:
            st.error(str(error))
    experiments = manager.list_experiments()
    if not experiments:
        st.info("No hay corridas registradas."); return
    options = {f"#{item.id} · {item.run_code} · {item.phase.upper()} · {item.status}": item for item in experiments}
    selected = options[st.selectbox("Corrida", list(options))]
    st.json({"id": selected.id, "fase": selected.phase, "origen": selected.origin, "estado": selected.status, "lote": selected.batch_id})
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("Iniciar", disabled=selected.status != ExperimentStatus.PREPARADO.value):
        command = "MODO:CONTROL" if selected.phase == ExperimentPhase.DESPUES.value else "MODO:MONITOREO"
        if selected.origin == MeasurementOrigin.SIMULADO.value or st.session_state.demo_mode:
            manager.start(selected.id); st.session_state.current_experiment_id = selected.id; st.rerun()
        elif publish_command(command, "start", selected.id):
            st.info("Comando enviado; la corrida iniciará cuando llegue ACK del Arduino.")
    if c2.button("Pausar", disabled=selected.status != ExperimentStatus.EJECUTANDO.value):
        if selected.origin == MeasurementOrigin.SIMULADO.value: manager.pause(selected.id); st.rerun()
        else: publish_command("PARAR", "pause", selected.id)
    if c3.button("Reanudar", disabled=selected.status != ExperimentStatus.PAUSADO.value):
        if selected.origin == MeasurementOrigin.SIMULADO.value: manager.resume(selected.id); st.rerun()
        else: publish_command("MODO:CONTROL" if selected.phase == ExperimentPhase.DESPUES.value else "MODO:MONITOREO", "resume", selected.id)
    with c4.popover("Finalizar"):
        final_weight = st.number_input("Peso final (g)", min_value=0.0, value=0.0, key="final_weight")
        final_moisture = st.number_input("Humedad final (%)", min_value=0.0, max_value=100.0, value=0.0, key="final_moisture")
        if st.button("Confirmar finalización"):
            manager.finish(selected.id, final_weight or None, final_moisture or None); st.rerun()


def render_hardware() -> None:
    st.header("Control de hardware")
    frame = current_frame()
    st.caption("Los comandos físicos se envían por MQTT al puente Python; Streamlit no abre el puerto serial.")
    mode = st.selectbox("Modo", ["MONITOREO", "CONTROL"])
    setpoint = st.number_input("Setpoint (°C)", min_value=10.0, max_value=50.0, value=float(frame.get("sp", 23.0) if frame else 23.0))
    pwm = st.slider("PWM del ventilador", 0, 255, int(frame.get("vent", 0) or 0) if frame else 0)
    online = mqtt_subscriber is not None and mqtt_subscriber.is_connected
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("Aplicar modo", disabled=not online): publish_command(f"MODO:{mode}")
    if c2.button("Aplicar setpoint", disabled=not online): publish_command(f"SP:{setpoint:.1f}")
    if c3.button("Aplicar ventilador", disabled=not online or mode == "CONTROL"): publish_command(f"VENT:{pwm}")
    if c4.button("PARAR", type="secondary", disabled=not online): publish_command("PARAR")
    if st.session_state.pending_command: st.warning(f"Esperando ACK de {st.session_state.pending_command['command']}...")
    if st.session_state.last_ack: st.json(st.session_state.last_ack)
    st.subheader("Estado reportado")
    st.json(frame or {"estado": "No disponible"})
    st.subheader("Historial de comandos")
    st.dataframe(pd.DataFrame(st.session_state.command_log).tail(20), width="stretch")


def render_history() -> None:
    st.header("Historial de experimentos")
    experiments = manager.list_experiments()
    grain = st.selectbox("Grano", ["Todos", GrainType.CAFE.value, GrainType.CACAO.value])
    phase = st.selectbox("Fase", ["Todos", ExperimentPhase.ANTES.value, ExperimentPhase.DESPUES.value])
    origin = st.selectbox("Origen", ["Todos", MeasurementOrigin.REAL.value, MeasurementOrigin.SIMULADO.value])
    devices = ["Todos"] + history_repo.devices()
    device = st.selectbox("Dispositivo", devices)
    batch = st.text_input("Lote", placeholder="Todos los lotes")
    d1, d2 = st.columns(2)
    date_from = d1.date_input("Fecha desde", value=None)
    date_to = d2.date_input("Fecha hasta", value=None)
    rows = history_repo.measurements(
        grain_type=grain, phase=phase, origin=origin, node_id=device, batch_id=batch,
        date_from=date_from.isoformat() if date_from else None,
        date_to=date_to.isoformat() if date_to else None,
    )
    if not rows:
        st.info("No hay registros para los filtros seleccionados."); return
    df = pd.DataFrame(rows)
    st.dataframe(df, width="stretch")
    st.download_button("Descargar mediciones CSV", df.to_csv(index=False).encode("utf-8"), "mediciones.csv", "text/csv")
    if experiments:
        experiment_id = st.selectbox("Consultar eventos de corrida", [row.id for row in experiments])
        st.dataframe(pd.DataFrame(manager.list_events(experiment_id)), width="stretch")


def render_comparison() -> None:
    st.header("Comparación ANTES / DESPUÉS")
    experiments = manager.list_experiments()
    include_simulated = st.checkbox("Incluir demostraciones simuladas", value=False)
    if not include_simulated:
        experiments = [item for item in experiments if item.origin == MeasurementOrigin.REAL.value]
    antes = [item for item in experiments if item.phase == ExperimentPhase.ANTES.value]
    despues = [item for item in experiments if item.phase == ExperimentPhase.DESPUES.value]
    if not antes or not despues:
        st.info("Selecciona corridas ANTES y DESPUÉS cuando existan datos suficientes. Los datos simulados no se incluyen por defecto."); return
    a = st.selectbox("Corrida ANTES", antes, format_func=lambda x: f"{x.run_code} · {x.origin}")
    d = st.selectbox("Corrida DESPUÉS", despues, format_func=lambda x: f"{x.run_code} · {x.origin}")
    if a.grain_type != d.grain_type or a.thermal_reference_c != d.thermal_reference_c or a.completion_criterion != d.completion_criterion:
        st.error("Las corridas no tienen criterios equivalentes, grano común o referencia térmica común; no se calcula la comparación.")
        return
    all_summaries = []
    for experiment in experiments:
        all_summaries.append({"run_code": experiment.run_code, "grain_type": experiment.grain_type, "batch_id": experiment.batch_id, "pair_id": experiment.pair_id, "phase": experiment.phase, "origin": experiment.origin, "date": experiment.created_at_utc, "status": experiment.status, **calculate_experiment_indicators(experiment, history_repo.measurements(experiment_id=experiment.id))})
    all_summary_df = pd.DataFrame(all_summaries)
    st.subheader("Resumen de corridas")
    st.dataframe(all_summary_df, width="stretch")
    selected = [a, d]
    summaries = []
    measurement_rows = []
    for experiment in selected:
        measurements = history_repo.measurements(experiment_id=experiment.id)
        measurement_rows.extend(measurements)
        indicator = calculate_experiment_indicators(experiment, measurements)
        summaries.append({"run_code": experiment.run_code, "grain_type": experiment.grain_type, "batch_id": experiment.batch_id, "pair_id": experiment.pair_id, "phase": experiment.phase, "origin": experiment.origin, "date": experiment.created_at_utc, "status": experiment.status, **indicator})
    summary_df = pd.DataFrame(summaries)
    display_columns = ["run_code", "grain_type", "batch_id", "phase", "origin", "date", "duration_hours", "thermal_mae_c", "time_in_range_percent", "mass_loss_percent", "ambient_humidity_mean_percent", "grain_temperature_mean_c", "energy_kwh", "status"]
    st.subheader("Indicadores por corrida")
    st.dataframe(summary_df[[column for column in display_columns if column in summary_df]], width="stretch")
    metrics = ["duration_hours", "thermal_mae_c", "time_in_range_percent", "mass_loss_percent", "ambient_humidity_mean_percent", "grain_temperature_mean_c", "energy_kwh"]
    paired = bool(a.pair_id and d.pair_id and a.pair_id == d.pair_id)
    st.caption(f"Diseño detectado: **{'pareado por pair_id' if paired else 'independiente'}**. El orden de filas no se utiliza para emparejar.")
    comparisons = [compare_experiments(summaries, metric, paired=paired) for metric in metrics]
    comparison_df = pd.DataFrame([{"indicador": item["metric"], "n_antes": item["before"]["n"], "media_antes": item["before"]["mean"], "mediana_antes": item["before"]["median"], "desv_antes": item["before"]["std"], "n_despues": item["after"]["n"], "media_despues": item["after"]["mean"], "mediana_despues": item["after"]["median"], "desv_despues": item["after"]["std"], "diferencia": item["difference"], "cambio_pct": item["percent_change"], "direccion": item["direction"]} for item in comparisons])
    st.subheader("Comparación descriptiva")
    st.dataframe(comparison_df, width="stretch")
    test_rows = []
    for metric in metrics:
        before_values = [row[metric] for row in summaries if row["phase"] == "antes" and row.get(metric) is not None]
        after_values = [row[metric] for row in summaries if row["phase"] == "despues" and row.get(metric) is not None]
        result = statistical_tests(before_values, after_values, paired=paired)
        test_rows.append({"indicador": metric, "prueba": result.get("test") or "No disponible", "p_valor": result.get("p_value"), "shapiro_p": (result.get("shapiro") or {}).get("p_value"), "wilcoxon_p": (result.get("wilcoxon") or {}).get("p_value"), "limitación": result.get("limitation") or ""})
    tests_df = pd.DataFrame(test_rows)
    st.subheader("Pruebas estadísticas")
    st.dataframe(tests_df, width="stretch")
    st.download_button("Descargar tabla estadística CSV", dataframe_csv(tests_df), "pruebas_estadisticas.csv", "text/csv")
    st.caption("Las pruebas se reportan como apoyo inferencial. No se afirma mejora solo por un p-valor; deben evaluarse magnitud, dirección, supuestos y relevancia práctica.")
    if measurement_rows:
        df = pd.DataFrame(measurement_rows)
        chart = df.pivot_table(index="timestamp_utc", columns="run_code", values="grain_temperature_c", aggfunc="mean")
        st.subheader("Evolución de temperatura del grano")
        st.line_chart(chart)
        try:
            st.download_button("Descargar gráfico de temperatura del grano", line_chart_png(chart, "Temperatura del grano"), "temperatura_grano.png", "image/png")
        except (ImportError, ModuleNotFoundError):
            st.caption("Exportación PNG no disponible: falta matplotlib")
        ambient = df.pivot_table(index="timestamp_utc", columns="run_code", values="ambient_temperature_c", aggfunc="mean")
        st.subheader("Evolución de temperatura ambiental")
        st.line_chart(ambient)
        target = df.pivot_table(index="timestamp_utc", columns="run_code", values="reference_temperature_c", aggfunc="mean")
        if not target.empty:
            st.subheader("Referencia térmica vs. temperatura real")
            st.line_chart(pd.concat({"grano": chart, "referencia": target}, axis=1))
    c1, c2, c3 = st.columns(3)
    c1.download_button("CSV de indicadores", dataframe_csv(summary_df), "resumen_corridas.csv", "text/csv")
    try:
        excel = dataframe_excel(summary_df, "indicadores")
        c2.download_button("Excel de indicadores", excel, "resumen_corridas.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except (ImportError, ModuleNotFoundError):
        c2.caption("Excel no disponible: falta openpyxl")
    try:
        pdf = comparison_pdf("Informe ANTES / DESPUÉS", summary_df, tests_df, a.grain_type, "simulado" if include_simulated else "real")
        c3.download_button("Informe PDF", pdf, "informe_experimental.pdf", "application/pdf")
    except (ImportError, ModuleNotFoundError):
        c3.caption("PDF no disponible: falta reportlab")


def render_diagnostics() -> None:
    st.header("Inteligencia artificial y diagnóstico")
    c1, c2, c3 = st.columns(3)
    c1.metric("Modelo", "Random Forest Regressor")
    c2.metric("Variable predicha", "Tiempo restante")
    c3.metric("Registros de entrenamiento", str(model_eval.samples_count) if model_eval.samples_count else "No disponible")
    st.info("El modelo predice tiempo restante de secado; no predice temperatura ideal ni sustituye la consigna del firmware.")
    st.write({"archivo": str(MODEL_PATH), "entradas": list(model_eval.feature_columns), "objetivo": model_eval.target_column, "origen_dataset": model_eval.dataset_origin, "MAE (h)": model_eval.mae_hours or "No disponible", "R²": model_eval.r2_score or "No disponible", "división": model_eval.split_strategy})
    st.warning("El dataset inicial puede ser sintético. Verifica su origen antes de usar resultados para conclusiones experimentales.")
    st.subheader("Comunicación y sensores")
    st.write({"EMQX": "conectado" if mqtt_subscriber and mqtt_subscriber.is_connected else "No disponible", "último ACK": st.session_state.last_ack or "No disponible", "último estado": st.session_state.last_state or "No disponible", "errores": st.session_state.last_error or "No disponible", "mensajes inválidos": st.session_state.invalid_messages})


init_state()
poll_mqtt()
render_sidebar()
render_header()
if st.session_state.page == "Dashboard general": render_dashboard()
elif st.session_state.page == "Gestión de experimentos": render_experiments()
elif st.session_state.page == "Control de hardware": render_hardware()
elif st.session_state.page == "Historial": render_history()
elif st.session_state.page == "Comparación ANTES/DESPUÉS": render_comparison()
else: render_diagnostics()
render_footer(len(st.session_state.telemetry), st.session_state.invalid_messages)
