from .models import Caja, Gimnasio, UsuarioGimnasio, Usuario


def sistema_pausado(request):
    try:
        from .models import EstadoAccesoSistema
        return {'sistema_pausado': EstadoAccesoSistema.get_estado().pausado}
    except Exception:
        return {'sistema_pausado': False}


def vencimiento_sistema(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {}
    from .sistema_vencimiento import (
        info_vencimiento_sistema, debe_mostrar_aviso_vencimiento, periodo_actual_pagado,
    )
    from .models import EstadoAccesoSistema
    if not debe_mostrar_aviso_vencimiento():
        return {}
    if periodo_actual_pagado(EstadoAccesoSistema.get_estado().periodos_pagados):
        return {}
    return {'vencimiento_sistema': info_vencimiento_sistema()}


def pago_sistema_su(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {}
    if not request.user.is_superuser:
        return {}
    from .sistema_vencimiento import debe_mostrar_aviso_vencimiento, periodo_actual_pagado
    from .models import EstadoAccesoSistema
    estado = EstadoAccesoSistema.get_estado()
    en_ventana = debe_mostrar_aviso_vencimiento()
    pausado_impago = estado.pausado and estado.pausado_por_vencimiento
    if not en_ventana and not pausado_impago:
        return {}
    return {'pago_sistema_su': {'pagado': periodo_actual_pagado(estado.periodos_pagados)}}


def gimnasio_context(request):
    """Añade gimnasio_actual y gimnasios_disponibles al contexto."""
    context = {}
    if not request.user.is_authenticated:
        return context

    gimnasios = []
    if request.user.is_superuser:
        gimnasios = list(Gimnasio.objects.all().order_by('nombre', 'direccion'))
    else:
        try:
            usuario = Usuario.objects.get(usuario=request.user.username)
            gimnasios = list(
                Gimnasio.objects.filter(usuarios_asignados__usuario=usuario).distinct().order_by('nombre', 'direccion')
            )
        except Usuario.DoesNotExist:
            gimnasios = list(Gimnasio.objects.all().order_by('nombre', 'direccion'))

    context['gimnasios_disponibles'] = gimnasios

    gimnasio_id = request.session.get('gimnasio_actual_id')
    if gimnasio_id and gimnasios:
        gim = next((g for g in gimnasios if g.id == int(gimnasio_id)), None)
        if gim:
            context['gimnasio_actual'] = gim
        else:
            context['gimnasio_actual'] = gimnasios[0]
            request.session['gimnasio_actual_id'] = gimnasios[0].id
    elif gimnasios:
        context['gimnasio_actual'] = gimnasios[0]
        request.session['gimnasio_actual_id'] = gimnasios[0].id
    else:
        context['gimnasio_actual'] = None

    gym = context.get('gimnasio_actual')
    if gym:
        caja = Caja.objects.filter(gimnasio=gym, fecha_cierre__isnull=True).select_related('usuario_apertura').first()
        context['caja_abierta'] = caja
        from .views import usuario_puede_operar_caja
        context['puede_operar_caja'] = usuario_puede_operar_caja(request, caja)
    else:
        context['caja_abierta'] = None
        from .views import usuario_puede_operar_caja
        context['puede_operar_caja'] = usuario_puede_operar_caja(request, None)

    return context
