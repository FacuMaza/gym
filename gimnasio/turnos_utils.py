from datetime import date, timedelta

from django.db import transaction
from django.db.models import Count

from .models import HorarioTurno, ReservaTurno
from .socio_portal_utils import socio_bloqueo_rutinas

DIAS_NOMBRE = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']


def categoria_usa_turnos(socio):
    cat = socio.tipo_mensualidad.categoria if socio.tipo_mensualidad else None
    return bool(cat and cat.usa_turnos)


def socio_puede_reservar_turnos(socio):
    bloqueado, _ = socio_bloqueo_rutinas(socio)
    return not bloqueado and categoria_usa_turnos(socio)


def cupos_ocupados(horario, fecha):
    return ReservaTurno.objects.filter(horario_turno=horario, fecha=fecha).count()


def cupos_disponibles(horario, fecha):
    if not horario.activo:
        return 0
    return max(0, horario.cupo_maximo - cupos_ocupados(horario, fecha))


def _fechas_para_horario(horario, desde, cantidad_dias=14):
    fechas = []
    for i in range(cantidad_dias):
        d = desde + timedelta(days=i)
        if d.weekday() == horario.dia_semana:
            fechas.append(d)
    return fechas


def slots_disponibles_socio(socio, cantidad_dias=14):
    cat = socio.tipo_mensualidad.categoria if socio.tipo_mensualidad else None
    if not cat or not cat.usa_turnos:
        return []

    hoy = date.today()
    horarios = (
        HorarioTurno.objects.filter(gimnasio=socio.gimnasio, categorias=cat, activo=True)
        .prefetch_related('categorias')
        .order_by('dia_semana', 'hora')
        .distinct()
    )

    reservas_socio = set(
        ReservaTurno.objects.filter(
            socio=socio,
            fecha__gte=hoy,
            fecha__lte=hoy + timedelta(days=cantidad_dias),
        ).values_list('horario_turno_id', 'fecha')
    )

    ocupacion = {
        (row['horario_turno_id'], row['fecha']): row['n']
        for row in ReservaTurno.objects.filter(
            horario_turno__in=horarios,
            fecha__gte=hoy,
            fecha__lte=hoy + timedelta(days=cantidad_dias),
        ).values('horario_turno_id', 'fecha').annotate(n=Count('id'))
    }

    slots = []
    for horario in horarios:
        for fecha in _fechas_para_horario(horario, hoy, cantidad_dias):
            ocupados = ocupacion.get((horario.pk, fecha), 0)
            disponibles = max(0, horario.cupo_maximo - ocupados)
            ya_reservado = (horario.pk, fecha) in reservas_socio
            slots.append({
                'horario_id': horario.pk,
                'fecha': fecha,
                'fecha_str': fecha.strftime('%d/%m/%Y'),
                'dia_nombre': DIAS_NOMBRE[fecha.weekday()],
                'hora': horario.hora.strftime('%H:%M'),
                'hora_fin': horario.hora_fin.strftime('%H:%M'),
                'categorias': horario.etiqueta_categorias(),
                'cupo_maximo': horario.cupo_maximo,
                'cupos_disponibles': disponibles,
                'completo': disponibles <= 0 and not ya_reservado,
                'ya_reservado': ya_reservado,
            })
    slots.sort(key=lambda s: (s['fecha'], s['hora']))
    return slots


def reservas_futuras_socio(socio):
    hoy = date.today()
    return (
        ReservaTurno.objects.filter(socio=socio, fecha__gte=hoy)
        .select_related('horario_turno')
        .prefetch_related('horario_turno__categorias')
        .order_by('fecha', 'horario_turno__hora')
    )


def reservar_turno(socio, horario_id, fecha):
    if not socio_puede_reservar_turnos(socio):
        return False, 'No podés reservar turnos. Regularizá tu cuota en recepción.'

    cat = socio.tipo_mensualidad.categoria
    try:
        horario = HorarioTurno.objects.get(
            pk=horario_id,
            gimnasio=socio.gimnasio,
            categorias=cat,
            activo=True,
        )
    except HorarioTurno.DoesNotExist:
        return False, 'Turno no válido.'

    if fecha < date.today():
        return False, 'No podés reservar fechas pasadas.'
    if fecha.weekday() != horario.dia_semana:
        return False, 'La fecha no coincide con el día del turno.'

    with transaction.atomic():
        if ReservaTurno.objects.filter(socio=socio, horario_turno=horario, fecha=fecha).exists():
            return False, 'Ya tenés reservado este turno.'
        ocupados = ReservaTurno.objects.filter(horario_turno=horario, fecha=fecha).count()
        if ocupados >= horario.cupo_maximo:
            return False, 'Horario completo.'
        ReservaTurno.objects.create(socio=socio, horario_turno=horario, fecha=fecha)
    return True, 'Turno reservado.'


def cancelar_reserva(socio, reserva_id):
    try:
        reserva = ReservaTurno.objects.get(pk=reserva_id, socio=socio)
    except ReservaTurno.DoesNotExist:
        return False, 'Reserva no encontrada.'
    if reserva.fecha < date.today():
        return False, 'No podés cancelar turnos pasados.'
    reserva.delete()
    return True, 'Reserva cancelada.'


def info_turno_kiosk(socio, hoy=None):
    hoy = hoy or date.today()
    if not categoria_usa_turnos(socio):
        return {'usa_turnos': False}

    reservas = (
        ReservaTurno.objects.filter(socio=socio, fecha=hoy)
        .select_related('horario_turno')
        .prefetch_related('horario_turno__categorias')
        .order_by('horario_turno__hora')
    )
    turnos_hoy = [
        {
            'hora': r.horario_turno.hora.strftime('%H:%M'),
            'hora_fin': r.horario_turno.hora_fin.strftime('%H:%M'),
            'categoria': r.horario_turno.etiqueta_categorias(),
        }
        for r in reservas
    ]
    return {
        'usa_turnos': True,
        'turnos_hoy': turnos_hoy,
        'tiene_turno_hoy': bool(turnos_hoy),
    }
