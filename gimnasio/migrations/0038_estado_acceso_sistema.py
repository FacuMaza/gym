import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('gimnasio', '0037_reparar_categorias_horarios'),
    ]

    operations = [
        migrations.CreateModel(
            name='EstadoAccesoSistema',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pausado', models.BooleanField(default=False)),
                ('pausado_en', models.DateTimeField(blank=True, null=True)),
                ('pausado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Estado de acceso al sistema',
                'verbose_name_plural': 'Estado de acceso al sistema',
            },
        ),
    ]
