"""
Capa de abstracción de hardware y comunicación serial.
"""

from .serial_manager import (
    SerialManager,
    SerialTelemetryFrame,
    TelemetryReading,
    parse_telemetry_frame,
    parse_telemetry_line,
    generate_simulated_telemetry,
    detect_available_ports
)

__all__ = [
    "SerialManager",
    "SerialTelemetryFrame",
    "TelemetryReading",
    "parse_telemetry_frame",
    "parse_telemetry_line",
    "generate_simulated_telemetry",
    "detect_available_ports"
]
