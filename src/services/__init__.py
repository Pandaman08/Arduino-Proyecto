"""Servicios de aplicación que coordinan hardware e inferencia sin depender de Streamlit."""

from .monitoring import TelemetryProcessor, TelemetryResult

__all__ = ["TelemetryProcessor", "TelemetryResult"]
