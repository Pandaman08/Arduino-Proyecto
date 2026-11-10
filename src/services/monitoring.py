"""Servicios de procesamiento de telemetría para el Gateway IoT.

Este módulo concentra la orquestación de una lectura: parseo, inferencia,
clasificación de etapa y evaluación del lazo térmico. No contiene código de UI,
MQTT ni persistencia, dejando esos adaptadores para fases posteriores.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Tuple

from ..hardware.serial_manager import TelemetryReading, parse_telemetry_line
from ..ml.model_manager import DryingPredictor
from ..ml.regional_drying import evaluate_thermal_state


@dataclass(frozen=True)
class TelemetryResult:
    """Resultado completo de procesar una lectura válida."""

    reading: TelemetryReading
    timestamp: str
    remaining_hours: float
    stage_info: Tuple[str, str]
    thermal_state: Tuple[str, str, int, str]


class TelemetryProcessor:
    """Coordina el pipeline de una trama sin conocer el mecanismo de transporte."""

    def __init__(self, predictor: DryingPredictor):
        self.predictor = predictor

    def process(self, raw_line: str, ideal_temperature: float) -> TelemetryResult | None:
        """Procesa una trama CSV; ignora mensajes de protocolo no telemétricos."""
        line = raw_line.strip()
        if not line or line.startswith("ACK") or line.startswith("SISTEMA"):
            return None

        reading = parse_telemetry_line(line)
        if reading is None:
            return None

        remaining_hours = self.predictor.predict(*reading.as_tuple())
        stage_info = self.predictor.get_drying_stage_info(
            remaining_hours=remaining_hours,
            grain_temp=reading.temp_grano,
        )
        thermal_state = evaluate_thermal_state(
            measured_temp=reading.temp_grano,
            ideal_temp=ideal_temperature,
        )
        return TelemetryResult(
            reading=reading,
            timestamp=datetime.now().strftime("%H:%M:%S"),
            remaining_hours=remaining_hours,
            stage_info=stage_info,
            thermal_state=thermal_state,
        )
