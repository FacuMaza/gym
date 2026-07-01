from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from .public_urls import build_socio_login_url, qr_usa_ip_local
from .models import Socio
from .socio_portal_utils import entregas_rutina_vigentes, socio_bloqueo_rutinas
from .turnos_utils import (
    cancelar_reserva,
    categoria_usa_turnos,
    reservar_turno,
    reservas_futuras_socio,
    slots_disponibles_socio,
    socio_puede_reservar_turnos,
)


def _socio_desde_request(request):
    if not request.user.is_authenticated:
        return None
    return Socio.objects.filter(auth_user=request.user).select_related(
        'gimnasio', 'tipo_mensualidad', 'tipo_mensualidad__categoria'
    ).first()


def socio_login_required(view_func):
    def wrapper(request, *args, **kwargs):
        socio = _socio_desde_request(request)
        if not socio:
            return redirect('login')
        request.socio = socio
        return view_func(request, *args, **kwargs)
    return wrapper


def socio_login(request):
    """Redirige al login único del gym (compatibilidad con QR/links viejos)."""
    gym_id = request.GET.get('gym') or request.POST.get('gym')
    if gym_id:
        return redirect(f'{reverse("login")}?gym={gym_id}')
    return redirect('login')


def _descartar_mensajes_sesion(request):
    """Quita mensajes flash del admin u otras vistas (no van al portal del socio)."""
    from django.contrib import messages
    list(messages.get_messages(request))


@socio_login_required
def socio_portal(request):
    _descartar_mensajes_sesion(request)
    socio = request.socio
    bloqueado, fecha_venc = socio_bloqueo_rutinas(socio)
    rutinas = []
    if not bloqueado:
        rutinas = entregas_rutina_vigentes(socio)

    usa_turnos = categoria_usa_turnos(socio)
    puede_turnos = socio_puede_reservar_turnos(socio)
    slots_turnos = slots_disponibles_socio(socio) if usa_turnos else []
    mis_reservas = reservas_futuras_socio(socio) if usa_turnos else []

    return render(request, 'socio/portal.html', {
        'socio': socio,
        'bloqueado_rutinas': bloqueado,
        'fecha_vencimiento': fecha_venc,
        'rutinas': rutinas,
        'usa_turnos': usa_turnos,
        'puede_reservar_turnos': puede_turnos,
        'slots_turnos': slots_turnos,
        'mis_reservas': mis_reservas,
        'reserva_ok': request.GET.get('reservado') == '1',
    })


@socio_login_required
def socio_reservar_turno(request):
    if request.method != 'POST':
        return redirect('socio_portal')
    from datetime import datetime
    horario_id = request.POST.get('horario_id')
    fecha_str = request.POST.get('fecha')
    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return redirect('socio_portal')
    ok, _msg = reservar_turno(request.socio, horario_id, fecha)
    if ok:
        return redirect(reverse('socio_portal') + '?reservado=1')
    return redirect('socio_portal')


@socio_login_required
def socio_cancelar_turno(request, pk):
    if request.method != 'POST':
        return redirect('socio_portal')
    ok, _msg = cancelar_reserva(request.socio, pk)
    return redirect('socio_portal')


def socio_logout(request):
    logout(request)
    return redirect('login')


@login_required
def socio_qr_info(request):
    from .views import get_gimnasio_actual

    gym = get_gimnasio_actual(request)
    if not gym:
        return redirect('gimnasio_lista')
    login_url = build_socio_login_url(request, gym.pk)
    return render(request, 'rutinas/qr_socio.html', {
        'gimnasio_actual': gym,
        'login_url': login_url,
        'qr_usa_ip_local': qr_usa_ip_local(request),
    })


@login_required
def socio_qr_imprimir(request):
    from .views import get_gimnasio_actual

    gym = get_gimnasio_actual(request)
    if not gym:
        return redirect('gimnasio_lista')
    login_url = build_socio_login_url(request, gym.pk)
    gym_nombre = gym.nombre or gym.direccion or 'Gimnasio'
    return render(request, 'rutinas/qr_socio_imprimir.html', {
        'gimnasio_actual': gym,
        'gimnasio_nombre': gym_nombre,
        'login_url': login_url,
    })
