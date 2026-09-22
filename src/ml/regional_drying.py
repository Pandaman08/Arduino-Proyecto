"""
Módulo de Agrometeorología y Machine Learning Regional de Perú para Secado.
Calcula la temperatura ideal de secado en función de la región geográfica,
humedad ambiental y precipitación, y clasifica el estado del lazo de control.
"""

from typing import Dict, Any, Tuple
from ..config import (
    PERU_REGIONS_DATA,
    DEFAULT_IDEAL_TEMP,
    TOLERANCIA_IDEAL_TEMP,
    UMBRAL_CERCA_TEMP,
    CRITICAL_GRAIN_OVERHEAT_THRESHOLD
)


def predict_ideal_temperature(
    region_name: str,
    hum_ambiente: float,
    temp_ambiente: float
) -> float:
    """
    Predice la temperatura ideal de secado para café/cacao calibrada según
    la región de Perú y las condiciones psicrométricas en tiempo real.
    
    Parámetros:
        region_name: Nombre de la región cafetalera de Perú.
        hum_ambiente: Humedad relativa actual del aire (%).
        temp_ambiente: Temperatura ambiental del aire (°C).
        
    Retorna:
        Temperatura ideal de secado redondeada a 1 decimal (°C),
        acotada en el rango agronómicamente seguro [35.0, 43.0].
    """
    profile = PERU_REGIONS_DATA.get(region_name)
    if profile is None:
        base_temp = DEFAULT_IDEAL_TEMP
        typical_hum = 70.0
    else:
        base_temp = float(profile["temp_base_ideal"])
        typical_hum = float(profile["humedad_tipica"])

    # Factor de corrección psicrométrico por desviación de humedad relativa:
    # A mayor humedad, se requiere elevar levemente la temperatura de consigna
    # para incrementar el gradiente de presión de vapor de agua sin cocer el grano.
    delta_hum = hum_ambiente - typical_hum
    ajuste_hum = delta_hum * 0.06

    # Corrección ambiental moderada
    ajuste_temp = (temp_ambiente - 25.0) * 0.04

    temp_calculada = base_temp + ajuste_hum + ajuste_temp

    # Acotamiento para escala prototipo (-15°C para demostración en vivo con temperatura ambiente):
    # Permite validación visual inmediata en aula/laboratorio entre 20.0°C y 28.5°C
    temp_ideal = max(20.0, min(28.5, temp_calculada))
    return round(temp_ideal, 1)


def evaluate_thermal_state(
    measured_temp: float,
    ideal_temp: float
) -> Tuple[str, str, int, str]:
    """
    Evalúa la proximidad de la temperatura medida respecto a la temperatura ideal
    y determina el estado de los indicadores luminosos y el ventilador.
    
    Retorna una tupla con:
        (estado_codigo, color_led, pwm_ventilador, etiqueta_ventilador)
        
    Valores posibles de color_led:
        - 'VERDE': Ideal alcanzada (|error| <= 0.8°C), Fan 0
        - 'AMARILLO': En camino (0.8°C < |error| <= 2.2°C), Fan 153 (60%)
        - 'ROJO': Falta mucho (|error| > 2.2°C), Fan 255 (100%)
    """
    error = round(abs(measured_temp - ideal_temp), 2)

    if error <= TOLERANCIA_IDEAL_TEMP:
        return (
            "IDEAL_ALCANZADA",
            "VERDE",
            0,
            "0% (Apagado - Meta alcanzada)"
        )
    elif error <= UMBRAL_CERCA_TEMP:
        return (
            "EN_CAMINO",
            "AMARILLO",
            153,
            "60% (PWM 153 - Estabilización)"
        )
    else:
        return (
            "FALTA_MUCHO",
            "ROJO",
            255,
            "100% (PWM 255 - Máxima convección)"
        )
