"""
Tokens de diseño, temas de color y estilos CSS para la interfaz web del Gateway.
"""

CUSTOM_CSS = """
<style>
    /* Tipografía y contenedor general */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Encabezado principal del Gateway */
    .main-header {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .main-header h1 {
        color: #ffffff !important;
        font-size: 2.1rem;
        font-weight: 700;
        margin: 0;
    }
    .main-header p {
        color: #e0e7ff;
        font-size: 1rem;
        margin-top: 0.4rem;
        margin-bottom: 0;
    }

    /* Tarjeta Destacada de Predicción de IA */
    .prediction-card {
        background: linear-gradient(135deg, #0d3b66 0%, #001e3d 100%);
        border: 2px solid #00b4d8;
        border-radius: 12px;
        padding: 1.25rem;
        text-align: center;
        color: white;
        box-shadow: 0 6px 20px rgba(0, 180, 216, 0.25);
    }
    .prediction-title {
        font-size: 0.85rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #caf0f8;
    }
    .prediction-value {
        font-size: 2.8rem;
        font-weight: 800;
        color: #90e0ef;
        margin: 0.2rem 0;
        line-height: 1.1;
    }
    .prediction-unit {
        font-size: 1.05rem;
        color: #caf0f8;
        font-weight: 500;
    }
    .prediction-badge {
        display: inline-block;
        margin-top: 0.5rem;
        padding: 0.35rem 0.85rem;
        border-radius: 20px;
        font-size: 0.82rem;
        font-weight: 600;
    }
    .status-normal {
        background-color: rgba(0, 180, 216, 0.2);
        color: #caf0f8;
    }
    .status-final {
        background-color: rgba(46, 204, 113, 0.25);
        color: #a3e635;
    }
    .alert-danger {
        background-color: rgba(239, 68, 68, 0.3);
        color: #fca5a5;
        border: 1px solid #ef4444;
    }

    /* Badges de conexión en la barra lateral */
    .badge-connected {
        background-color: #2ecc71;
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-disconnected {
        background-color: #e74c3c;
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
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
</style>
"""
