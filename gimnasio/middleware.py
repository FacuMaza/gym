from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils import timezone


class SistemaPausadoMiddleware:
    """Si el sistema está pausado, cierra sesión de usuarios que no sean Super Usuario."""

    RUTAS_EXENTAS = frozenset({
        '/login/',
        '/logout/',
        '/sistema-pausado/',
        '/sistema-pausa/toggle/',
        '/sistema-pausa/pagado/',
    })

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self._aplicar_pausa_vencimiento()
        if self._debe_expulsar(request):
            logout(request)
            return redirect('sistema_pausado')
        return self.get_response(request)

    def _debe_expulsar(self, request):
        from .models import EstadoAccesoSistema

        if not EstadoAccesoSistema.get_estado().pausado:
            return False
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return False
        path = request.path
        if not path.endswith('/'):
            path = f'{path}/'
        return path not in self.RUTAS_EXENTAS

    def _aplicar_pausa_vencimiento(self):
        from .models import EstadoAccesoSistema
        from .sistema_vencimiento import debe_pausar_por_vencimiento

        estado = EstadoAccesoSistema.get_estado()
        if not debe_pausar_por_vencimiento(estado.periodos_pagados):
            if estado.pausado and estado.pausado_por_vencimiento:
                estado.pausado = False
                estado.pausado_por_vencimiento = False
                estado.pausado_en = None
                estado.pausado_por = None
                estado.save(update_fields=[
                    'pausado', 'pausado_por_vencimiento', 'pausado_en', 'pausado_por',
                ])
            return
        if estado.pausado:
            return
        estado.pausado = True
        estado.pausado_por_vencimiento = True
        estado.pausado_en = timezone.now()
        estado.pausado_por = None
        estado.save(update_fields=[
            'pausado', 'pausado_por_vencimiento', 'pausado_en', 'pausado_por',
        ])
