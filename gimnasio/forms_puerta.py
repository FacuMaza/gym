from django import forms

from .models import ConfiguracionPuerta


class ConfiguracionPuertaForm(forms.ModelForm):
    pulso_segundos = forms.IntegerField(
        min_value=1,
        max_value=30,
        initial=3,
        label='Tiempo que la puerta queda libre (segundos)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 30}),
    )

    class Meta:
        model = ConfiguracionPuerta
        fields = ['activa']
        widgets = {
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'activa': 'Abrir la puerta automáticamente cuando el ingreso sale en verde',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.pulso_ms:
            self.fields['pulso_segundos'].initial = max(1, round(self.instance.pulso_ms / 1000))

    def save(self, commit=True):
        instance = super().save(commit=False)
        seg = self.cleaned_data.get('pulso_segundos') or 3
        instance.pulso_ms = seg * 1000
        if commit:
            instance.save()
        return instance
