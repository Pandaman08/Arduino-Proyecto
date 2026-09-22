"""
Capa de interfaz gráfica y componentes de usuario para Streamlit.
"""

from .styles import CUSTOM_CSS
from .components import (
    render_header,
    render_sidebar_controls,
    render_metrics_panel,
    render_trend_charts,
    render_status_banner,
    render_footer
)

__all__ = [
    "CUSTOM_CSS",
    "render_header",
    "render_sidebar_controls",
    "render_metrics_panel",
    "render_trend_charts",
    "render_status_banner",
    "render_footer"
]
