"""
Componentes Visuales Modulares para la Interfaz Streamlit.
Encapsula la presentación y desacopla la vista de la lógica de negocio.
"""

from typing import Dict, Any, Tuple
import pandas as pd
import streamlit as st

from ..config import BAUD_RATES, DEFAULT_BAUDRATE, MODEL_PATH
from ..hardware.serial_manager import get_default_port, detect_available_ports
from ..ml.model_manager import ModelEvaluation


def render_header() -> None:
    """Renderiza el título principal y la descripción del Gateway."""
    st.markdown("""
    <div class="main-header">
        <h1>Monitor IoT - Secado de Granos con IA</h1>
        <p>Puerta de Enlace (Gateway) Inteligente para el Monitoreo y Estimación del Secado de Café y Cacao</p>
    </div>
    """, unsafe_allow_html=True)


def render_sidebar_controls(
    is_connected: bool,
    eval_info: ModelEvaluation
) -> Dict[str, Any]:
    """
    Renderiza los controles de hardware y Machine Learning en la barra lateral.
    Retorna un diccionario con las acciones del usuario.
    """
    st.sidebar.markdown("### 🔌 Configuración de Hardware")

    # Detección de puertos
    ports = detect_available_ports()
    if ports:
        st.sidebar.caption(f"Puertos activos: {', '.join(ports)}")
    else:
        st.sidebar.caption("No se detectaron puertos automáticamente.")

    selected_port = st.sidebar.text_input(
        "Puerto Serial:",
        value=get_default_port(),
        help="Ej. en Linux: /dev/ttyUSB0. En Windows: COM3 o COM4."
    )

    selected_baudrate = st.sidebar.selectbox(
        "Velocidad (Baud rate):",
        options=BAUD_RATES,
        index=BAUD_RATES.index(DEFAULT_BAUDRATE)
    )

    simulation_mode = st.sidebar.checkbox(
        "🧪 Modo Simulación (Sin Arduino)",
        value=False,
        help="Simula el flujo de datos del Arduino cada 2s sin requerir el circuito físico conectado."
    )

    st.sidebar.markdown("---")

    # Botones Conectar / Desconectar
    col1, col2 = st.sidebar.columns(2)
    connect_clicked = False
    disconnect_clicked = False

    if not is_connected:
        connect_clicked = col1.button("▶ Conectar", type="primary", use_container_width=True)
    else:
        disconnect_clicked = col2.button("⏹ Desconectar", type="secondary", use_container_width=True)

    # Indicador de estado visual
    if is_connected:
        st.sidebar.markdown('<span class="badge-connected">● CONECTADO</span>', unsafe_allow_html=True)
    else:
        st.sidebar.markdown('<span class="badge-disconnected">○ DESCONECTADO</span>', unsafe_allow_html=True)

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🤖 Estado del Modelo IA")
    st.sidebar.write("**Algoritmo:** Random Forest")
    st.sidebar.write(f"**Archivo:** `{MODEL_PATH.name}`")

    if eval_info.r2_score is not None:
        st.sidebar.write(f"**$R^2$ Score:** `{eval_info.r2_score:.3f}`")
        st.sidebar.write(f"**MAE:** `{eval_info.mae_hours:.2f} hrs`")

    retrain_clicked = st.sidebar.button("🔄 Reentrenar Modelo")

    return {
        "port": selected_port,
        "baudrate": selected_baudrate,
        "simulation_mode": simulation_mode,
        "connect_clicked": connect_clicked,
        "disconnect_clicked": disconnect_clicked,
        "retrain_clicked": retrain_clicked
    }


def render_status_banner(
    container,
    is_connected: bool,
    port: str,
    baudrate: int
) -> bool:
    """
    Muestra la barra de estado y el botón de parada rápida.
    Retorna True si el usuario solicita detener el monitoreo.
    """
    if is_connected:
        c1, c2 = container.columns([4, 1.2])
        c1.info(f"📡 Monitoreando telemetría en **{port}** ({baudrate} bauds)...")
        if c2.button("⏹ Detener Monitoreo", key="quick_stop_btn", type="secondary", use_container_width=True):
            return True
    else:
        container.warning("⚠️ Sistema en espera. Selecciona el puerto en la barra lateral y presiona **'▶ Conectar'**.")
    return False


def render_metrics_panel(
    container,
    temp_amb: float,
    hum_amb: float,
    temp_grano: float,
    tiempo_est: float,
    stage_info: Tuple[str, str]
) -> None:
    """Renderiza las 3 métricas de sensores y la tarjeta destacada de predicción de IA."""
    stage_text, stage_class = stage_info

    with container:
        col1, col2, col3, col4 = st.columns([1, 1, 1, 1.3])

        with col1:
            st.metric(
                label="🌡️ Temp. Ambiente (DHT22)",
                value=f"{temp_amb:.1f} °C",
                delta=f"{temp_amb - 25.0:+.1f} vs ref"
            )

        with col2:
            st.metric(
                label="💧 Humedad Relativa (DHT22)",
                value=f"{hum_amb:.1f} %",
                delta=f"{hum_amb - 60.0:+.1f} vs ref",
                delta_color="inverse"
            )

        with col3:
            st.metric(
                label="🌾 Temp. Grano (DS18B20)",
                value=f"{temp_grano:.1f} °C",
                delta=f"{temp_grano - temp_amb:+.1f} vs amb"
            )

        with col4:
            st.markdown(f"""
            <div class="prediction-card">
                <div class="prediction-title">⏱️ Tiempo Estimado Restante</div>
                <div class="prediction-value">{tiempo_est:.1f}</div>
                <div class="prediction-unit">Horas de secado</div>
                <div class="prediction-badge {stage_class}">{stage_text}</div>
            </div>
            """, unsafe_allow_html=True)


def render_trend_charts(container, history_df: pd.DataFrame) -> None:
    """Renderiza gráficos dinámicos en tiempo real con el historial de telemetría."""
    with container:
        if not history_df.empty:
            st.markdown("#### 📈 Evolución Dinámica de Variables y Secado")
            df = history_df.set_index('Timestamp')

            c1, c2 = st.columns(2)
            with c1:
                st.caption("Temperaturas (°C) y Humedad (%)")
                st.line_chart(df[['Temp_Ambiente', 'Humedad_Ambiente', 'Temp_Grano']], height=250)
            with c2:
                st.caption("Curva de Decaimiento: Tiempo Restante Estimado (Horas)")
                st.line_chart(df[['Tiempo_Restante_Estimado']], height=250, color="#00b4d8")


def render_footer(valid_reads: int, corrupted_reads: int) -> None:
    """Renderiza el pie de página con contadores de fallos y telemetría de robustez."""
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    col1.caption(f"Lecturas válidas procesadas: **{valid_reads}**")
    col2.caption(f"Lecturas con ruido descartadas: **{corrupted_reads}**")
    col3.caption("Arquitectura IoT Gateway v2.0 | Clean Architecture con Python & Streamlit")
