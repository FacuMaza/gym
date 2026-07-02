#!/usr/bin/env python3
"""
Agente de puerta para la PC del kiosco (USB + Arduino).
No requiere Django — solo Python 3 + pyserial.

Uso:
  pip install pyserial python-dotenv
  cp door.env.example door.env   # editar si hace falta
  python agent.py
"""
from __future__ import annotations

import json
import logging
import os
import signal
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from gimnasio.puerta_serial_core import ControlPuertaSerial, PuertaConfig

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('agente_puerta')

ENV_FILE = ROOT / 'door.env'
if load_dotenv and ENV_FILE.exists():
    load_dotenv(ENV_FILE)


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


CONFIG = PuertaConfig(
    port=(os.environ.get('DOOR_ARDUINO_PORT') or '').strip(),
    baud=_env_int('DOOR_ARDUINO_BAUD', 9600),
    pulse_ms=_env_int('DOOR_ARDUINO_PULSE_MS', 3000),
    open_delay=_env_float('DOOR_ARDUINO_OPEN_DELAY', 2.0),
)
AGENT_HOST = os.environ.get('DOOR_AGENT_HOST', '127.0.0.1').strip()
AGENT_PORT = _env_int('DOOR_AGENT_PORT', 8765)
AGENT_SECRET = (os.environ.get('DOOR_AGENT_SECRET') or '').strip()

CONTROL = ControlPuertaSerial(CONFIG)


class Handler(BaseHTTPRequestHandler):
    server_version = 'GYM-PRO-DoorAgent/1.1'

    def log_message(self, fmt, *args):
        logger.info('%s - %s', self.address_string(), fmt % args)

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')

    def _json(self, code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Door-Token')
        self.end_headers()

    def _token_ok(self) -> bool:
        if not AGENT_SECRET:
            return True
        return self.headers.get('X-Door-Token', '').strip() == AGENT_SECRET

    def do_GET(self):
        if self.path.rstrip('/') == '/health':
            self._json(200, {'ok': True, 'estado': CONTROL.estado()})
            return
        self._json(404, {'ok': False, 'error': 'No encontrado'})

    def do_POST(self):
        if self.path.rstrip('/') != '/unlock':
            self._json(404, {'ok': False, 'error': 'No encontrado'})
            return
        if not self._token_ok():
            self._json(403, {'ok': False, 'error': 'Token inválido'})
            return
        ok, mensaje = CONTROL.abrir()
        self._json(200 if ok else 503, {'ok': ok, 'mensaje': mensaje})


def main():
    if AGENT_HOST not in ('127.0.0.1', 'localhost', '::1'):
        print('Solo se permite escuchar en localhost.', file=sys.stderr)
        sys.exit(1)

    httpd = ThreadingHTTPServer((AGENT_HOST, AGENT_PORT), Handler)

    def stop(*_args):
        logger.info('Deteniendo agente…')
        CONTROL.cerrar()
        httpd.shutdown()

    signal.signal(signal.SIGINT, stop)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, stop)

    estado = CONTROL.estado()
    print(f'Agente en http://{AGENT_HOST}:{AGENT_PORT}')
    print(f'Arduino: {estado.get("puerto_detectado") or "no detectado"} — {estado.get("mensaje")}')
    print('GET /health   POST /unlock')
    try:
        httpd.serve_forever()
    finally:
        CONTROL.cerrar()


if __name__ == '__main__':
    main()
