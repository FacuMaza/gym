"""
Agente local en la PC del kiosco (USB + Arduino).

Uso en la PC de ingreso (Windows/Linux), con el sitio en VPS o local:
  python manage.py agente_puerta

Escucha solo en 127.0.0.1; la pantalla de ingreso llama POST /unlock cuando el socio está en verde.
"""
from __future__ import annotations

import json
import logging
import signal
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from django.conf import settings
from django.core.management.base import BaseCommand

from gimnasio.puerta_arduino import abrir_puerta, cerrar_conexion, estado_puerta

logger = logging.getLogger(__name__)


class _AgentePuertaHandler(BaseHTTPRequestHandler):
    server_version = 'GYM-PRO-DoorAgent/1.0'

    def log_message(self, fmt, *args):
        logger.info('%s - %s', self.address_string(), fmt % args)

    def _json(self, code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Door-Token')
        self.end_headers()

    def _token_valido(self) -> bool:
        secreto = (getattr(settings, 'DOOR_AGENT_SECRET', '') or '').strip()
        if not secreto:
            return True
        return self.headers.get('X-Door-Token', '').strip() == secreto

    def do_GET(self):
        if self.path.rstrip('/') == '/health':
            self._json(200, {'ok': True, 'estado': estado_puerta()})
            return
        self._json(404, {'ok': False, 'error': 'No encontrado'})

    def do_POST(self):
        if self.path.rstrip('/') != '/unlock':
            self._json(404, {'ok': False, 'error': 'No encontrado'})
            return
        if not self._token_valido():
            self._json(403, {'ok': False, 'error': 'Token inválido'})
            return
        ok, mensaje = abrir_puerta(forzar=True)
        self._json(200 if ok else 503, {'ok': ok, 'mensaje': mensaje})


class Command(BaseCommand):
    help = 'Agente HTTP local para abrir la puerta vía Arduino (PC del kiosco con USB).'

    def add_arguments(self, parser):
        parser.add_argument('--host', default='127.0.0.1', help='Solo localhost por seguridad (default: 127.0.0.1)')
        parser.add_argument('--port', type=int, default=None, help='Puerto HTTP (default: DOOR_AGENT_PORT o 8765)')

    def handle(self, *args, **options):
        if not getattr(settings, 'DOOR_ARDUINO_ENABLED', False):
            self.stderr.write(self.style.WARNING(
                'DOOR_ARDUINO_ENABLED=0 en .env. Activá la puerta y reiniciá el agente.'
            ))

        host = options['host']
        if host not in ('127.0.0.1', 'localhost', '::1'):
            self.stderr.write(self.style.ERROR('Por seguridad el agente solo puede escuchar en localhost.'))
            sys.exit(1)

        port = options['port'] or int(getattr(settings, 'DOOR_AGENT_PORT', 8765))
        httpd = ThreadingHTTPServer((host, port), _AgentePuertaHandler)

        def _shutdown(signum, frame):
            self.stdout.write('\nDeteniendo agente…')
            cerrar_conexion()
            httpd.shutdown()

        signal.signal(signal.SIGINT, _shutdown)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, _shutdown)

        estado = estado_puerta()
        self.stdout.write(self.style.SUCCESS(
            f'Agente de puerta en http://{host}:{port}  '
            f'(Arduino: {estado.get("puerto_detectado") or "no detectado"})'
        ))
        self.stdout.write('Endpoints: GET /health  POST /unlock')
        self.stdout.write('Ctrl+C para salir.')

        try:
            httpd.serve_forever()
        finally:
            cerrar_conexion()
