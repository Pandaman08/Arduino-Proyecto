"""
Módulo de Comunicación Serial y Procesamiento de Señales IoT.
Gestiona el ciclo de vida del puerto COM/tty, parseo de tramas y filtrado de ruido eléctrico.
"""

import time
import os
from dataclasses import dataclass
from typing import Optional, List, Tuple
import numpy as np
import serial
import serial.tools.list_ports

from ..config import (
    TEMP_MIN_CELSIUS,
    TEMP_MAX_CELSIUS,
    HUM_MIN_PERCENT,
    HUM_MAX_PERCENT,
    TEMP_GRANO_MAX_CELSIUS,
    SERIAL_TIMEOUT_SECONDS,
    SERIAL_STABILIZATION_DELAY,
    DEFAULT_BAUDRATE
)


@dataclass(frozen=True)
class TelemetryReading:
    """Estructura inmutable que representa una lectura válida de sensores."""
    temp_ambiente: float
    humedad_ambiente: float
    temp_grano: float

    def as_tuple(self) -> Tuple[float, float, float]:
        """Devuelve los valores en tupla para procesamiento numérico."""
        return (self.temp_ambiente, self.humedad_ambiente, self.temp_grano)


def detect_available_ports() -> List[str]:
    """Lista todos los puertos seriales activos detectados por el sistema operativo."""
    return [port.device for port in serial.tools.list_ports.comports()]


def get_default_port() -> str:
    """Devuelve un puerto serial sugerido según el sistema operativo."""
    ports = detect_available_ports()
    if ports:
        return ports[0]
    return "COM3" if os.name == 'nt' else "/dev/ttyUSB0"


def parse_telemetry_line(raw_line: str) -> Optional[TelemetryReading]:
    """
    Decodifica y valida una trama de texto proveniente del microcontrolador.
    
    Formato esperado: 'Temp_Ambiente,Humedad_Ambiente,Temp_Grano'
    Ejemplo: '28.5,65.0,26.2'
    
    Raises:
        ValueError: Si la línea está incompleta, corrupta o contiene valores fuera de rango físico.
    """
    line = raw_line.strip()
    if not line:
        return None

    parts = line.split(',')
    if len(parts) != 3:
        raise ValueError(f"Trama truncada o corrupta ({len(parts)} campos recibidos, esperados 3): '{line}'")

    try:
        temp_amb = float(parts[0].strip())
        hum_amb = float(parts[1].strip())
        temp_grano = float(parts[2].strip())
    except ValueError as e:
        raise ValueError(f"Caracteres no numéricos en la trama: '{line}' ({e})")

    # Validación de plausibilidad física (filtrado de rebotes o glitches)
    if not (TEMP_MIN_CELSIUS <= temp_amb <= TEMP_MAX_CELSIUS):
        raise ValueError(f"Temperatura ambiente fuera de rango plausible: {temp_amb}°C")
    if not (HUM_MIN_PERCENT <= hum_amb <= HUM_MAX_PERCENT):
        raise ValueError(f"Humedad relativa fuera de rango plausible: {hum_amb}%")
    if not (TEMP_MIN_CELSIUS <= temp_grano <= TEMP_GRANO_MAX_CELSIUS):
        raise ValueError(f"Temperatura de grano fuera de rango plausible: {temp_grano}°C")

    return TelemetryReading(
        temp_ambiente=temp_amb,
        humedad_ambiente=hum_amb,
        temp_grano=temp_grano
    )


def generate_simulated_telemetry() -> TelemetryReading:
    """Genera lecturas sintéticas consistentes con la física del secado para pruebas sin hardware."""
    sim_temp_amb = round(float(np.random.uniform(22.0, 36.0)), 1)
    sim_hum_amb = round(float(np.random.uniform(45.0, 75.0)), 1)
    sim_temp_grano = round(sim_temp_amb + float(np.random.uniform(-1.0, 4.0)), 1)
    
    return TelemetryReading(
        temp_ambiente=sim_temp_amb,
        humedad_ambiente=sim_hum_amb,
        temp_grano=sim_temp_grano
    )


class SerialManager:
    """
    Administrador del puerto serial con soporte para context manager (with)
    y manejo robusto de excepciones de desconexión física.
    """

    def __init__(self, port: str, baudrate: int = DEFAULT_BAUDRATE, timeout: float = SERIAL_TIMEOUT_SECONDS):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial: Optional[serial.Serial] = None

    def connect(self) -> None:
        """Abre la conexión serial y estabiliza el microcontrolador."""
        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=2.0
            )
            # Drenar posibles residuos en búfer
            self._serial.reset_input_buffer()
            time.sleep(SERIAL_STABILIZATION_DELAY)
        except serial.SerialException as err:
            self._serial = None
            raise serial.SerialException(f"No fue posible abrir el puerto serial '{self.port}': {err}")

    def is_open(self) -> bool:
        """Indica si el puerto se encuentra abierto."""
        return self._serial is not None and self._serial.is_open

    def read_line(self) -> Optional[str]:
        """
        Lee una línea de texto del puerto serie.
        Retorna None si se produce un timeout normal sin datos recibidos.
        """
        if not self.is_open():
            raise serial.SerialException("Intento de lectura con puerto serial cerrado.")

        raw_bytes = self._serial.readline()
        if not raw_bytes:
            return None

        return raw_bytes.decode('utf-8', errors='ignore').strip()

    def close(self) -> None:
        """Cierra de forma segura el descriptor de archivo del puerto serie."""
        if self._serial is not None:
            try:
                if self._serial.is_open:
                    self._serial.close()
            except Exception:
                pass
            finally:
                self._serial = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
