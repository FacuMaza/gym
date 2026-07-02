"""Integración puerta + Django settings."""
from __future__ import annotations

from typing import Optional

from .puerta_serial_core import ControlPuertaSerial, PuertaConfig, detectar_puerto_arduino

_controller: Optional[ControlPuertaSerial] = None


def _config_desde_settings() -> PuertaConfig:
    from django.conf import settings

    return PuertaConfig(
        port=(getattr(settings, 'DOOR_ARDUINO_PORT', '') or '').strip(),
        baud=int(getattr(settings, 'DOOR_ARDUINO_BAUD', 9600)),
        pulse_ms=int(getattr(settings, 'DOOR_ARDUINO_PULSE_MS', 3000)),
        open_delay=float(getattr(settings, 'DOOR_ARDUINO_OPEN_DELAY', 2.0)),
    )


def _controller_activo() -> ControlPuertaSerial:
    global _controller
    if _controller is None:
        _controller = ControlPuertaSerial(_config_desde_settings())
    return _controller


def abrir_puerta(pulse_ms: Optional[int] = None, *, forzar: bool = False) -> tuple[bool, str]:
    from django.conf import settings

    if not forzar and not getattr(settings, 'DOOR_ARDUINO_ENABLED', False):
        return False, 'Puerta deshabilitada en configuración'
    return _controller_activo().abrir(pulse_ms)


def cerrar_conexion():
    global _controller
    if _controller:
        _controller.cerrar()
        _controller = None


def estado_puerta() -> dict:
    from django.conf import settings

    info = _controller_activo().estado()
    info['habilitada'] = bool(getattr(settings, 'DOOR_ARDUINO_ENABLED', False))
    if not info['habilitada']:
        info['mensaje'] = 'Deshabilitada (DOOR_ARDUINO_ENABLED=0)'
    return info


__all__ = ['abrir_puerta', 'cerrar_conexion', 'estado_puerta', 'detectar_puerto_arduino']
