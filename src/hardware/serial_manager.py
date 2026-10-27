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
from .port_lock import SerialPortInUseError, SerialPortLease


@dataclass(frozen=True)
class TelemetryReading:
    """Estructura inmutable que representa una lectura válida de sensores."""
    temp_ambiente: float
    humedad_ambiente: float
    temp_grano: float

    def as_tuple(self) -> Tuple[float, float, float]:
        """Devuelve los valores en tupla para procesamiento numérico."""
        return (self.temp_ambiente, self.humedad_ambiente, self.temp_grano)


@dataclass(frozen=True)
class SerialTelemetryFrame:
    """Trama enriquecida del firmware, manteniendo compatibilidad con CSV antiguo."""
    reading: TelemetryReading
    sequence: Optional[int] = None
    setpoint: Optional[float] = None
    mode: Optional[str] = None
    heater_state: Optional[str] = None
    fan_pwm: Optional[int] = None


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


def parse_telemetry_frame(raw_line: str) -> Optional[SerialTelemetryFrame]:
    """Parsea ``TEL,seq,t_amb,hum,t_grano,sp,modo,foco,vent`` o el CSV legado."""
    line = raw_line.strip()
    if not line:
        return None
    if not line.upper().startswith("TEL,"):
        reading = parse_telemetry_line(line)
        return None if reading is None else SerialTelemetryFrame(reading=reading)
    parts = [part.strip() for part in line.split(",")]
    if len(parts) != 9:
        raise ValueError(f"Trama TEL incompleta ({len(parts)} campos recibidos, esperados 9): '{line}'")
    try:
        sequence = int(parts[1])
        setpoint = None if parts[5].upper() in {"", "NA", "NULL"} else float(parts[5])
        fan_pwm = None if parts[8].upper() in {"", "NA", "NULL"} else int(parts[8])
    except ValueError as error:
        raise ValueError(f"Campos TEL no numéricos: '{line}'") from error
    if sequence < 0:
        raise ValueError("sequence no puede ser negativo")
    if setpoint is not None and not 10.0 <= setpoint <= 50.0:
        raise ValueError(f"setpoint fuera de rango: {setpoint}")
    if fan_pwm is not None and not 0 <= fan_pwm <= 255:
        raise ValueError(f"PWM fuera de rango: {fan_pwm}")
    mode = parts[6].upper()
    if mode not in {"MONITOREO", "CONTROL"}:
        raise ValueError(f"modo serial inválido: {parts[6]}")
    heater_state = None if parts[7].upper() in {"", "NA", "NULL"} else parts[7]
    reading = parse_telemetry_line(",".join(parts[2:5]))
    return SerialTelemetryFrame(reading, sequence, setpoint, mode, heater_state, fan_pwm)


def generate_simulated_telemetry(
    ideal_temperature: Optional[float] = None,
    previous_grain: Optional[float] = None,
) -> TelemetryReading:
    """Genera telemetría sintética, opcionalmente siguiendo el lazo térmico de la demo."""
    sim_temp_amb = round(float(np.random.uniform(22.0, 36.0)), 1)
    sim_hum_amb = round(float(np.random.uniform(45.0, 75.0)), 1)
    if ideal_temperature is None or previous_grain is None:
        sim_temp_grano = round(sim_temp_amb + float(np.random.uniform(-1.0, 4.0)), 1)
    else:
        error = previous_grain - ideal_temperature
        if abs(error) > 2.2:
            grain = previous_grain - 0.8
        elif abs(error) > 0.8:
            grain = previous_grain - 0.4
        else:
            grain = ideal_temperature + float(np.random.choice([-0.2, 0.0, 0.2, 1.8], p=[0.3, 0.4, 0.2, 0.1]))
        sim_temp_grano = round(grain, 1)
    
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
        self._lease: Optional[SerialPortLease] = None

    def connect(self) -> None:
        """Abre la conexión serial y estabiliza el microcontrolador."""
        lease = SerialPortLease(self.port)
        try:
            lease.acquire()
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
            lease.release()
            self._serial = None
            raise serial.SerialException(f"No fue posible abrir el puerto serial '{self.port}': {err}")
        except SerialPortInUseError as err:
            self._serial = None
            raise serial.SerialException(str(err)) from err
        except Exception:
            lease.release()
            self._serial = None
            raise
        self._lease = lease

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

    def send_command(self, command: str) -> None:
        """Envía un comando textual al firmware usando una única interfaz de transporte."""
        if not self.is_open():
            raise serial.SerialException("Intento de escritura con puerto serial cerrado.")

        payload = command if command.endswith("\n") else f"{command}\n"
        self._serial.write(payload.encode("utf-8"))
        self._serial.flush()

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
                if self._lease is not None:
                    self._lease.release()
                    self._lease = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
