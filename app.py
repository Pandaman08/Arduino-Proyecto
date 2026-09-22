"""
Monitor IoT - Secado de Granos con IA (Café y Cacao)
Gateway Bidireccional en Streamlit con Control de Actuadores,
Diagnóstico de Componentes y Predicción ML.
"""

import os
import time
import datetime
from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error
import serial
import serial.tools.list_ports

# ==============================================================================
# 1. CONFIGURACIÓN DE PÁGINA Y RUTAS
# ==============================================================================
st.set_page_config(
    page_title="Monitor IoT - Secado de Granos con IA",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "data" / "dataset_secado_cafe.csv"
if not DATASET_PATH.exists():
    DATASET_PATH = BASE_DIR / "dataset_secado_cafe.csv"

MODEL_PATH = BASE_DIR / "models" / "modelo_secado.pkl"
if not MODEL_PATH.parent.exists():
    MODEL_PATH = BASE_DIR / "modelo_secado.pkl"

# Integración del modelo regional de Perú y control térmico
try:
    from src.config import (
        PERU_REGIONS_DATA,
        DEFAULT_IDEAL_TEMP,
        TOLERANCIA_IDEAL_TEMP,
        UMBRAL_CERCA_TEMP
    )
    from src.ml.regional_drying import (
        predict_ideal_temperature,
        evaluate_thermal_state
    )
except ImportError:
    import sys
    sys.path.insert(0, str(BASE_DIR))
    from src.config import (
        PERU_REGIONS_DATA,
        DEFAULT_IDEAL_TEMP,
        TOLERANCIA_IDEAL_TEMP,
        UMBRAL_CERCA_TEMP
    )
    from src.ml.regional_drying import (
        predict_ideal_temperature,
        evaluate_thermal_state
    )

# Estilos CSS profesionales para panel IoT
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 1.4rem 2rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 1.2rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .main-header h1 { color: #ffffff !important; font-size: 2.1rem; font-weight: 700; margin: 0; }
    .main-header p { color: #e0e7ff; font-size: 0.95rem; margin-top: 0.3rem; margin-bottom: 0; }
    
    /* Tarjeta destacada de IA */
    .prediction-card {
        background: linear-gradient(135deg, #0d3b66 0%, #001e3d 100%);
        border: 2px solid #00b4d8;
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
        color: white;
        box-shadow: 0 6px 20px rgba(0, 180, 216, 0.25);
    }
    .prediction-title { font-size: 0.85rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #caf0f8; }
    .prediction-value { font-size: 2.8rem; font-weight: 800; color: #90e0ef; margin: 0.2rem 0; line-height: 1.1; }
    .prediction-unit { font-size: 1rem; color: #caf0f8; font-weight: 500; }
    .prediction-badge { display: inline-block; margin-top: 0.5rem; padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }
    .badge-normal { background-color: rgba(0, 180, 216, 0.2); color: #caf0f8; }
    .badge-final { background-color: rgba(46, 204, 113, 0.25); color: #a3e635; }
    .badge-danger { background-color: rgba(239, 68, 68, 0.3); color: #fca5a5; border: 1px solid #ef4444; }
    
    /* Semáforo Térmico de Secado (Lazo Cerrado) */
    .semaforo-banner {
        border-radius: 12px;
        padding: 1rem 1.4rem;
        margin: 0.9rem 0;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 4px 15px rgba(0,0,0,0.15);
        font-family: inherit;
    }
    .semaforo-verde {
        background: linear-gradient(135deg, rgba(34, 197, 94, 0.18) 0%, rgba(22, 101, 52, 0.35) 100%);
        border: 2px solid #22c55e;
        color: #bbf7d0;
    }
    .semaforo-amarillo {
        background: linear-gradient(135deg, rgba(234, 179, 8, 0.18) 0%, rgba(133, 77, 14, 0.35) 100%);
        border: 2px solid #eab308;
        color: #fef08a;
    }
    .semaforo-rojo {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.2) 0%, rgba(127, 29, 29, 0.38) 100%);
        border: 2px solid #ef4444;
        color: #fecaca;
    }
    .badge-semaforo-pill {
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.85rem;
        letter-spacing: 0.5px;
        background: rgba(0, 0, 0, 0.35);
        border: 1px solid rgba(255, 255, 255, 0.2);
    }
    
    /* Tarjetas de Diagnóstico Adaptativas (Modo Oscuro y Claro) */
    .diag-card {
        background-color: var(--secondary-background-color, #1e293b);
        color: var(--text-color, #e2e8f0);
        border: 1px solid rgba(148, 163, 184, 0.25);
        border-radius: 12px;
        padding: 1.15rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
        transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    }
    .diag-card:hover {
        border-color: #00b4d8;
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(0, 180, 216, 0.2);
    }
    .diag-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: var(--text-color, #f8fafc);
        margin-bottom: 0.5rem;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .diag-pin {
        font-size: 0.75rem;
        background: rgba(148, 163, 184, 0.2);
        color: var(--text-color, #94a3b8);
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 600;
        border: 1px solid rgba(148, 163, 184, 0.25);
    }
    .diag-card p {
        color: var(--text-color, #cbd5e1);
        margin-bottom: 0.4rem;
        font-size: 0.92rem;
    }
    .diag-card strong {
        color: var(--text-color, #f1f5f9);
    }
    .diag-card code {
        background-color: rgba(0, 180, 216, 0.15) !important;
        color: #38bdf8 !important;
        padding: 2px 6px !important;
        border-radius: 4px !important;
        font-weight: 600;
    }
    .diag-muted {
        color: rgba(148, 163, 184, 0.85);
        font-size: 0.82rem;
        margin-top: 0.35rem;
    }
    .diag-status-ok { color: #22c55e; font-weight: 700; }
    .diag-status-warn { color: #f59e0b; font-weight: 700; }
    .diag-status-off { color: #94a3b8; font-weight: 600; }
    .diag-status-err { color: #ef4444; font-weight: 700; }
    
    /* Badges de Conexión */
    .badge-conn-on { background-color: #2ecc71; color: white; padding: 4px 10px; border-radius: 12px; font-weight: 600; font-size: 0.85rem; }
    .badge-conn-off { background-color: #e74c3c; color: white; padding: 4px 10px; border-radius: 12px; font-weight: 600; font-size: 0.85rem; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. GESTIÓN DEL MODELO PREDICTIVO (RANDOM FOREST)
# ==============================================================================
def generar_dataset_si_no_existe(ruta_csv: Path) -> pd.DataFrame:
    """Genera un dataset sintético calibrado si no se encuentra el archivo local."""
    np.random.seed(42)
    n_samples = 800
    temp_amb = np.random.uniform(20.0, 42.0, n_samples)
    hum_amb = np.random.uniform(35.0, 85.0, n_samples)
    temp_grano = np.clip(temp_amb + np.random.uniform(-2.0, 5.0, n_samples), 18.0, 48.0)
    
    factor_secado = (temp_grano * 0.45 + temp_amb * 0.35) / (hum_amb * 0.5)
    tiempo_restante = np.clip(60.0 - (factor_secado * 25.0) + np.random.normal(0, 2.0, n_samples), 0.5, 48.0)
    
    df = pd.DataFrame({
        'Temp_Ambiente': np.round(temp_amb, 1),
        'Humedad_Ambiente': np.round(hum_amb, 1),
        'Temp_Grano': np.round(temp_grano, 1),
        'Tiempo_Restante_Horas': np.round(tiempo_restante, 1)
    })
    ruta_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta_csv, index=False)
    return df

@st.cache_resource(show_spinner="Cargando modelo predictivo...")
def obtener_o_entrenar_modelo():
    info = {"reentrenado": False, "r2": None, "mae": None, "muestras": 0}
    
    if MODEL_PATH.exists():
        try:
            modelo = joblib.load(MODEL_PATH)
            return modelo, info
        except Exception:
            pass
            
    if not DATASET_PATH.exists():
        generar_dataset_si_no_existe(DATASET_PATH)
        
    df = pd.read_csv(DATASET_PATH)
    columnas_req = ['Temp_Ambiente', 'Humedad_Ambiente', 'Temp_Grano', 'Tiempo_Restante_Horas']
    for col in columnas_req:
        if col not in df.columns:
            raise ValueError(f"Falta columna obligatoria '{col}' en {DATASET_PATH}")
            
    X = df[['Temp_Ambiente', 'Humedad_Ambiente', 'Temp_Grano']]
    y = df['Tiempo_Restante_Horas']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    modelo = RandomForestRegressor(n_estimators=100, max_depth=12, random_state=42, n_jobs=1)
    modelo.fit(X_train, y_train)
    
    y_pred = modelo.predict(X_test)
    r2 = float(r2_score(y_test, y_pred))
    mae = float(mean_absolute_error(y_test, y_pred))
    
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(modelo, MODEL_PATH)
    
    info.update({"reentrenado": True, "r2": r2, "mae": mae, "muestras": len(df)})
    return modelo, info

modelo_ml, info_modelo = obtener_o_entrenar_modelo()

# ==============================================================================
# 3. GESTIÓN PERSISTENTE DE CONEXIÓN SERIAL Y ESTADO DE COMPONENTES
# ==============================================================================
if 'serial_conn' not in st.session_state:
    st.session_state.serial_conn = None
if 'puerto_actual' not in st.session_state:
    st.session_state.puerto_actual = ""
if 'analisis_en_ejecucion' not in st.session_state:
    st.session_state.analisis_en_ejecucion = False
if 'historial' not in st.session_state:
    st.session_state.historial = pd.DataFrame(columns=[
        'Timestamp', 'Temp_Ambiente', 'Humedad_Ambiente', 'Temp_Grano', 'Tiempo_Restante_Estimado'
    ])
if 'ultimo_comando' not in st.session_state:
    st.session_state.ultimo_comando = "Ninguno"
if 'lineas_corruptas' not in st.session_state:
    st.session_state.lineas_corruptas = 0

# Estado de actuadores, semáforo y pantalla
if 'estado_led_verde' not in st.session_state:
    st.session_state.estado_led_verde = False
if 'estado_led_amarillo' not in st.session_state:
    st.session_state.estado_led_amarillo = False
if 'estado_led_rojo' not in st.session_state:
    st.session_state.estado_led_rojo = False
if 'estado_ventilador' not in st.session_state:
    st.session_state.estado_ventilador = "0% (Apagado)"
if 'texto_display_actual' not in st.session_state:
    st.session_state.texto_display_actual = "SECADO CAFE IA"

# Parámetros y Estado del Lazo Cerrado de Temperatura Ideal (Perú)
if 'region_seleccionada' not in st.session_state:
    st.session_state.region_seleccionada = "San Martín (Moyobamba / Tarapoto)"
if 'temp_ideal_consigna' not in st.session_state:
    st.session_state.temp_ideal_consigna = DEFAULT_IDEAL_TEMP
if 'estado_semaforo_codigo' not in st.session_state:
    st.session_state.estado_semaforo_codigo = "IDEAL_ALCANZADA"
if 'color_semaforo_led' not in st.session_state:
    st.session_state.color_semaforo_led = "VERDE"
if 'sim_grano_actual' not in st.session_state:
    st.session_state.sim_grano_actual = 43.5  # Inicia por encima para ver al ventilador enfriar

# Estado y salud de sensores
if 'sensor_dht_estado' not in st.session_state:
    st.session_state.sensor_dht_estado = "⚪ En espera de telemetría"
if 'sensor_ds_estado' not in st.session_state:
    st.session_state.sensor_ds_estado = "⚪ En espera de telemetría"
if 'ultima_temp_amb' not in st.session_state:
    st.session_state.ultima_temp_amb = None
if 'ultima_hum_amb' not in st.session_state:
    st.session_state.ultima_hum_amb = None
if 'ultima_temp_grano' not in st.session_state:
    st.session_state.ultima_temp_grano = None
if 'ultima_hora_lectura' not in st.session_state:
    st.session_state.ultima_hora_lectura = "Sin lecturas previas"

def enviar_comando(caracter: str, descripcion: str = "") -> bool:
    """Envía comando serial y actualiza el estado de los actuadores sin reconectar el puerto."""
    st.session_state.ultimo_comando = f"'{caracter}' ({descripcion})"
    
    # Actualización reactiva del estado virtual de actuadores
    if caracter in ('V', 'v'):
        st.session_state.estado_led_verde = True
        st.session_state.estado_led_amarillo = False
        st.session_state.estado_led_rojo = False
    elif caracter in ('A', 'a'):
        st.session_state.estado_led_verde = False
        st.session_state.estado_led_amarillo = True
        st.session_state.estado_led_rojo = False
    elif caracter in ('R', 'r'):
        st.session_state.estado_led_verde = False
        st.session_state.estado_led_amarillo = False
        st.session_state.estado_led_rojo = True
    elif caracter == '1':
        st.session_state.estado_ventilador = "60% (PWM 153)"
    elif caracter == '2':
        st.session_state.estado_ventilador = "100% (PWM 255)"
    elif caracter == '0':
        st.session_state.estado_led_verde = False
        st.session_state.estado_led_amarillo = False
        st.session_state.estado_led_rojo = False
        st.session_state.estado_ventilador = "0% (Apagado)"
    elif caracter.startswith('D:') or caracter.startswith('d:'):
        st.session_state.texto_display_actual = caracter[2:].strip()
    elif caracter.startswith('T:') or caracter.startswith('t:'):
        try:
            val_str = caracter[2:].strip()
            st.session_state.temp_ideal_consigna = float(val_str)
        except ValueError:
            pass

    ser = st.session_state.serial_conn
    if ser is not None and getattr(ser, 'is_open', False):
        try:
            # Enviar con delimitador de línea para comandos de texto y caracteres
            payload = caracter if caracter.endswith('\n') else (caracter + '\n')
            ser.write(payload.encode('utf-8'))
            ser.flush()
            return True
        except (serial.SerialException, OSError) as e:
            st.error(f"Error al enviar comando: {e}")
            return False
    else:
        if st.session_state.get('modo_simulacion', False):
            return True
        st.warning("⚠️ El puerto serial no está conectado.")
        return False

# ==============================================================================
# 4. BARRA LATERAL (SIDEBAR) - CONEXIÓN SERIAL
# ==============================================================================
st.sidebar.markdown("### 🔌 Conexión con Arduino")

puertos_detectados = [p.device for p in serial.tools.list_ports.comports()]
puerto_default = puertos_detectados[0] if puertos_detectados else ("/dev/ttyUSB0" if os.name != 'nt' else "COM3")

if puertos_detectados:
    st.sidebar.caption(f"Puertos activos: {', '.join(puertos_detectados)}")
else:
    st.sidebar.caption("No se detectaron puertos automáticamente.")

puerto_seleccionado = st.sidebar.text_input("Puerto Serial:", value=puerto_default)
baud_rate = st.sidebar.selectbox("Velocidad (Baud rate):", options=[9600, 19200, 38400, 57600, 115200], index=0)

modo_simulacion = st.sidebar.checkbox("🧪 Modo Simulación (Sin Arduino)", value=False)
st.session_state.modo_simulacion = modo_simulacion

st.sidebar.markdown("---")
col_c1, col_c2 = st.sidebar.columns(2)

esta_conectado = (st.session_state.serial_conn is not None and st.session_state.serial_conn.is_open) or modo_simulacion

if not esta_conectado:
    if col_c1.button("▶ Conectar", type="primary", use_container_width=True):
        if modo_simulacion:
            st.session_state.puerto_actual = "SIMULADOR"
            st.rerun()
        else:
            try:
                ser = serial.Serial(port=puerto_seleccionado, baudrate=baud_rate, timeout=1.5, write_timeout=1.5)
                ser.reset_input_buffer()
                time.sleep(1.5)  # Estabilización de línea DTR
                st.session_state.serial_conn = ser
                st.session_state.puerto_actual = puerto_seleccionado
                st.rerun()
            except serial.SerialException as err:
                st.sidebar.error(f"Fallo al abrir {puerto_seleccionado}: {err}")
else:
    if col_c2.button("⏹ Desconectar", type="secondary", use_container_width=True):
        st.session_state.analisis_en_ejecucion = False
        if st.session_state.serial_conn is not None:
            try:
                st.session_state.serial_conn.write(b'P')
                st.session_state.serial_conn.close()
            except Exception:
                pass
            st.session_state.serial_conn = None
        st.rerun()

if esta_conectado:
    st.sidebar.markdown(f'<span class="badge-conn-on">● CONECTADO ({st.session_state.puerto_actual})</span>', unsafe_allow_html=True)
else:
    st.sidebar.markdown('<span class="badge-conn-off">○ DESCONECTADO</span>', unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.markdown("### 🤖 Modelo de IA")
st.sidebar.write(f"**Archivo:** `{MODEL_PATH.name}`")
if info_modelo.get("r2") is not None:
    st.sidebar.write(f"**$R^2$:** `{info_modelo['r2']:.3f}` | **MAE:** `{info_modelo['mae']:.2f} h`")

# ==============================================================================
# 5. ENCABEZADO Y PESTAÑAS (st.tabs)
# ==============================================================================
st.markdown("""
<div class="main-header">
    <h1>Monitor IoT - Secado de Granos con IA</h1>
    <p>Puerta de Enlace Bidireccional para Pruebas de Actuadores, Diagnóstico de Componentes y Predicción de Secado</p>
</div>
""", unsafe_allow_html=True)

tab_hardware, tab_analisis, tab_estado = st.tabs([
    "🛠️ Pestaña 1: Prueba de Hardware",
    "☕ Pestaña 2: Análisis de Secado (IA)",
    "🩺 Pestaña 3: Diagnóstico y Estado de Componentes"
])

# ------------------------------------------------------------------------------
# PESTAÑA 1: PRUEBA DE HARDWARE
# ------------------------------------------------------------------------------
with tab_hardware:
    st.subheader("Prueba y Diagnóstico de Actuadores")
    st.write("Presiona los botones para activar cada actuador de forma individual. La conexión se mantiene abierta sin reiniciar el Arduino.")

    if not esta_conectado:
        st.warning("⚠️ Presiona **'▶ Conectar'** en la barra lateral para habilitar el control del Arduino.")

    st.markdown("#### 💡 Indicadores Luminosos (LEDs)")
    col_led1, col_led2, col_led3 = st.columns(3)

    with col_led1:
        # Comando 'V' -> Pin D4 (LED Verde)
        if st.button("🟢 Probar LED Verde", use_container_width=True, disabled=not esta_conectado):
            if enviar_comando('V', "LED Verde (Pin D4)"):
                st.toast("Comando 'V' enviado: LED Verde", icon="🟢")

    with col_led2:
        # Comando 'A' -> Pin D6 (LED Amarillo - Corregido mapeo físico)
        if st.button("🟡 Probar LED Amarillo", use_container_width=True, disabled=not esta_conectado):
            if enviar_comando('A', "LED Amarillo (Pin D6)"):
                st.toast("Comando 'A' enviado: LED Amarillo", icon="🟡")

    with col_led3:
        # Comando 'R' -> Pin D5 (LED Rojo - Corregido mapeo físico)
        if st.button("🔴 Probar LED Rojo", use_container_width=True, disabled=not esta_conectado):
            if enviar_comando('R', "LED Rojo (Pin D5)"):
                st.toast("Comando 'R' enviado: LED Rojo", icon="🔴")

    st.markdown("---")
    st.markdown("#### 🌀 Control de Ventilación y Apagado General")
    col_fan1, col_fan2, col_off = st.columns(3)

    with col_fan1:
        if st.button("💨 Ventilador al 60%", use_container_width=True, disabled=not esta_conectado):
            if enviar_comando('1', "Ventilador 60% (Pin D9 PWM)"):
                st.toast("Comando '1' enviado: Ventilador 60%", icon="💨")

    with col_fan2:
        if st.button("🌪️ Ventilador al 100%", use_container_width=True, disabled=not esta_conectado):
            if enviar_comando('2', "Ventilador 100% (Pin D9 PWM)"):
                st.toast("Comando '2' enviado: Ventilador 100%", icon="🌪️")

    with col_off:
        if st.button("🛑 Apagar Todo", type="primary", use_container_width=True, disabled=not esta_conectado):
            if enviar_comando('0', "Apagado General"):
                st.toast("Comando '0' enviado: Todos los actuadores apagados", icon="🛑")

    st.markdown("---")
    st.markdown("#### 📋 Estado Actual de los Actuadores")
    c_st1, c_st2, c_st3, c_st4 = st.columns(4)
    c_st1.metric("LED Verde (D4)", "🟢 ENCENDIDO" if st.session_state.estado_led_verde else "⚫ Apagado")
    c_st2.metric("LED Amarillo (D6)", "🟡 ENCENDIDO" if st.session_state.estado_led_amarillo else "⚫ Apagado")
    c_st3.metric("LED Rojo (D5)", "🔴 ENCENDIDO" if st.session_state.estado_led_rojo else "⚫ Apagado")
    c_st4.metric("Ventilador (D9 PWM)", st.session_state.estado_ventilador)

    st.markdown("---")
    st.markdown("#### 🎯 Consigna de Temperatura Ideal (Comando 'T:XX.X')")
    st.caption("Fija en el microcontrolador la temperatura ideal hacia la cual debe regular el lazo cerrado.")
    col_t_in, col_t_btn = st.columns([2.5, 2.4])
    with col_t_in:
        temp_input = st.number_input(
            "Temperatura Ideal (°C):",
            min_value=20.0,
            max_value=50.0,
            value=float(st.session_state.temp_ideal_consigna),
            step=0.5,
            key="temp_hardware_input"
        )
    with col_t_btn:
        st.write("")
        st.write("")
        if st.button("📤 Enviar Consigna Térmica", use_container_width=True, disabled=not esta_conectado):
            if enviar_comando(f"T:{temp_input:.1f}", f"Consigna Térmica {temp_input:.1f}°C"):
                st.session_state.temp_ideal_consigna = temp_input
                st.toast(f"Comando 'T:{temp_input:.1f}' enviado al Arduino", icon="🎯")

    st.markdown("---")
    st.markdown("#### 📟 Prueba de Pantalla LCD (I2C 16x2)")
    st.caption("Escribe una frase y envíala al Arduino para desplegarla en la pantalla LCD (Pines A4 SDA y A5 SCL del Arduino Nano).")

    col_lcd_in, col_lcd_btn1, col_lcd_btn2 = st.columns([2.5, 1.2, 1.2])
    with col_lcd_in:
        frase_display = st.text_input(
            "Frase para el Display (máx. 32 caracteres):",
            value=st.session_state.texto_display_actual,
            max_chars=32,
            help="Si excede los 16 caracteres, el Arduino divide automáticamente el texto en las 2 filas del LCD."
        )
    with col_lcd_btn1:
        st.write("")
        st.write("")
        if st.button("📤 Enviar al LCD", use_container_width=True, disabled=not esta_conectado):
            if enviar_comando(f"D:{frase_display}", f"Display: '{frase_display}'"):
                st.session_state.texto_display_actual = frase_display
                st.toast(f"Frase enviada al LCD: '{frase_display}'", icon="📟")

    with col_lcd_btn2:
        st.write("")
        st.write("")
        if st.button("🧹 Limpiar LCD", use_container_width=True, disabled=not esta_conectado):
            if enviar_comando("D: ", "Display Limpio"):
                st.session_state.texto_display_actual = ""
                st.toast("Pantalla LCD limpiada", icon="🧹")

    # Vista Previa Virtual de la Pantalla LCD (16x2)
    st.markdown("**Vista Previa Virtual del Display LCD (16x2):**")
    txt_disp = st.session_state.texto_display_actual
    linea1 = (txt_disp[:16]).ljust(16)
    linea2 = (txt_disp[16:32]).ljust(16)
    st.markdown(f"""
    <div style="background-color: #0b2512; border: 3px solid #1e3a29; border-radius: 8px; padding: 12px 18px; width: fit-content; margin-bottom: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.25);">
        <div style="font-family: 'Courier New', monospace; font-weight: 700; font-size: 1.15rem; color: #4ade80; letter-spacing: 2px;">
            [{linea1}]
        </div>
        <div style="font-family: 'Courier New', monospace; font-weight: 700; font-size: 1.15rem; color: #4ade80; letter-spacing: 2px;">
            [{linea2}]
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.info(f"📡 Último comando registrado en bus serial: **{st.session_state.ultimo_comando}**")

# ------------------------------------------------------------------------------
# PESTAÑA 2: ANÁLISIS DE SECADO (IA)
# ------------------------------------------------------------------------------
with tab_analisis:
    st.subheader("Monitoreo y Predicción en Tiempo Real")
    st.caption("Predicción de temperatura ideal de secado por región de Perú y control automático en lazo cerrado con Arduino Nano.")

    # 1. Selector de Región Cafetalera / Cacaotera de Perú
    st.markdown("#### 🇵🇪 Región Cafetalera / Cacaotera de Perú (Predicción de Temperatura Ideal)")
    regiones_lista = list(PERU_REGIONS_DATA.keys())
    idx_def = regiones_lista.index(st.session_state.region_seleccionada) if st.session_state.region_seleccionada in regiones_lista else 0

    col_reg1, col_reg2 = st.columns([1.5, 2.5])
    with col_reg1:
        region_sel = st.selectbox(
            "Región de Producción:",
            options=regiones_lista,
            index=idx_def,
            help="Adapta la consigna según las condiciones psicrométricas y precipitaciones típicas de cada zona productora del Perú."
        )
        st.session_state.region_seleccionada = region_sel

    perfil = PERU_REGIONS_DATA[region_sel]
    
    # Estimación de Temperatura Ideal de Secado ML
    hum_ref = st.session_state.ultima_hum_amb if st.session_state.ultima_hum_amb is not None else perfil["humedad_tipica"]
    temp_ref = st.session_state.ultima_temp_amb if st.session_state.ultima_temp_amb is not None else 26.0
    temp_ideal_predicha = predict_ideal_temperature(region_sel, hum_ref, temp_ref)

    with col_reg2:
        st.info(
            f"🌧️ **Zona:** {perfil['zona']} | **Precipitación:** `{perfil['precipitacion_anual_mm']} mm/año` | **Humedad Típica:** `{perfil['humedad_tipica']}%`\n\n"
            f"⚠️ **Riesgo:** {perfil['riesgo_humedad']}\n\n"
            f"💡 *{perfil['descripcion']}*"
        )

    # 2. Tarjetas de Consigna de Temperatura y Control
    col_t1, col_t2 = st.columns([1.4, 2.6])
    with col_t1:
        st.markdown(f"""
        <div class="prediction-card" style="border-color: #f59e0b; background: linear-gradient(135deg, #451a03 0%, #1e1b4b 100%);">
            <div class="prediction-title" style="color: #fde68a;">🎯 Temp. Ideal Predicha (ML)</div>
            <div class="prediction-value" style="color: #fbbf24;">{temp_ideal_predicha:.1f}</div>
            <div class="prediction-unit" style="color: #fde68a;">°C (Consigna Óptima)</div>
        </div>
        """, unsafe_allow_html=True)
    with col_t2:
        st.caption("Esta temperatura ideal se envía al microcontrolador para regular automáticamente la convección del ventilador y el semáforo LED.")
        col_c_sync, col_c_man = st.columns([1.3, 1.7])
        with col_c_sync:
            st.write("")
            if st.button("📤 Sincronizar con Arduino", use_container_width=True, disabled=not esta_conectado):
                if enviar_comando(f"T:{temp_ideal_predicha:.1f}", f"Temp Ideal {temp_ideal_predicha:.1f}°C"):
                    st.session_state.temp_ideal_consigna = temp_ideal_predicha
                    st.toast(f"Consigna T:{temp_ideal_predicha:.1f}°C transmitida al Arduino", icon="🎯")
        with col_c_man:
            temp_manual = st.number_input(
                "Ajustar Consigna de Secado (°C):",
                min_value=20.0,
                max_value=48.0,
                value=float(st.session_state.temp_ideal_consigna),
                step=0.5,
                key="temp_ideal_analisis_input"
            )
            if temp_manual != st.session_state.temp_ideal_consigna:
                st.session_state.temp_ideal_consigna = temp_manual
                if esta_conectado:
                    enviar_comando(f"T:{temp_manual:.1f}", f"Ajuste manual {temp_manual:.1f}°C")

    st.markdown("---")

    col_btn_ini, col_btn_pau, _ = st.columns([1.3, 1.3, 2.4])
    
    with col_btn_ini:
        if st.button("▶ Iniciar Análisis", type="primary", use_container_width=True, disabled=not esta_conectado or st.session_state.analisis_en_ejecucion):
            # Enviar automáticamente la consigna térmica predicha antes de iniciar
            enviar_comando(f"T:{st.session_state.temp_ideal_consigna:.1f}", f"Consigna Inicial {st.session_state.temp_ideal_consigna:.1f}°C")
            time.sleep(0.1)
            enviar_comando('I', "Iniciar Análisis y Telemetría")
            st.session_state.analisis_en_ejecucion = True
            st.rerun()

    with col_btn_pau:
        if st.button("⏸ Pausar Análisis", type="secondary", use_container_width=True, disabled=not st.session_state.analisis_en_ejecucion):
            enviar_comando('P', "Pausar Análisis")
            st.session_state.analisis_en_ejecucion = False
            st.rerun()

    status_area = st.empty()
    semaforo_area = st.empty()
    metrics_area = st.container()
    charts_area = st.empty()
    log_area = st.expander("📝 Registro de Comunicaciones Serial y Depuración", expanded=False)

    if st.session_state.analisis_en_ejecucion:
        status_area.info("📡 **Análisis en ejecución:** Recibiendo telemetría del Arduino cada 2 segundos...")
        ser = st.session_state.serial_conn

        while st.session_state.analisis_en_ejecucion:
            raw_line = ""
            try:
                if modo_simulacion:
                    time.sleep(2.0)
                    sim_t_amb = round(float(np.random.uniform(25.0, 31.0)), 1)
                    sim_h_amb = round(float(np.random.uniform(55.0, 78.0)), 1)
                    
                    # Dinámica de simulación reactiva del lazo cerrado
                    ideal_t = st.session_state.temp_ideal_consigna
                    grano_prev = st.session_state.get('sim_grano_actual', ideal_t + 4.0)
                    error_sim = grano_prev - ideal_t

                    if abs(error_sim) > 3.5:
                        # Lejos: Ventilador al 100% reduce la temperatura rápidamente
                        grano_prev -= 0.8
                    elif abs(error_sim) > 1.0:
                        # En camino: Ventilador al 60% reduce suavemente
                        grano_prev -= 0.4
                    else:
                        # Meta alcanzada: Ventilador apagado. Fluctúa levemente
                        # Ocasionalmente sube para demostrar que el ventilador se vuelve a prender
                        fluctuacion = float(np.random.choice([-0.2, 0.0, 0.2, 1.8], p=[0.3, 0.4, 0.2, 0.1]))
                        grano_prev = ideal_t + fluctuacion

                    st.session_state.sim_grano_actual = round(grano_prev, 1)
                    sim_t_grano = st.session_state.sim_grano_actual
                    raw_line = f"{sim_t_amb},{sim_h_amb},{sim_t_grano}"
                else:
                    if ser is None or not ser.is_open:
                        raise serial.SerialException("El puerto serie se encuentra cerrado.")
                    
                    bytes_leidos = ser.readline()
                    if not bytes_leidos:
                        continue
                    raw_line = bytes_leidos.decode('utf-8', errors='ignore').strip()

                if not raw_line or raw_line.startswith("ACK") or raw_line.startswith("SISTEMA"):
                    continue

                partes = raw_line.split(',')
                if len(partes) != 3:
                    raise ValueError(f"Trama corrupta ({len(partes)} valores): '{raw_line}'")

                temp_amb = float(partes[0].strip())
                hum_amb = float(partes[1].strip())
                temp_grano = float(partes[2].strip())

                if not (-10.0 <= temp_amb <= 80.0 and 0.0 <= hum_amb <= 100.0 and -10.0 <= temp_grano <= 85.0):
                    raise ValueError(f"Lectura fuera de rango físico: {temp_amb}°C, {hum_amb}%, {temp_grano}°C")

                # Actualizar diagnóstico de salud de sensores
                ahora = datetime.datetime.now().strftime("%H:%M:%S")
                st.session_state.sensor_dht_estado = "🟢 Operativo (Lectura íntegra)"
                st.session_state.sensor_ds_estado = "⚠️ Sobrecalentado (>45°C)" if temp_grano > 45.0 else "🟢 Operativo (En rango)"
                st.session_state.ultima_temp_amb = temp_amb
                st.session_state.ultima_hum_amb = hum_amb
                st.session_state.ultima_temp_grano = temp_grano
                st.session_state.ultima_hora_lectura = ahora

                # Evaluación de Lazo Cerrado y Semáforo Térmico
                estado_termico, color_led, pwm_fan, label_fan = evaluate_thermal_state(
                    temp_grano, st.session_state.temp_ideal_consigna
                )
                st.session_state.estado_semaforo_codigo = estado_termico
                st.session_state.color_semaforo_led = color_led
                st.session_state.estado_ventilador = label_fan
                st.session_state.estado_led_verde = (color_led == "VERDE")
                st.session_state.estado_led_amarillo = (color_led == "AMARILLO")
                st.session_state.estado_led_rojo = (color_led == "ROJO")

                # Inferencia con Random Forest para tiempo restante
                features = pd.DataFrame([{
                    'Temp_Ambiente': temp_amb,
                    'Humedad_Ambiente': hum_amb,
                    'Temp_Grano': temp_grano
                }])
                tiempo_restante = float(modelo_ml.predict(features)[0])
                tiempo_restante = max(0.0, tiempo_restante)

                if temp_grano > 45.0:
                    etiqueta_estado = "⚠️ ALERTA: Sobrecalentamiento (>45°C)"
                    clase_badge = "badge-danger"
                elif tiempo_restante > 30.0:
                    etiqueta_estado = "Fase 1: Alto Contenido de Humedad"
                    clase_badge = "badge-normal"
                elif tiempo_restante > 10.0:
                    etiqueta_estado = "Fase 2: Deshidratación Constante"
                    clase_badge = "badge-normal"
                else:
                    etiqueta_estado = "Fase 3: Etapa Final de Secado"
                    clase_badge = "badge-final"

                fila = {
                    'Timestamp': ahora,
                    'Temp_Ambiente': temp_amb,
                    'Humedad_Ambiente': hum_amb,
                    'Temp_Grano': temp_grano,
                    'Temp_Ideal': st.session_state.temp_ideal_consigna,
                    'Tiempo_Restante_Estimado': round(tiempo_restante, 1)
                }
                st.session_state.historial = pd.concat([
                    st.session_state.historial,
                    pd.DataFrame([fila])
                ], ignore_index=True).tail(60)

                # Renderizado del Semáforo Térmico
                if color_led == "VERDE":
                    css_banner = "semaforo-verde"
                    icono_banner = "🟢"
                    texto_banner = "TEMPERATURA IDEAL ALCANZADA (Diferencia ≤ ±1.0°C)"
                    accion_banner = "Ventilador APAGADO (0%) — Preservando temperatura ideal de secado"
                elif color_led == "AMARILLO":
                    css_banner = "semaforo-amarillo"
                    icono_banner = "🟡"
                    texto_banner = "EN CAMINO A LA TEMPERATURA IDEAL (Diferencia ≤ 3.5°C)"
                    accion_banner = "Ventilador al 60% (PWM 153) — Estabilización suave en curso"
                else:
                    css_banner = "semaforo-rojo"
                    icono_banner = "🔴"
                    texto_banner = "FALTA MUCHO PARA LA TEMPERATURA IDEAL (Diferencia > 3.5°C)"
                    accion_banner = "Ventilador al 100% (PWM 255) — Máxima convección para forzar ajuste"

                with semaforo_area:
                    delta_t = temp_grano - st.session_state.temp_ideal_consigna
                    st.markdown(f"""
                    <div class="semaforo-banner {css_banner}">
                        <div>
                            <div style="font-size: 1.15rem; font-weight: 800; display: flex; align-items: center; gap: 8px;">
                                {icono_banner} {texto_banner}
                            </div>
                            <div style="font-size: 0.92rem; margin-top: 4px; opacity: 0.92;">
                                ⚙️ {accion_banner}
                            </div>
                        </div>
                        <div class="badge-semaforo-pill">
                            Consigna: {st.session_state.temp_ideal_consigna:.1f}°C | Grano: {temp_grano:.1f}°C (Δ {delta_t:+.1f}°C)
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                with metrics_area:
                    col1, col2, col3, col4 = st.columns([1, 1, 1.2, 1.3])
                    with col1:
                        st.metric("🌡️ Temp. Ambiente", f"{temp_amb:.1f} °C", delta=f"{temp_amb - 25.0:+.1f} vs ref")
                    with col2:
                        st.metric("💧 Humedad Relativa", f"{hum_amb:.1f} %", delta=f"{hum_amb - 60.0:+.1f} vs ref", delta_color="inverse")
                    with col3:
                        delta_grano_ideal = temp_grano - st.session_state.temp_ideal_consigna
                        st.metric(
                            "🌾 Temp. Grano",
                            f"{temp_grano:.1f} °C",
                            delta=f"{delta_grano_ideal:+.1f}°C vs ideal ({st.session_state.temp_ideal_consigna:.1f}°C)",
                            delta_color="off" if abs(delta_grano_ideal) <= 1.0 else ("inverse" if delta_grano_ideal > 0 else "normal")
                        )
                    with col4:
                        st.markdown(f"""
                        <div class="prediction-card">
                            <div class="prediction-title">⏱️ Tiempo Estimado Restante</div>
                            <div class="prediction-value">{tiempo_restante:.1f}</div>
                            <div class="prediction-unit">Horas de secado</div>
                            <div class="prediction-badge {clase_badge}">{etiqueta_estado}</div>
                        </div>
                        """, unsafe_allow_html=True)

                with charts_area:
                    if not st.session_state.historial.empty:
                        st.markdown("#### 📈 Dinámica Térmica y Cinética de Secado")
                        df_chart = st.session_state.historial.set_index('Timestamp')
                        c_ch1, c_ch2 = st.columns(2)
                        with c_ch1:
                            st.caption("Seguimiento de Lazo Cerrado (Temp. Grano vs Temp. Ideal)")
                            cols_plot = ['Temp_Grano', 'Temp_Ideal', 'Temp_Ambiente'] if 'Temp_Ideal' in df_chart.columns else ['Temp_Grano', 'Temp_Ambiente']
                            st.line_chart(df_chart[cols_plot], height=240)
                        with c_ch2:
                            st.caption("Curva de Tiempo Restante Estimado por IA (Horas)")
                            st.line_chart(df_chart[['Tiempo_Restante_Estimado']], height=240, color="#00b4d8")

                with log_area:
                    st.text(f"[{ahora}] Datos: '{raw_line}' | Semáforo: {color_led} | Fan: {label_fan} | Predicción: {tiempo_restante:.2f} h")

            except (ValueError, IndexError) as err_ruido:
                st.session_state.lineas_corruptas += 1
                with log_area:
                    st.warning(f"⚠️ [Ruido eléctrico] Trama descartada: '{raw_line}'. Causa: {err_ruido}")
                continue

            except (serial.SerialException, OSError) as err_desconexion:
                st.session_state.analisis_en_ejecucion = False
                st.session_state.serial_conn = None
                status_area.error(f"🔌 **Dispositivo desconectado:** Se perdió la comunicación física ({err_desconexion}).")
                st.stop()

            except Exception as e:
                with log_area:
                    st.error(f"Excepción inesperada: {e}")
                time.sleep(0.05)

    else:
        status_area.warning("⚠️ Análisis en pausa. Selecciona tu región de Perú y presiona **'▶ Iniciar Análisis'** para enviar la consigna y comenzar la regulación continua.")
        if not st.session_state.historial.empty:
            st.markdown("#### 📊 Últimos datos registrados en la sesión")
            st.dataframe(st.session_state.historial, use_container_width=True)

# ------------------------------------------------------------------------------
# PESTAÑA 3: DIAGNÓSTICO Y ESTADO DE COMPONENTES
# ------------------------------------------------------------------------------
with tab_estado:
    st.subheader("🩺 Panel de Diagnóstico Integral del Sistema")
    st.caption("Supervisión en tiempo real del estado operativo de sensores, actuadores, bus de comunicación y motor de IA.")

    # 1. ESTADO DE SENSORES
    st.markdown("### 📡 1. Sensores de Telemetría")
    col_s1, col_s2 = st.columns(2)

    with col_s1:
        st.markdown(f"""
        <div class="diag-card">
            <div class="diag-title">
                🌡️ Sensor DHT22 (Ambiente)
                <span class="diag-pin">Pin D2</span>
            </div>
            <p><strong>Estado Operativo:</strong> <span class="diag-status-ok">{st.session_state.sensor_dht_estado}</span></p>
            <p><strong>Última Temp. Ambiente:</strong> {f"{st.session_state.ultima_temp_amb:.1f} °C" if st.session_state.ultima_temp_amb is not None else "Sin datos"}</p>
            <p><strong>Última Humedad Relativa:</strong> {f"{st.session_state.ultima_hum_amb:.1f} %" if st.session_state.ultima_hum_amb is not None else "Sin datos"}</p>
            <p><strong>Rango Físico Válido:</strong> -10°C a 80°C | 0% a 100% HR</p>
            <p class="diag-muted">Última actualización: {st.session_state.ultima_hora_lectura}</p>
        </div>
        """, unsafe_allow_html=True)

    with col_s2:
        es_sobrecalentado = (st.session_state.ultima_temp_grano is not None and st.session_state.ultima_temp_grano > 45.0)
        color_ds = "diag-status-warn" if es_sobrecalentado else "diag-status-ok"
        st.markdown(f"""
        <div class="diag-card">
            <div class="diag-title">
                🌾 Sensor DS18B20 (Masa de Grano)
                <span class="diag-pin">Pin D3 (OneWire)</span>
            </div>
            <p><strong>Estado Operativo:</strong> <span class="{color_ds}">{st.session_state.sensor_ds_estado}</span></p>
            <p><strong>Última Temp. del Grano:</strong> {f"{st.session_state.ultima_temp_grano:.1f} °C" if st.session_state.ultima_temp_grano is not None else "Sin datos"}</p>
            <p><strong>Umbral Crítico de Calidad:</strong> 45.0 °C (Preserva embrión de café/cacao)</p>
            <p><strong>Condición Térmica:</strong> {'⚠️ ALERTA: Grano en riesgo térmico' if es_sobrecalentado else '✅ Óptima conservación'}</p>
            <p class="diag-muted">Última actualización: {st.session_state.ultima_hora_lectura}</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # 2. ESTADO DE ACTUADORES Y CONTROL EN LAZO CERRADO
    st.markdown("### ⚙️ 2. Actuadores y Etapas de Potencia (Lazo Cerrado ML)")
    
    # Resumen de consigna térmica activa
    st.info(
        f"🎯 **Consigna Térmica Activa en Arduino:** `{st.session_state.temp_ideal_consigna:.1f} °C` | "
        f"**Región Configurada:** `{st.session_state.region_seleccionada}` | "
        f"**Semáforo Actual:** `{st.session_state.color_semaforo_led}`"
    )

    col_a1, col_a2, col_a3 = st.columns(3)

    with col_a1:
        st.markdown(f"""
        <div class="diag-card">
            <div class="diag-title">🟢 LED Verde <span class="diag-pin">Pin D4</span></div>
            <p><strong>Función en Lazo:</strong> Meta Térmica Alcanzada (±1.0°C)</p>
            <p><strong>Estado:</strong> {'<span class="diag-status-ok">ENCENDIDO</span>' if st.session_state.estado_led_verde else '<span class="diag-status-off">Apagado</span>'}</p>
            <p class="diag-muted">Se activa cuando el grano llega a la temperatura ideal calculada por el ML. Apaga el ventilador.</p>
        </div>
        """, unsafe_allow_html=True)

    with col_a2:
        st.markdown(f"""
        <div class="diag-card">
            <div class="diag-title">🟡 LED Amarillo <span class="diag-pin">Pin D6</span></div>
            <p><strong>Función en Lazo:</strong> En Camino a la Ideal (1.0°C a 3.5°C)</p>
            <p><strong>Estado:</strong> {'<span class="diag-status-warn">ENCENDIDO</span>' if st.session_state.estado_led_amarillo else '<span class="diag-status-off">Apagado</span>'}</p>
            <p class="diag-muted">Aproximación progresiva. El ventilador modula al 60% PWM (153) para estabilización suave.</p>
        </div>
        """, unsafe_allow_html=True)

    with col_a3:
        st.markdown(f"""
        <div class="diag-card">
            <div class="diag-title">🔴 LED Rojo <span class="diag-pin">Pin D5</span></div>
            <p><strong>Función en Lazo:</strong> Falta Mucho / Desviación (>3.5°C)</p>
            <p><strong>Estado:</strong> {'<span class="diag-status-err">ENCENDIDO</span>' if st.session_state.estado_led_rojo else '<span class="diag-status-off">Apagado</span>'}</p>
            <p class="diag-muted">Diferencia térmica amplia. El ventilador opera al 100% PWM (255) a máxima potencia.</p>
        </div>
        """, unsafe_allow_html=True)

    col_a4, col_a5 = st.columns(2)

    with col_a4:
        st.markdown(f"""
        <div class="diag-card">
            <div class="diag-title">💨 Ventilador de Convección <span class="diag-pin">Pin D9 PWM</span></div>
            <p><strong>Régimen Actual:</strong> <span class="diag-status-ok">{st.session_state.estado_ventilador}</span></p>
            <p><strong>Consigna de Regulación:</strong> <code>T:{st.session_state.temp_ideal_consigna:.1f}°C</code></p>
            <p class="diag-muted">Se apaga al alcanzar la temperatura ideal (Verde). Se reactiva automáticamente si la temperatura se desvía.</p>
        </div>
        """, unsafe_allow_html=True)

    with col_a5:
        st.markdown(f"""
        <div class="diag-card">
            <div class="diag-title">📟 Pantalla LCD 16x2 <span class="diag-pin">Pines A4 (SDA) / A5 (SCL) I2C</span></div>
            <p><strong>Línea 1 Telemetría:</strong> <code>A:&lt;TempAmb&gt; H:&lt;HumAmb&gt;</code></p>
            <p><strong>Línea 2 Telemetría:</strong> <code>G:&lt;TempGrano&gt; Id:&lt;TempIdeal&gt;</code></p>
            <p class="diag-muted">Muestra en tiempo real Temperatura Ambiente, Humedad, Grano y la Consigna Ideal fijada por ML.</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # 3. ENLACE DE COMUNICACIONES Y MACHINE LEARNING
    st.markdown("### 🔌 3. Canal de Comunicación y Motor IA")
    col_c1, col_c2 = st.columns(2)

    with col_c1:
        total_recibidas = len(st.session_state.historial) + st.session_state.lineas_corruptas
        tasa_integridad = (len(st.session_state.historial) / total_recibidas * 100) if total_recibidas > 0 else 100.0
        st.markdown(f"""
        <div class="diag-card">
            <div class="diag-title">🔌 Enlace Serial / Gateway</div>
            <p><strong>Puerto Seleccionado:</strong> <code>{st.session_state.puerto_actual or puerto_seleccionado}</code></p>
            <p><strong>Velocidad de Transmisión:</strong> {baud_rate} Baudios</p>
            <p><strong>Lecturas Válidas Procesadas:</strong> {len(st.session_state.historial)}</p>
            <p><strong>Tramas Descartadas (Ruido eléctrico):</strong> {st.session_state.lineas_corruptas}</p>
            <p><strong>Tasa de Integridad de Señal:</strong> {tasa_integridad:.1f}%</p>
        </div>
        """, unsafe_allow_html=True)

    with col_c2:
        st.markdown(f"""
        <div class="diag-card">
            <div class="diag-title">🤖 Motor de Inferencia Machine Learning</div>
            <p><strong>Algoritmo:</strong> Random Forest Regressor (Scikit-Learn)</p>
            <p><strong>Variables de Entrada:</strong> <code>Temp_Ambiente</code>, <code>Humedad_Ambiente</code>, <code>Temp_Grano</code></p>
            <p><strong>Variable Objetivo:</strong> <code>Tiempo_Restante_Horas</code></p>
            <p><strong>Precisión ($R^2$ Score):</strong> {f"{info_modelo['r2']:.3f}" if info_modelo.get('r2') is not None else "N/A"}</p>
            <p><strong>Error Medio Absoluto (MAE):</strong> {f"{info_modelo['mae']:.2f} horas" if info_modelo.get('mae') is not None else "N/A"}</p>
        </div>
        """, unsafe_allow_html=True)

# ==============================================================================
# 6. PIE DE PÁGINA
# ==============================================================================
st.markdown("---")
col_f1, col_f2, col_f3 = st.columns(3)
col_f1.caption(f"Lecturas registradas: **{len(st.session_state.historial)}**")
col_f2.caption(f"Tramas con ruido descartadas: **{st.session_state.lineas_corruptas}**")
col_f3.caption("IoT Gateway Bidireccional | Diagnóstico de Componentes & ML")
