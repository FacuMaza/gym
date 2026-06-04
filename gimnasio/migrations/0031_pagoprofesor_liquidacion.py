from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gimnasio', '0030_socio_celular'),
    ]

    operations = [
        migrations.AddField(
            model_name='pagoprofesor',
            name='adelantos_liquidados',
            field=models.FloatField(default=0, help_text='Adelantos incluidos en esta liquidación'),
        ),
        migrations.AddField(
            model_name='pagoprofesor',
            name='productos_liquidados',
            field=models.FloatField(default=0, help_text='Productos a cuenta incluidos en esta liquidación'),
        ),
    ]
