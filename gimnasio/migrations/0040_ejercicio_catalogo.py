# Generated manually for ejercicio catalogo

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gimnasio', '0039_estado_acceso_vencimiento_pago'),
    ]

    operations = [
        migrations.CreateModel(
            name='EjercicioCatalogo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('clave', models.CharField(help_text='Ej: biceps/barbell-curl', max_length=120, unique=True)),
                ('slug', models.SlugField(max_length=120, unique=True)),
                ('nombre', models.CharField(max_length=200)),
                ('nombre_en', models.CharField(blank=True, max_length=200)),
                ('musculo', models.CharField(blank=True, max_length=80)),
                ('parte_cuerpo', models.CharField(blank=True, max_length=80)),
                ('equipo', models.CharField(blank=True, max_length=80)),
                ('categoria', models.CharField(blank=True, max_length=80)),
                ('instrucciones', models.JSONField(blank=True, default=list)),
                ('gif_url', models.URLField(max_length=500)),
                ('activo', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Ejercicio (catálogo)',
                'verbose_name_plural': 'Ejercicios (catálogo)',
                'db_table': 'EjerciciosCatalogo',
                'ordering': ['nombre'],
            },
        ),
        migrations.AddField(
            model_name='ejerciciorutina',
            name='ejercicio_catalogo',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='usos_en_rutinas',
                to='gimnasio.ejerciciocatalogo',
            ),
        ),
    ]
