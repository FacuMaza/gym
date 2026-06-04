# Quita categorías de ejemplo (TAEBO, SALSA, PESAS) si no tienen opciones cargadas.

from django.db import migrations

PLANTILLA = ('TAEBO', 'SALSA', 'PESAS')


def quitar_plantillas(apps, schema_editor):
    CategoriaMensualidad = apps.get_model('gimnasio', 'CategoriaMensualidad')
    TipoMensualidad = apps.get_model('gimnasio', 'TipoMensualidad')
    for cat in CategoriaMensualidad.objects.filter(nombre__in=PLANTILLA):
        if not TipoMensualidad.objects.filter(categoria_id=cat.pk).exists():
            cat.delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('gimnasio', '0032_movimientos_caja'),
    ]

    operations = [
        migrations.RunPython(quitar_plantillas, noop_reverse),
    ]
