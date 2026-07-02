from django import forms

from .models import ConfiguracionPuerta


class ConfiguracionPuertaForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionPuerta
        fields = ['activa', 'url_agente', 'puerto_arduino', 'pulso_ms', 'espera_serial']
        widgets = {
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'url_agente': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'http://127.0.0.1:8765',
            }),
            'puerto_arduino': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Vacío = automático (COM5, /dev/ttyUSB0…)',
            }),
            'pulso_ms': forms.NumberInput(attrs={'class': 'form-control', 'min': 500, 'max': 30000}),
            'espera_serial': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 10, 'step': 0.5}),
        }
        labels = {
            'activa': 'Puerta automática activa',
            'url_agente': 'Dirección del agente en esta PC',
            'puerto_arduino': 'Puerto USB del Arduino (opcional)',
            'pulso_ms': 'Duración de apertura (milisegundos)',
            'espera_serial': 'Espera al conectar USB (segundos)',
        }
        help_texts = {
            'puerto_arduino': 'Dejalo vacío si solo tenés el Arduino conectado. Si hay varios USB, poné COM5 (Windows) o /dev/ttyUSB0 (Linux).',
        }

    def clean_pulso_ms(self):
        valor = self.cleaned_data['pulso_ms']
        if valor < 500 or valor > 30000:
            raise forms.ValidationError('Entre 500 y 30000 ms.')
        return valor
