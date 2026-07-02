"""
Lógica serial para Arduino (sin dependencia de Django).
Protocolo: PING->PONG, UNLOCK [ms]->OK
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

CH340_VID = 0x1A86
CH340_PID = 0x7523
ARDUINO_VID = 0x2341


@dataclass
class PuertaConfig:
    port: str = ''
    baud: int = 9600
    pulse_ms: int = 3000
    open_delay: float = 2.0


def _import_serial():
    try:
        import serial
        from serial.tools import list_ports
    except ImportError as exc:
        raise RuntimeError('Falta pyserial. Instalá: pip install pyserial') from exc
    return serial, list_ports


def detectar_puerto_arduino() -> Optional[str]:
    _, list_ports = _import_serial()
    candidatos = []
    for port in list_ports.comports():
        desc = (port.description or '').upper()
        if port.vid == CH340_VID and port.pid == CH340_PID:
            candidatos.append((0, port.device))
        elif port.vid == ARDUINO_VID:
            candidatos.append((1, port.device))
        elif 'CH340' in desc or 'ARDUINO' in desc:
            candidatos.append((2, port.device))
    if not candidatos:
        return None
    candidatos.sort(key=lambda item: item[0])
    return candidatos[0][1]


class ControlPuertaSerial:
    def __init__(self, config: PuertaConfig):
        self.config = config
        self._lock = threading.Lock()
        self._serial = None
        self._serial_port: Optional[str] = None

    def _abrir_puerto(self, port: str):
        serial, _ = _import_serial()
        ser = serial.Serial(port, self.config.baud, timeout=2, write_timeout=2)
        time.sleep(self.config.open_delay)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        return ser

    @staticmethod
    def _leer_linea(ser, timeout: float = 2.0) -> str:
        deadline = time.monotonic() + timeout
        buf = bytearray()
        while time.monotonic() < deadline:
            chunk = ser.read(ser.in_waiting or 1)
            if chunk:
                buf.extend(chunk)
                if b'\n' in buf:
                    line, _, rest = buf.partition(b'\n')
                    if rest:
                        ser.reset_input_buffer()
                    return line.decode('utf-8', errors='ignore').strip()
            else:
                time.sleep(0.05)
        return ''

    def _enviar(self, ser, comando: str, esperado: str = 'OK', timeout: float = 5.0) -> bool:
        ser.write(f'{comando}\n'.encode('utf-8'))
        ser.flush()
        respuesta = self._leer_linea(ser, timeout=timeout)
        if respuesta == esperado:
            return True
        logger.warning('Arduino respondió %r (esperado %r) a %r', respuesta, esperado, comando)
        return False

    def _conectar(self):
        port = self.config.port or detectar_puerto_arduino()
        if not port:
            raise RuntimeError('No se encontró Arduino en USB')

        if self._serial and self._serial.is_open and self._serial_port == port:
            return self._serial

        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None

        self._serial = self._abrir_puerto(port)
        self._serial_port = port
        if not self._enviar(self._serial, 'PING', esperado='PONG', timeout=3.0):
            self._serial.close()
            self._serial = None
            self._serial_port = None
            raise RuntimeError(f'Arduino en {port} no respondió PING/PONG')
        return self._serial

    def abrir(self, pulse_ms: Optional[int] = None) -> tuple[bool, str]:
        ms = pulse_ms if pulse_ms is not None else self.config.pulse_ms
        with self._lock:
            try:
                ser = self._conectar()
                ok = self._enviar(ser, f'UNLOCK {ms}', esperado='OK', timeout=max(5.0, ms / 1000 + 2))
                return (True, 'Puerta liberada') if ok else (False, 'Arduino no confirmó apertura')
            except Exception as exc:
                if self._serial:
                    try:
                        self._serial.close()
                    except Exception:
                        pass
                self._serial = None
                self._serial_port = None
                logger.exception('Error abriendo puerta')
                return False, str(exc)

    def ping(self) -> bool:
        with self._lock:
            try:
                ser = self._conectar()
                return self._enviar(ser, 'PING', esperado='PONG', timeout=2.0)
            except Exception:
                return False

    def cerrar(self):
        with self._lock:
            if self._serial:
                try:
                    self._serial.close()
                except Exception:
                    pass
            self._serial = None
            self._serial_port = None

    def estado(self) -> dict:
        port = self.config.port or detectar_puerto_arduino()
        info = {
            'puerto_configurado': self.config.port or None,
            'puerto_detectado': port,
            'conectada': False,
            'mensaje': '',
        }
        if not port:
            info['mensaje'] = 'Sin Arduino en USB'
            return info
        try:
            info['conectada'] = self.ping()
            info['mensaje'] = 'OK' if info['conectada'] else 'Sin respuesta PING'
        except Exception as exc:
            info['mensaje'] = str(exc)
        return info
