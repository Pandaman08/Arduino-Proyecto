"""Serialización y validación del contrato JSON de telemetría MQTT."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from ..hardware.serial_manager import TelemetryReading


PROTOCOL_VERSION = "1.0"


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class TelemetryPayload:
    node_id: str
    timestamp_utc: str
    sequence: int
    t_amb: float
    hum: float
    t_grano: float
    simulado: bool
    sp: Optional[float] = None
    foco: Optional[str] = None
    vent: Optional[int] = None
    modo: Optional[str] = None
    protocol_version: str = PROTOCOL_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "node_id": self.node_id,
            # Alias de compatibilidad con los mensajes observados en EMQX:
            # id/ts. No se agregan aliases de actuadores si no fueron reportados.
            "id": self.node_id,
            "timestamp": self.timestamp_utc,
            "ts": self.timestamp_utc,
            "sequence": self.sequence,
            "seq": self.sequence,
            "t_amb": self.t_amb,
            "hum": self.hum,
            "t_grano": self.t_grano,
            "simulado": self.simulado,
            "version": self.protocol_version,
        }
        for key, value in (("sp", self.sp), ("foco", self.foco), ("vent", self.vent), ("modo", self.modo)):
            if value is not None:
                payload[key] = value
        if self.sp is not None:
            payload["t_ideal"] = self.sp
        if self.foco is not None:
            payload["led"] = self.foco
        if self.vent is not None:
            payload["ventilador_pwm"] = self.vent
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_reading(
        cls,
        node_id: str,
        sequence: int,
        reading: TelemetryReading,
        simulado: bool,
        **optional_fields: Any,
    ) -> "TelemetryPayload":
        return cls(
            node_id=node_id,
            timestamp_utc=optional_fields.pop("timestamp_utc", None) or utc_timestamp(),
            sequence=sequence,
            t_amb=reading.temp_ambiente,
            hum=reading.humedad_ambiente,
            t_grano=reading.temp_grano,
            simulado=simulado,
            **optional_fields,
        )


def parse_telemetry_payload(payload: str | bytes | dict[str, Any]) -> TelemetryPayload:
    """Valida un JSON MQTT sin aceptar telemetría incompleta o mal tipada."""
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as error:
            raise ValueError(f"JSON MQTT inválido: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("La telemetría MQTT debe ser un objeto JSON")
    required = {"t_amb", "hum", "t_grano"}
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"Faltan campos de telemetría: {', '.join(missing)}")
    node_id = payload.get("node_id", payload.get("id"))
    timestamp = payload.get("timestamp", payload.get("ts"))
    if not isinstance(node_id, str) or not node_id.strip():
        raise ValueError("node_id debe ser texto no vacío")
    if timestamp is None:
        raise ValueError("timestamp/ts es obligatorio")
    simulado = payload.get("simulado", node_id.startswith("sim"))
    if not isinstance(simulado, bool):
        raise ValueError("simulado debe ser booleano")
    try:
        sequence = int(payload.get("sequence", payload.get("seq", 0)))
        t_amb = float(payload["t_amb"])
        hum = float(payload["hum"])
        t_grano = float(payload["t_grano"])
    except (TypeError, ValueError) as error:
        raise ValueError("Los campos sequence/t_amb/hum/t_grano deben ser numéricos") from error
    if sequence < 0:
        raise ValueError("sequence no puede ser negativo")
    try:
        datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("timestamp debe ser ISO-8601") from error
    if not (-10 <= t_amb <= 80 and 0 <= hum <= 100 and -10 <= t_grano <= 85):
        raise ValueError("Telemetría fuera de rango físico")
    return TelemetryPayload(
        node_id=node_id, timestamp_utc=str(timestamp), sequence=sequence,
        t_amb=t_amb, hum=hum, t_grano=t_grano, simulado=simulado,
        sp=float(payload.get("sp", payload.get("t_ideal"))) if payload.get("sp", payload.get("t_ideal")) is not None else None,
        foco=str(payload.get("foco", payload.get("led"))) if payload.get("foco", payload.get("led")) is not None else None,
        vent=int(payload.get("vent", payload.get("ventilador_pwm"))) if payload.get("vent", payload.get("ventilador_pwm")) is not None else None,
        modo=str(payload["modo"]) if payload.get("modo") is not None else None,
        protocol_version=str(payload.get("version", payload.get("protocol_version", PROTOCOL_VERSION))),
    )
