from datetime import datetime
from zoneinfo import ZoneInfo

from django.db import migrations, models


def grandfather_periodo_pagado(apps, schema_editor):
    EstadoAccesoSistema = apps.get_model('gimnasio', 'EstadoAccesoSistema')
    ahora = datetime.now(ZoneInfo('America/Argentina/Buenos_Aires'))
    vence = ahora.replace(day=10, hour=0, minute=0, second=0, microsecond=0)
    if ahora < vence:
        mes, anio = vence.month - 1, vence.year
        if mes < 1:
            mes, anio = 12, anio - 1
        key = f"{anio}-{mes:02d}"
    else:
        key = ''
    obj, _ = EstadoAccesoSistema.objects.get_or_create(pk=1, defaults={'pausado': False})
    obj.periodos_pagados = key
    obj.save(update_fields=['periodos_pagados'])


class Migration(migrations.Migration):

    dependencies = [
        ('gimnasio', '0038_estado_acceso_sistema'),
    ]

    operations = [
        migrations.AddField(
            model_name='estadoaccesosistema',
            name='pausado_por_vencimiento',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='estadoaccesosistema',
            name='periodos_pagados',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.RunPython(grandfather_periodo_pagado, migrations.RunPython.noop),
    ]
