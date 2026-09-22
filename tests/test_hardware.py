"""
Pruebas Unitarias para el Módulo de Hardware y Parseo de Señales IoT.
Valida la decodificación de tramas y el rechazo de ruido eléctrico.
"""

import pytest
from src.hardware.serial_manager import (
    parse_telemetry_line,
    generate_simulated_telemetry,
    TelemetryReading
)


def test_parse_valid_telemetry():
    """Valida la decodificación de una trama estándar emitida por el Arduino."""
    line = "28.5,65.0,26.2"
    reading = parse_telemetry_line(line)
    
    assert reading is not None
    assert isinstance(reading, TelemetryReading)
    assert reading.temp_ambiente == 28.5
    assert reading.humedad_ambiente == 65.0
    assert reading.temp_grano == 26.2
    assert reading.as_tuple() == (28.5, 65.0, 26.2)


def test_parse_empty_and_whitespace():
    """Verifica que tramas vacías retornen None sin generar excepciones."""
    assert parse_telemetry_line("") is None
    assert parse_telemetry_line("   \r\n") is None


def test_parse_truncated_line_rejects_noise():
    """Verifica que tramas truncadas por desconexión o rebote disparen ValueError."""
    with pytest.raises(ValueError, match="Trama truncada o corrupta"):
        parse_telemetry_line("28.5,65.0")  # Falta 1 campo


def test_parse_non_numeric_rejects_noise():
    """Verifica que caracteres no numéricos o basura en el puerto serie sean rechazados."""
    with pytest.raises(ValueError, match="Caracteres no numéricos"):
        parse_telemetry_line("28.5,ERR_DHT,26.2")


def test_parse_out_of_physical_range():
    """Verifica que picos de sensores físicamente imposibles sean filtrados."""
    with pytest.raises(ValueError, match="fuera de rango"):
        parse_telemetry_line("150.0,65.0,26.2")  # Temperatura ambiente imposible

    with pytest.raises(ValueError, match="fuera de rango"):
        parse_telemetry_line("28.5,120.0,26.2")  # Humedad > 100%


def test_simulated_telemetry_validity():
    """Verifica que las lecturas sintéticas del simulador cumplan los rangos físicos."""
    for _ in range(20):
        sim = generate_simulated_telemetry()
        assert 20.0 <= sim.temp_ambiente <= 40.0
        assert 40.0 <= sim.humedad_ambiente <= 80.0
        assert sim.temp_grano >= 18.0
