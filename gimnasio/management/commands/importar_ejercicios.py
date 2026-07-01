from django.core.management.base import BaseCommand
from django.db import transaction

from gimnasio.ejercicios_catalogo_import import iter_catalogo_desde_api
from gimnasio.models import EjercicioCatalogo


class Command(BaseCommand):
    help = 'Importa el catálogo de ejercicios con GIF (ExerciseGymGifsDB, ~1300 ejercicios en español).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--idioma',
            default='es',
            help='Idioma del dataset (default: es).',
        )

    def handle(self, *args, **options):
        lang = options['idioma']
        creados = 0
        actualizados = 0
        errores = 0

        self.stdout.write(f'Importando ejercicios ({lang})…')

        try:
            ejercicios = list(iter_catalogo_desde_api(lang))
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f'No se pudo leer el catálogo remoto: {exc}'))
            return

        if not ejercicios:
            self.stderr.write(self.style.ERROR('No se encontraron ejercicios. Verificá conexión a internet.'))
            return

        with transaction.atomic():
            for data in ejercicios:
                try:
                    obj, created = EjercicioCatalogo.objects.update_or_create(
                        clave=data['clave'],
                        defaults={
                            'slug': data['slug'][:120],
                            'nombre': data['nombre'][:200],
                            'nombre_en': data['nombre_en'][:200],
                            'musculo': data['musculo'][:80],
                            'parte_cuerpo': data['parte_cuerpo'][:80],
                            'equipo': data['equipo'][:80],
                            'categoria': data['categoria'][:80],
                            'instrucciones': data['instrucciones'],
                            'gif_url': data['gif_url'][:500],
                            'activo': True,
                        },
                    )
                    if created:
                        creados += 1
                    else:
                        actualizados += 1
                except Exception:
                    errores += 1

        total = EjercicioCatalogo.objects.filter(activo=True).count()
        self.stdout.write(self.style.SUCCESS(
            f'Listo: {creados} nuevos, {actualizados} actualizados, {errores} errores. '
            f'Catálogo activo: {total} ejercicios.'
        ))
