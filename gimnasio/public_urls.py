import os
import socket

from django.conf import settings


def _detectar_ip_red_local():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(('8.8.8.8', 80))
            return sock.getsockname()[0]
    except OSError:
        return None


def get_public_base_url(request):
    """
    URL base para QR y links que se abren desde el celular.
    En local reemplaza 127.0.0.1 por la IP de la PC en la red WiFi.
    En producción usar PUBLIC_BASE_URL en .env (ej. https://tudominio.com).
    """
    configurada = (getattr(settings, 'PUBLIC_BASE_URL', None) or os.environ.get('PUBLIC_BASE_URL', '')).strip()
    if configurada:
        return configurada.rstrip('/')

    host = request.get_host()
    scheme = 'https' if request.is_secure() else 'http'
    hostname = host.split(':')[0].lower()
    port = host.split(':')[1] if ':' in host else ('443' if scheme == 'https' else '80')

    if hostname in ('127.0.0.1', 'localhost', '::1'):
        ip_red = _detectar_ip_red_local()
        if ip_red:
            puerto = port if port not in ('80', '443') else '8000'
            return f'http://{ip_red}:{puerto}'

    return f'{scheme}://{host}'


def build_socio_login_url(request, gym_id):
    base = get_public_base_url(request)
    return f'{base}/login/?gym={gym_id}'


def qr_usa_ip_local(request):
    configurada = (getattr(settings, 'PUBLIC_BASE_URL', None) or os.environ.get('PUBLIC_BASE_URL', '')).strip()
    if configurada:
        return False
    host = request.get_host().split(':')[0].lower()
    return host in ('127.0.0.1', 'localhost', '::1')
