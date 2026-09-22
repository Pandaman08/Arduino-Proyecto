"""
Pruebas Unitarias para el Control de Temperatura Ideal y Agrometeorología Regional (Perú).
Valida predicción de consignas por región, semáforo LED y modulación de ventilador.
"""

import pytest
from src.ml.regional_drying import predict_ideal_temperature, evaluate_thermal_state
from src.config import (
    PERU_REGIONS_DATA,
    DEFAULT_IDEAL_TEMP,
    TOLERANCIA_IDEAL_TEMP,
    UMBRAL_CERCA_TEMP
)


def test_predict_ideal_temperature_regions():
    """Valida que cada región del Perú obtenga consignas térmicas coherentes en escala prototipo."""
    for region_name in PERU_REGIONS_DATA:
        temp_ideal = predict_ideal_temperature(
            region_name=region_name,
            hum_ambiente=70.0,
            temp_ambiente=26.0
        )
        assert isinstance(temp_ideal, float)
        # La temperatura prototipo debe mantenerse en el rango de demo en vivo (20°C a 28.5°C)
        assert 20.0 <= temp_ideal <= 28.5


def test_predict_ideal_temperature_san_martin_vs_cajamarca():
    """
    San Martín (alta precipitación y humedad) debe requerir mayor temperatura
    de secado que Cajamarca (clima más seco) para prevenir proliferación de moho.
    """
    temp_sm = predict_ideal_temperature("San Martín (Moyobamba / Tarapoto)", hum_ambiente=85.0, temp_ambiente=28.0)
    temp_caj = predict_ideal_temperature("Cajamarca (Jaén / San Ignacio)", hum_ambiente=60.0, temp_ambiente=24.0)

    assert temp_sm > temp_caj
    assert temp_sm >= 25.0
    assert temp_caj <= 23.5


def test_evaluate_thermal_state_green_target_reached():
    """Valida el encendido de LED Verde y apagado de ventilador cuando se alcanza la temperatura ideal."""
    ideal = 23.0  # Escala prototipo para demostración en vivo
    
    # Exactamente en la ideal o dentro de la tolerancia de ±1.0°C (22.0°C a 24.0°C)
    for temp in [23.0, 23.5, 22.2, 24.0, 22.0]:
        state, led, pwm, label = evaluate_thermal_state(measured_temp=temp, ideal_temp=ideal)
        assert state == "IDEAL_ALCANZADA"
        assert led == "VERDE"
        assert pwm == 0  # Ventilador apagado
        assert "Apagado" in label


def test_evaluate_thermal_state_yellow_on_the_way():
    """Valida LED Amarillo y ventilador a 60% (PWM 153) cuando está en camino (1.0°C a 3.5°C)."""
    ideal = 23.0
    
    # Temperaturas a distancia intermedia (24.1°C a 26.5°C o 19.5°C a 21.9°C)
    for temp in [24.5, 26.0, 21.5, 20.0]:
        state, led, pwm, label = evaluate_thermal_state(measured_temp=temp, ideal_temp=ideal)
        assert state == "EN_CAMINO"
        assert led == "AMARILLO"
        assert pwm == 153  # ~60% PWM
        assert "60%" in label


def test_evaluate_thermal_state_red_far_from_target():
    """Valida LED Rojo y ventilador a 100% (PWM 255) cuando falta mucho (> 3.5°C)."""
    ideal = 23.0
    
    # Temperaturas lejanas (> 26.5°C o < 19.5°C)
    for temp in [28.0, 32.0, 18.0, 15.0]:
        state, led, pwm, label = evaluate_thermal_state(measured_temp=temp, ideal_temp=ideal)
        assert state == "FALTA_MUCHO"
        assert led == "ROJO"
        assert pwm == 255  # 100% PWM
        assert "100%" in label

