"""Helpers de configuración de puerta por gimnasio."""
from __future__ import annotations

from django.conf import settings

from .models import ConfiguracionPuerta, Gimnasio
from .puerta_serial_core import PuertaConfig


def obtener_config_puerta(gimnasio: Gimnasio | None) -> ConfiguracionPuerta | None:
    if not gimnasio or not gimnasio.pk:
        return None
    config, _ = ConfiguracionPuerta.objects.get_or_create(gimnasio=gimnasio)
    return config


def puerta_serial_desde_config(config: ConfiguracionPuerta) -> PuertaConfig:
    return PuertaConfig(
        port=(config.puerto_arduino or '').strip(),
        baud=9600,
        pulse_ms=config.pulso_ms,
        open_delay=float(config.espera_serial),
    )


def datos_puerta_pantalla(gimnasio: Gimnasio | None) -> dict:
    config = obtener_config_puerta(gimnasio)
    if not config or not config.activa:
        return {
            'habilitada': False,
            'pulso_ms': 3000,
        }
    return {
        'habilitada': True,
        'pulso_ms': config.pulso_ms,
    }


def datos_puerta_api(config: ConfiguracionPuerta) -> dict:
    return {
        'activa': config.activa,
        'url_agente': config.url_agente,
        'token_agente': config.token_agente,
        'puerto_arduino': config.puerto_arduino,
        'pulso_ms': config.pulso_ms,
        'espera_serial': config.espera_serial,
    }


def agente_json_local(request, gimnasio: Gimnasio, config: ConfiguracionPuerta) -> dict:
    base = (getattr(settings, 'PUBLIC_BASE_URL', None) or '').strip().rstrip('/')
    if not base:
        base = request.build_absolute_uri('/').rstrip('/')
    return {
        'servidor': base,
        'gimnasio_id': gimnasio.pk,
        'token': config.token_agente,
    }
