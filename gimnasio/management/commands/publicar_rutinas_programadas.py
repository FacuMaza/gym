from django.core.management.base import BaseCommand

from gimnasio.models import Socio
from gimnasio.socio_portal_utils import crear_o_actualizar_cuenta_socio, publicar_programaciones_pendientes


class Command(BaseCommand):
    help = 'Crea cuentas web de socios y publica rutinas programadas para hoy.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--solo-cuentas',
            action='store_true',
            help='Solo crear/actualizar cuentas de socios, sin publicar rutinas.',
        )
        parser.add_argument(
            '--solo-rutinas',
            action='store_true',
            help='Solo publicar rutinas programadas, sin tocar cuentas.',
        )

    def handle(self, *args, **options):
        solo_cuentas = options['solo_cuentas']
        solo_rutinas = options['solo_rutinas']
        if not solo_rutinas:
            n_cuentas = 0
            for socio in Socio.objects.all().iterator():
                crear_o_actualizar_cuenta_socio(socio)
                n_cuentas += 1
            self.stdout.write(self.style.SUCCESS(f'Cuentas de socios procesadas: {n_cuentas}'))
        if not solo_cuentas:
            entregas = publicar_programaciones_pendientes()
            self.stdout.write(self.style.SUCCESS(f'Nuevas entregas de rutina hoy: {entregas}'))
