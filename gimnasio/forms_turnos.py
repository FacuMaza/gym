from django import forms
from datetime import datetime, timedelta

from .models import CategoriaMensualidad, HorarioTurno

DIAS_SEMANA = [
    (0, 'Lunes'),
    (1, 'Martes'),
    (2, 'Miércoles'),
    (3, 'Jueves'),
    (4, 'Viernes'),
    (5, 'Sábado'),
    (6, 'Domingo'),
]


class HorarioTurnoRangoForm(forms.Form):
    """Alta de horarios: rango de días y horas (categorías vienen de la combinación en /turnos/)."""
    dia_desde = forms.ChoiceField(
        choices=DIAS_SEMANA,
        label='Día desde',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    dia_hasta = forms.ChoiceField(
        choices=DIAS_SEMANA,
        label='Día hasta',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    hora_desde = forms.TimeField(
        label='Hora desde',
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
    )
    hora_hasta = forms.TimeField(
        label='Hora hasta',
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
    )
    cupo_maximo = forms.IntegerField(
        label='Cupo máximo',
        min_value=1,
        initial=12,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
    )
    activo = forms.BooleanField(
        label='Activo',
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('dia_desde') is not None and cleaned.get('dia_hasta') is not None:
            if int(cleaned['dia_desde']) > int(cleaned['dia_hasta']):
                self.add_error('dia_hasta', 'El día «Hasta» debe ser igual o posterior a «Desde».')
        hora_desde = cleaned.get('hora_desde')
        hora_hasta = cleaned.get('hora_hasta')
        if hora_desde and hora_hasta:
            if hora_desde >= hora_hasta:
                self.add_error('hora_hasta', '«Hora hasta» debe ser posterior a «Hora desde».')
            elif not self._horas_en_rango(hora_desde, hora_hasta):
                self.add_error('hora_hasta', 'El rango debe incluir al menos una clase de 1 hora.')
        return cleaned

    def _horas_en_rango(self, hora_desde, hora_hasta):
        inicio = datetime.combine(datetime.today(), hora_desde)
        fin_bloque = datetime.combine(datetime.today(), hora_hasta)
        horas = []
        while inicio + timedelta(hours=1) <= fin_bloque:
            horas.append(inicio.time())
            inicio += timedelta(hours=1)
        return horas

    def dias_en_rango(self):
        if not self.cleaned_data:
            return []
        d0 = int(self.cleaned_data['dia_desde'])
        d1 = int(self.cleaned_data['dia_hasta'])
        return list(range(d0, d1 + 1))

    def horas_en_rango(self):
        if not self.cleaned_data:
            return []
        return self._horas_en_rango(
            self.cleaned_data['hora_desde'],
            self.cleaned_data['hora_hasta'],
        )


class HorarioTurnoForm(forms.ModelForm):
    categorias = forms.ModelMultipleChoiceField(
        queryset=CategoriaMensualidad.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label='Categorías (comparten cupo)',
    )

    class Meta:
        model = HorarioTurno
        fields = ['categorias', 'dia_semana', 'hora', 'cupo_maximo', 'activo']
        widgets = {
            'dia_semana': forms.Select(attrs={'class': 'form-select'}),
            'hora': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'cupo_maximo': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, gimnasio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if gimnasio:
            self.fields['categorias'].queryset = (
                CategoriaMensualidad.objects.filter(gimnasio=gimnasio).order_by('nombre')
            )

    def clean_categorias(self):
        cats = self.cleaned_data.get('categorias')
        if not cats:
            raise forms.ValidationError('Elegí al menos una categoría.')
        return cats
