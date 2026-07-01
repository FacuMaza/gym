import re
from datetime import date

from django.contrib.auth.models import User

from .models import Cuota, Socio


def _username_auth_socio(socio):
    dni_limpio = re.sub(r'\W', '', socio.dni or '') or str(socio.pk)
    return f'gym{socio.gimnasio_id}_{dni_limpio}'[:150]


def crear_o_actualizar_cuenta_socio(socio):
    """Crea o actualiza la cuenta web del socio (usuario y contraseña = DNI)."""
    if not socio.pk or not socio.dni:
        return None
    username = _username_auth_socio(socio)
    password = (socio.dni or '').strip()
    if socio.auth_user_id:
        user = socio.auth_user
        if user.username != username:
            user.username = username
        user.set_password(password)
        user.is_staff = False
        user.is_superuser = False
        user.save()
        return user
    user, created = User.objects.get_or_create(
        username=username,
        defaults={'is_staff': False, 'is_superuser': False},
    )
    user.set_password(password)
    user.save()
    Socio.objects.filter(pk=socio.pk).update(auth_user=user)
    socio.auth_user = user
    return user


def socio_bloqueo_rutinas(socio):
    """
    Devuelve (bloqueado, fecha_vencimiento).
    Sin categoría, sin cuota, vencido por fecha o sin clases → no puede ver rutinas.
    """
    sin_categoria = not socio.tipo_mensualidad or not socio.tipo_mensualidad.categoria_id
    sin_cuota = not Cuota.objects.filter(socio=socio).exists()
    hoy = date.today()
    vencido_fecha = bool(socio.fecha_vencimiento and socio.fecha_vencimiento < hoy)
    vencido_clases = (
        socio.tipo_mensualidad
        and socio.tipo_mensualidad.frecuencia == 'clases'
        and socio.clases_restantes <= 0
    )
    bloqueado = sin_categoria or sin_cuota or vencido_fecha or vencido_clases
    return bloqueado, socio.fecha_vencimiento


def socios_de_rutina(rutina):
    return Socio.objects.filter(
        gimnasio=rutina.gimnasio,
        tipo_mensualidad__categoria=rutina.categoria,
    ).select_related('tipo_mensualidad', 'auth_user')


def entregas_rutina_vigentes(socio):
    """Única entrega vigente por categoría (evita acumular rutinas viejas)."""
    from .models import RutinaEntregada

    entregas = (
        RutinaEntregada.objects.filter(socio=socio)
        .select_related('rutina', 'rutina__categoria')
        .prefetch_related('rutina__ejercicios__ejercicio_catalogo')
        .order_by('-fecha_publicacion', '-id')
    )
    vigentes = {}
    for entrega in entregas:
        cat_id = entrega.rutina.categoria_id
        if cat_id not in vigentes:
            vigentes[cat_id] = entrega
    return sorted(vigentes.values(), key=lambda e: e.fecha_publicacion, reverse=True)


def publicar_rutina(rutina, programacion=None, fecha=None):
    """Publica la rutina en cada socio de la categoría, reemplazando la entrega anterior."""
    from .models import RutinaEntregada

    fecha = fecha or date.today()
    publicados = 0
    for socio in socios_de_rutina(rutina):
        RutinaEntregada.objects.filter(
            socio=socio,
            rutina__categoria=rutina.categoria,
        ).delete()
        RutinaEntregada.objects.create(
            socio=socio,
            rutina=rutina,
            fecha_publicacion=fecha,
            programacion=programacion,
        )
        publicados += 1
    return publicados


def debe_publicar_hoy(programacion, hoy=None):
    hoy = hoy or date.today()
    if not programacion.activa:
        return False
    if programacion.ultimo_envio == hoy:
        return False
    freq = programacion.frecuencia
    if freq == 'diaria':
        return True
    if freq == 'semanal':
        dias = {d.strip() for d in (programacion.dias_semana or '').split(',') if d.strip() != ''}
        return str(hoy.weekday()) in dias
    if freq == 'mensual' and programacion.dia_mes:
        return hoy.day == programacion.dia_mes
    return False


def publicar_programaciones_pendientes(hoy=None):
    from .models import ProgramacionEnvio

    hoy = hoy or date.today()
    total = 0
    for prog in ProgramacionEnvio.objects.filter(activa=True).select_related('rutina'):
        if debe_publicar_hoy(prog, hoy):
            total += publicar_rutina(prog.rutina, programacion=prog, fecha=hoy)
            prog.ultimo_envio = hoy
            prog.save(update_fields=['ultimo_envio'])
    return total
