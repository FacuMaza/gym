#!/usr/bin/env python3
"""
Agente de puerta — PC de la pantalla de ingreso (USB + Arduino).
Lee door.local.json (descargado desde el panel web). Sin .env.
"""
from __future__ import annotations

import json
import logging
import signal
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
sys.path.insert(0, str(REPO_ROOT))

from gimnasio.puerta_serial_core import ControlPuertaSerial, PuertaConfig, detectar_puerto_arduino

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('agente_puerta')

LOCAL_FILE = ROOT / 'door.local.json'
AGENT_HOST = '127.0.0.1'
AGENT_PORT = 8765

_vinculo: dict = {}
_runtime: dict = {
    'token_unlock': '',
    'config_remota': {},
}
_control: ControlPuertaSerial | None = None
_control_lock = threading.Lock()


def _cargar_vinculo() -> dict:
    if not LOCAL_FILE.exists():
        print(
            f'Falta {LOCAL_FILE.name}. Descargalo desde el panel: Configuración → Puerta.',
            file=sys.stderr,
        )
        sys.exit(1)
    with LOCAL_FILE.open(encoding='utf-8') as f:
        data = json.load(f)
    for key in ('servidor', 'gimnasio_id', 'token'):
        if not data.get(key):
            print(f'{LOCAL_FILE.name} incompleto (servidor, gimnasio_id, token).', file=sys.stderr)
            sys.exit(1)
    return data


def _fetch_remoto():
    servidor = _vinculo['servidor'].rstrip('/')
    url = (
        f"{servidor}/api/puerta/agente-config/"
        f"?gimnasio_id={_vinculo['gimnasio_id']}"
    )
    req = urllib.request.Request(url, headers={'X-Gym-Door-Token': _vinculo['token']})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode('utf-8'))


def _aplicar_config_remota(payload: dict):
    global _control
    cfg = payload.get('config') or {}
    if not cfg.get('activa'):
        logger.warning('Puerta desactivada en el panel web.')
    puerta = PuertaConfig(
        port=(cfg.get('puerto_arduino') or '').strip(),
        baud=9600,
        pulse_ms=int(cfg.get('pulso_ms') or 3000),
        open_delay=float(cfg.get('espera_serial') or 2.0),
    )
    _runtime['token_unlock'] = cfg.get('token_agente') or _vinculo['token']
    _runtime['config_remota'] = cfg
    with _control_lock:
        if _control:
            _control.cerrar()
        _control = ControlPuertaSerial(puerta)


def _sync_loop():
    while True:
        try:
            data = _fetch_remoto()
            if data.get('ok'):
                _aplicar_config_remota(data)
                logger.info('Config actualizada desde el servidor (%s)', data.get('gimnasio', ''))
        except Exception as exc:
            logger.warning('No se pudo sincronizar config: %s', exc)
        time.sleep(60)


def _control_activo() -> ControlPuertaSerial:
    global _control
    with _control_lock:
        if _control is None:
            _aplicar_config_remota({'config': {
                'activa': True,
                'puerto_arduino': '',
                'pulso_ms': 3000,
                'espera_serial': 2.0,
                'token_agente': _vinculo['token'],
            }})
        return _control


class Handler(BaseHTTPRequestHandler):
    server_version = 'GYM-PRO-DoorAgent/1.2'

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
        token = _runtime.get('token_unlock') or ''
        if not token:
            return True
        return self.headers.get('X-Door-Token', '').strip() == token

    def do_GET(self):
        path = self.path.rstrip('/')
        if path == '/health':
            ctrl = _control_activo()
            estado = ctrl.estado()
            estado['puertos_usb'] = []
            try:
                puerto = detectar_puerto_arduino()
                if puerto:
                    estado['puertos_usb'] = [puerto]
            except Exception:
                pass
            self._json(200, {'ok': True, 'estado': estado, 'activa_remota': _runtime['config_remota'].get('activa')})
            return
        self._json(404, {'ok': False, 'error': 'No encontrado'})

    def do_POST(self):
        if self.path.rstrip('/') != '/unlock':
            self._json(404, {'ok': False, 'error': 'No encontrado'})
            return
        if not _runtime['config_remota'].get('activa', True):
            self._json(403, {'ok': False, 'error': 'Puerta desactivada en el panel'})
            return
        if not self._token_ok():
            self._json(403, {'ok': False, 'error': 'Token inválido'})
            return
        ok, mensaje = _control_activo().abrir()
        self._json(200 if ok else 503, {'ok': ok, 'mensaje': mensaje})


def main():
    global _vinculo
    _vinculo = _cargar_vinculo()
    try:
        data = _fetch_remoto()
        if not data.get('ok'):
            raise RuntimeError(data.get('error', 'respuesta inválida'))
        _aplicar_config_remota(data)
    except Exception as exc:
        print(f'Advertencia: no se pudo leer config del servidor ({exc}). Usando valores locales.', file=sys.stderr)

    threading.Thread(target=_sync_loop, daemon=True).start()

    httpd = ThreadingHTTPServer((AGENT_HOST, AGENT_PORT), Handler)

    def stop(*_args):
        logger.info('Deteniendo agente…')
        with _control_lock:
            if _control:
                _control.cerrar()
        httpd.shutdown()

    signal.signal(signal.SIGINT, stop)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, stop)

    estado = _control_activo().estado()
    print(f'Agente en http://{AGENT_HOST}:{AGENT_PORT}')
    print(f'Vinculado a gym #{_vinculo["gimnasio_id"]} — {_vinculo["servidor"]}')
    print(f'Arduino: {estado.get("puerto_detectado") or "no detectado"} — {estado.get("mensaje")}')
    try:
        httpd.serve_forever()
    finally:
        stop()


if __name__ == '__main__':
    main()
