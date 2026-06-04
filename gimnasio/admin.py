from django.contrib import admin
from .models import CategoriaMensualidad, TipoMensualidad

@admin.register(CategoriaMensualidad)
class CategoriaMensualidadAdmin(admin.ModelAdmin):
    list_display = ['nombre']

@admin.register(TipoMensualidad)
class TipoMensualidadAdmin(admin.ModelAdmin):
    list_display = ['tipo', 'categoria', 'frecuencia', 'precio', 'clases_incluidas']
    list_filter = ['categoria', 'frecuencia']
