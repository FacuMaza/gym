from django.db import migrations


def reparar_horarios_sin_categoria(apps, schema_editor):
    HorarioTurno = apps.get_model('gimnasio', 'HorarioTurno')
    CategoriaMensualidad = apps.get_model('gimnasio', 'CategoriaMensualidad')
    ReservaTurno = apps.get_model('gimnasio', 'ReservaTurno')
    Socio = apps.get_model('gimnasio', 'Socio')

    for h in HorarioTurno.objects.all():
        if h.categorias.exists():
            continue
        cat_ids = set()
        for reserva in ReservaTurno.objects.filter(horario_turno_id=h.pk):
            socio = Socio.objects.filter(pk=reserva.socio_id).select_related('tipo_mensualidad').first()
            if socio and socio.tipo_mensualidad_id:
                tm = socio.tipo_mensualidad
                if tm and tm.categoria_id:
                    cat_ids.add(tm.categoria_id)
        if not cat_ids:
            turnos = list(
                CategoriaMensualidad.objects.filter(gimnasio_id=h.gimnasio_id, usa_turnos=True).values_list('pk', flat=True)
            )
            if len(turnos) == 1:
                cat_ids = {turnos[0]}
        if cat_ids:
            h.categorias.set(cat_ids)


class Migration(migrations.Migration):

    dependencies = [
        ('gimnasio', '0036_horario_turno_categorias_m2m'),
    ]

    operations = [
        migrations.RunPython(reparar_horarios_sin_categoria, migrations.RunPython.noop),
    ]
