from django import forms
from django.forms import inlineformset_factory

from .models import CategoriaMensualidad, EjercicioRutina, ProgramacionEnvio, Rutina

DIAS_SEMANA = [
    ('0', 'Lunes'),
    ('1', 'Martes'),
    ('2', 'Miércoles'),
    ('3', 'Jueves'),
    ('4', 'Viernes'),
    ('5', 'Sábado'),
    ('6', 'Domingo'),
]


class RutinaForm(forms.ModelForm):
    class Meta:
        model = Rutina
        fields = ['categoria', 'titulo', 'notas']
        widgets = {
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, gimnasio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if gimnasio:
            self.fields['categoria'].queryset = CategoriaMensualidad.objects.filter(gimnasio=gimnasio)


class EjercicioRutinaForm(forms.ModelForm):
    class Meta:
        model = EjercicioRutina
        fields = ['nombre', 'series', 'repeticiones', 'peso', 'descanso', 'notas', 'orden']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Press banca'}),
            'series': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'repeticiones': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '12 o 10-12'}),
            'peso': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Opcional'}),
            'descanso': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '60 seg'}),
            'notas': forms.TextInput(attrs={'class': 'form-control'}),
            'orden': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }


EjercicioRutinaFormSet = inlineformset_factory(
    Rutina,
    EjercicioRutina,
    form=EjercicioRutinaForm,
    extra=1,
    can_delete=True,
    max_num=100,
)


class ProgramacionEnvioForm(forms.ModelForm):
    dias_semana = forms.MultipleChoiceField(
        choices=DIAS_SEMANA,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Días de la semana (envío semanal)',
    )

    class Meta:
        model = ProgramacionEnvio
        fields = ['rutina', 'frecuencia', 'dia_mes', 'activa']
        widgets = {
            'rutina': forms.Select(attrs={'class': 'form-select'}),
            'frecuencia': forms.Select(attrs={'class': 'form-select'}),
            'dia_mes': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 31}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, gimnasio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if gimnasio:
            self.fields['rutina'].queryset = Rutina.objects.filter(gimnasio=gimnasio).select_related('categoria')
        if self.instance and self.instance.pk and self.instance.dias_semana:
            self.initial['dias_semana'] = [
                d.strip() for d in self.instance.dias_semana.split(',') if d.strip() != ''
            ]

    def clean(self):
        cleaned = super().clean()
        freq = cleaned.get('frecuencia')
        dias = cleaned.get('dias_semana') or []
        dia_mes = cleaned.get('dia_mes')
        if freq == 'semanal' and not dias:
            self.add_error('dias_semana', 'Elegí al menos un día para el envío semanal.')
        if freq == 'mensual' and not dia_mes:
            self.add_error('dia_mes', 'Indicá el día del mes (1-31).')
        return cleaned

    def save(self, commit=True):
        inst = super().save(commit=False)
        dias = self.cleaned_data.get('dias_semana') or []
        inst.dias_semana = ','.join(sorted(dias))
        if commit:
            inst.save()
        return inst
