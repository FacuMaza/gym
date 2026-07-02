# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gimnasio', '0040_ejercicio_catalogo'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfiguracionPuerta',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('activa', models.BooleanField(default=False, help_text='Habilita apertura automática al ingreso en verde.')),
                ('url_agente', models.CharField(default='http://127.0.0.1:8765', help_text='URL del agente en la PC de la pantalla de ingreso (misma máquina que el Arduino USB).', max_length=200)),
                ('token_agente', models.CharField(blank=True, editable=False, max_length=64)),
                ('puerto_arduino', models.CharField(blank=True, help_text='Ej: COM5 o /dev/ttyUSB0. Vacío = detección automática del Nano CH340.', max_length=80)),
                ('pulso_ms', models.PositiveIntegerField(default=3000, help_text='Milisegundos que el relé permanece activo al abrir.')),
                ('espera_serial', models.FloatField(default=2.0, help_text='Segundos de espera al conectar el puerto USB (reinicio del Arduino).')),
                ('gimnasio', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='config_puerta', to='gimnasio.gimnasio')),
            ],
            options={
                'verbose_name': 'Configuración de puerta',
                'verbose_name_plural': 'Configuraciones de puerta',
                'db_table': 'ConfiguracionPuerta',
            },
        ),
    ]
