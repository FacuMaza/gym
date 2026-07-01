from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms_turnos import HorarioTurnoForm, HorarioTurnoRangoForm
from .models import CategoriaMensualidad, HorarioTurno, ReservaTurno
from .views import get_gimnasio_actual


def _session_key_combinacion(gym_id):
    return f'turnos_combinacion_{gym_id}'


def _parse_combinacion_ids(raw_ids, gym):
    if not raw_ids:
        return []
    qs = CategoriaMensualidad.objects.filter(
        gimnasio=gym,
        pk__in=raw_ids,
        usa_turnos=True,
    ).order_by('nombre')
    return list(qs.values_list('pk', flat=True))


def _get_combinacion_ids(request, gym):
    key = _session_key_combinacion(gym.id)
    raw = request.session.get(key, [])
    try:
        ids = [int(x) for x in raw]
    except (TypeError, ValueError):
        ids = []
    return _parse_combinacion_ids(ids, gym)


def _set_combinacion_ids(request, gym, ids):
    valid = _parse_combinacion_ids(ids, gym)
    request.session[_session_key_combinacion(gym.id)] = valid
    return valid


def _combinacion_queryset(request, gym, categoria=None, combinar_param=None):
    """Resuelve categorías activas para horarios (sesión + query + categoría del link)."""
    if combinar_param:
        raw = [x.strip() for x in combinar_param.split(',') if x.strip().isdigit()]
        ids = _parse_combinacion_ids(raw, gym)
        if categoria and categoria.pk not in ids:
            ids = _parse_combinacion_ids(list(set(ids + [categoria.pk])), gym)
        if ids:
            _set_combinacion_ids(request, gym, ids)
            return CategoriaMensualidad.objects.filter(gimnasio=gym, pk__in=ids).order_by('nombre')

    ids = _get_combinacion_ids(request, gym)
    if categoria and categoria.pk not in ids:
        ids = _parse_combinacion_ids(list(set(ids + [categoria.pk])), gym)
        _set_combinacion_ids(request, gym, ids)
    elif not ids and categoria:
        ids = [categoria.pk]
        _set_combinacion_ids(request, gym, ids)

    return CategoriaMensualidad.objects.filter(gimnasio=gym, pk__in=ids).order_by('nombre')


def _etiqueta_combinacion(categorias):
    return ' + '.join(c.nombre for c in categorias)


@login_required
def turnos_index(request):
    gym = get_gimnasio_actual(request)
    if not gym:
        return redirect('gimnasio_lista')

    if request.method == 'POST':
        if request.POST.get('action') == 'guardar_combinacion':
            ids = request.POST.getlist('combinar')
            valid = _set_combinacion_ids(request, gym, ids)
            if valid:
                cats = CategoriaMensualidad.objects.filter(pk__in=valid)
                messages.success(
                    request,
                    f'Combinación guardada: {_etiqueta_combinacion(cats)}.',
                )
            else:
                messages.warning(request, 'Marcá al menos una categoría con turnos activos.')
            return redirect('turnos_index')

        cat_id = request.POST.get('categoria_id')
        usa = request.POST.get('usa_turnos') == 'on'
        cat = get_object_or_404(CategoriaMensualidad, pk=cat_id, gimnasio=gym)
        cat.usa_turnos = usa
        cat.save(update_fields=['usa_turnos'])
        messages.success(request, f'«{cat.nombre}»: turnos {"activados" if usa else "desactivados"}.')
        return redirect('turnos_index')

    categorias = CategoriaMensualidad.objects.filter(gimnasio=gym).annotate(
        num_horarios=Count('horarios_turno', distinct=True),
    ).order_by('nombre')
    combinacion_ids = set(_get_combinacion_ids(request, gym))
    return render(request, 'turnos/index.html', {
        'categorias': categorias,
        'gimnasio_actual': gym,
        'combinacion_ids': combinacion_ids,
    })


@login_required
def turnos_horarios(request, categoria_id):
    gym = get_gimnasio_actual(request)
    cat = get_object_or_404(CategoriaMensualidad, pk=categoria_id, gimnasio=gym)
    if not cat.usa_turnos:
        messages.warning(request, f'Activá turnos en «{cat.nombre}» primero.')
        return redirect('turnos_index')

    combinar_param = request.GET.get('combinar') if request.method == 'GET' else None
    categorias_sel = list(_combinacion_queryset(request, gym, cat, combinar_param))
    if not categorias_sel:
        messages.warning(request, 'No hay categorías válidas en la combinación.')
        return redirect('turnos_index')

    combinacion_etiqueta = _etiqueta_combinacion(categorias_sel)
    sel_ids = [c.pk for c in categorias_sel]

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'eliminar':
            horario = get_object_or_404(
                HorarioTurno,
                pk=request.POST.get('horario_id'),
                gimnasio=gym,
                categorias__in=sel_ids,
            )
            horario.delete()
            messages.success(request, 'Horario eliminado.')
            return redirect('turnos_horarios', categoria_id=cat.pk)
        if action == 'eliminar_todos':
            horarios_qs = (
                HorarioTurno.objects.filter(gimnasio=gym, categorias__in=sel_ids)
                .distinct()
            )
            n = horarios_qs.count()
            horarios_qs.delete()
            messages.success(request, f'Se eliminaron {n} horario(s) de «{combinacion_etiqueta}».')
            return redirect('turnos_horarios', categoria_id=cat.pk)
        form = HorarioTurnoRangoForm(request.POST)
        if form.is_valid():
            cupo = form.cleaned_data['cupo_maximo']
            activo = form.cleaned_data['activo']
            creados = 0
            actualizados = 0
            for dia in form.dias_en_rango():
                for hora in form.horas_en_rango():
                    horario, created = HorarioTurno.objects.update_or_create(
                        gimnasio=gym,
                        dia_semana=dia,
                        hora=hora,
                        defaults={'cupo_maximo': cupo, 'activo': activo},
                    )
                    horario.categorias.set(categorias_sel)
                    if created:
                        creados += 1
                    else:
                        actualizados += 1
            total = creados + actualizados
            msg = f'{total} horario(s) guardado(s)'
            if len(categorias_sel) > 1:
                msg += f' (cupos compartidos: {combinacion_etiqueta})'
            if creados and actualizados:
                msg += f' — {creados} nuevo(s), {actualizados} actualizado(s)'
            elif actualizados:
                msg += f' — {actualizados} actualizado(s)'
            messages.success(request, msg + '.')
            return redirect('turnos_horarios', categoria_id=cat.pk)
    else:
        form = HorarioTurnoRangoForm()

    horarios = (
        HorarioTurno.objects.filter(gimnasio=gym, categorias__in=sel_ids)
        .prefetch_related('categorias')
        .order_by('dia_semana', 'hora')
        .distinct()
    )
    return render(request, 'turnos/horarios.html', {
        'categoria': cat,
        'categorias_combinacion': categorias_sel,
        'combinacion_etiqueta': combinacion_etiqueta,
        'horarios': horarios,
        'form': form,
        'gimnasio_actual': gym,
    })


@login_required
def turnos_horario_editar(request, pk):
    gym = get_gimnasio_actual(request)
    horario = get_object_or_404(HorarioTurno, pk=pk, gimnasio=gym)
    cat_id = request.GET.get('cat') or request.POST.get('cat')
    cat = None
    if cat_id:
        cat = get_object_or_404(CategoriaMensualidad, pk=cat_id, gimnasio=gym)
    if not cat:
        cat = horario.categorias.filter(gimnasio=gym).first()

    if request.method == 'POST':
        form = HorarioTurnoForm(request.POST, instance=horario, gimnasio=gym)
        if form.is_valid():
            form.save()
            messages.success(request, 'Horario actualizado.')
            return redirect('turnos_horarios', categoria_id=cat.pk if cat else horario.categorias.first().pk)
    else:
        form = HorarioTurnoForm(instance=horario, gimnasio=gym)
    return render(request, 'turnos/horario_editar.html', {
        'form': form,
        'horario': horario,
        'categoria': cat,
    })


@login_required
def turnos_reservas(request, categoria_id):
    gym = get_gimnasio_actual(request)
    cat = get_object_or_404(CategoriaMensualidad, pk=categoria_id, gimnasio=gym)
    hoy = timezone.localdate()
    reservas = (
        ReservaTurno.objects.filter(
            horario_turno__gimnasio=gym,
            horario_turno__categorias=cat,
            fecha__gte=hoy,
        )
        .select_related('socio', 'horario_turno')
        .prefetch_related('horario_turno__categorias')
        .order_by('fecha', 'horario_turno__hora')
        .distinct()
    )
    return render(request, 'turnos/reservas.html', {
        'categoria': cat,
        'reservas': reservas,
        'gimnasio_actual': gym,
    })
