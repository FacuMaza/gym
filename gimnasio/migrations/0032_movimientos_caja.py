# Generated manually — vincular movimientos a sesión de caja

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gimnasio', '0031_pagoprofesor_liquidacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='caja',
            name='balance',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='caja',
            name='total_egresos',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='caja',
            name='total_ingresos',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='cuota',
            name='caja',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cuotas', to='gimnasio.caja'),
        ),
        migrations.AddField(
            model_name='egreso',
            name='caja',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='egresos', to='gimnasio.caja'),
        ),
        migrations.AddField(
            model_name='gasto',
            name='caja',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='gastos', to='gimnasio.caja'),
        ),
        migrations.AddField(
            model_name='ingresos',
            name='caja',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ingresos', to='gimnasio.caja'),
        ),
        migrations.AddField(
            model_name='pagoprofesor',
            name='caja',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pagos_profesor', to='gimnasio.caja'),
        ),
        migrations.AddField(
            model_name='venta',
            name='caja',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ventas', to='gimnasio.caja'),
        ),
    ]
