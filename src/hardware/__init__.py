"""
Capa de abstracción de hardware y comunicación serial.
"""

from .serial_manager import (
    SerialManager,
    TelemetryReading,
    parse_telemetry_line,
    generate_simulated_telemetry,
    detect_available_ports
)

__all__ = [
    "SerialManager",
    "TelemetryReading",
    "parse_telemetry_line",
    "generate_simulated_telemetry",
    "detect_available_ports"
]
