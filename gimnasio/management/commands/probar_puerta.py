from django.core.management.base import BaseCommand

from gimnasio.puerta_arduino import abrir_puerta, estado_puerta


class Command(BaseCommand):
    help = 'Prueba conexión con Arduino y abre la puerta una vez.'

    def handle(self, *args, **options):
        estado = estado_puerta()
        self.stdout.write(f'Estado: {estado}')
        if not estado.get('habilitada'):
            self.stderr.write(self.style.WARNING('Activá DOOR_ARDUINO_ENABLED=1 en .env'))
            return
        ok, mensaje = abrir_puerta(forzar=True)
        if ok:
            self.stdout.write(self.style.SUCCESS(mensaje))
        else:
            self.stderr.write(self.style.ERROR(mensaje))
