from django import forms
from django.forms import DateInput
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date
from .models import *



class SocioForm(forms.ModelForm):
    codigo_pais = forms.ChoiceField(
        choices=[
            ('+549', '🇦🇷 +549'),
            ('+591', '🇧🇴 +591'),
        ],
        initial='+549',
        widget=forms.Select(attrs={'class': 'form-select', 'style': 'max-width: 150px;'}),
        label='Prefijo país'
    )

    class Meta:
        model = Socio
        fields = ['nombre', 'apellido', 'dni', 'celular', 'tipo_mensualidad']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control'}),
            'dni': forms.TextInput(attrs={'class': 'form-control'}),
            'celular': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 3875123123'}),
        }

    def __init__(self, *args, gimnasio=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Si el socio ya tiene celular guardado, separar prefijo + número local para edición cómoda.
        celular_actual = (self.instance.celular or '').strip() if self.instance and self.instance.pk else ''
        if celular_actual.startswith('+549'):
            self.initial['codigo_pais'] = '+549'
            self.initial['celular'] = celular_actual[4:]
        elif celular_actual.startswith('+591'):
            self.initial['codigo_pais'] = '+591'
            self.initial['celular'] = celular_actual[4:]

        if gimnasio:
            self.gimnasio_fijo = gimnasio
            self.fields['tipo_mensualidad'].queryset = TipoMensualidad.objects.filter(categoria__gimnasio=gimnasio).distinct()
        else:
            self.gimnasio_fijo = None

    def clean(self):
        cleaned = super().clean()
        numero_local = (cleaned.get('celular') or '').strip()
        codigo_pais = (cleaned.get('codigo_pais') or '+549').strip()

        if numero_local:
            numero_local = ''.join(ch for ch in numero_local if ch.isdigit())
            if not numero_local:
                self.add_error('celular', 'Ingresá un número válido (solo dígitos).')
            else:
                # Guardamos en formato E.164 para máxima compatibilidad con Twilio.
                cleaned['celular'] = f'{codigo_pais}{numero_local}'
        else:
            cleaned['celular'] = ''

        return cleaned


class TipoUsuarioForm(forms.ModelForm):
    class Meta:
        model = TipoUsuario
        fields = ['tipousuario']
        widgets = {
            'tipousuario': forms.TextInput(attrs={'class': 'form-control'}),
        }

from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

class UsuarioForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        label="Nombre de usuario",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
        required=False # O True, dependiendo de si quieres que el email sea obligatorio
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="Contraseña"
    )
    tipo_usuario = forms.ModelChoiceField(
        queryset=TipoUsuario.objects.exclude(tipousuario='super_usuario'),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Tipo de Usuario"
    )
    gimnasios = forms.ModelMultipleChoiceField(
        queryset=Gimnasio.objects.all().order_by('nombre', 'direccion'),
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
        label="Gimnasio(s)",
        required=False
    )

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get('tipo_usuario')
        gimnasios = cleaned.get('gimnasios') or []
        if tipo and tipo.tipousuario == 'empleado' and not gimnasios:
            raise ValidationError('Debe asignar al menos un gimnasio cuando el tipo es empleado.')
        return cleaned

    def save(self, commit=True):
        username = self.cleaned_data['username']
        email = self.cleaned_data['email']
        password = self.cleaned_data['password']
        tipo_usuario = self.cleaned_data['tipo_usuario']

        # Crear el usuario en auth_user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        # Crea el usuario en tu modelo Usuario personalizado
        usuario_custom = Usuario.objects.create(
            tipo_usuario=tipo_usuario,
            usuario=username,
            contrasena=user.password  # El password ya viene hasheado
        )

        # Asignar gimnasios: los seleccionados, o todos si es admin sin selección
        gimnasios = list(self.cleaned_data.get('gimnasios', []))
        if not gimnasios and tipo_usuario.tipousuario == 'admin':
            gimnasios = list(Gimnasio.objects.all())
        for g in gimnasios:
            UsuarioGimnasio.objects.get_or_create(usuario=usuario_custom, gimnasio=g)

        return usuario_custom


class LoginForm(forms.Form):
    usuario = forms.CharField(max_length=255)
    contrasena = forms.CharField(widget=forms.PasswordInput)

class GimnasioForm(forms.ModelForm):
    class Meta:
        model = Gimnasio
        fields = ['nombre', 'direccion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del gimnasio'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control'}),
        }




class CrearPlanMensualidadForm(forms.Form):
    """Solo nombre del plan - el usuario lo arma como quiere."""
    nombre = forms.CharField(
        max_length=100,
        label="Nombre del plan de mensualidad",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Plan Fitness, Taebo, etc.'})
    )


class CrearOpcionMensualidadForm(forms.Form):
    """Opciones dentro del plan: libre, 12 clases, 8 clases, etc."""
    nombre = forms.CharField(
        max_length=255,
        label="Nombre (ej: libre, 12 clases, 8 clases)",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: libre, 12 clases, 8 clases'})
    )
    precio = forms.DecimalField(
        max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        label="Precio ($)"
    )
    clases_incluidas = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Dejar vacío si es pase libre'}),
        label="Clases incluidas (opcional, para contabilizar)"
    )


class TipoMensualidadForm(forms.ModelForm):
    """Editar una opción existente."""
    class Meta:
        model = TipoMensualidad
        fields = ['tipo', 'precio', 'clases_incluidas']
        widgets = {
            'tipo': forms.TextInput(attrs={'class': 'form-control'}),
            'precio': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'clases_incluidas': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Vacío = pase libre'})
        }

from django import forms
from .models import Socio, TipoMensualidad

class AsignarMensualidadForm(forms.Form):
    socio = forms.CharField(
        label="Socio",
        widget=forms.TextInput(attrs={'readonly': 'readonly'}),
    )
    tipo_mensualidad_display = forms.CharField(label="Tipo de Mensualidad Actual", required=False, widget=forms.TextInput(attrs={'readonly':'readonly'}))
    tipo_mensualidad = forms.ModelChoiceField(
        queryset=TipoMensualidad.objects.all(),
        label="Seleccionar Nueva Mensualidad",
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="Seleccione una mensualidad"
    )
    metodo_pago = forms.ChoiceField(choices=[
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia'),
        ('tarjeta_credito', 'Tarjeta de Crédito')
    ], label="Método de Pago")
    monto = forms.FloatField(label="Monto Recibido")
    clases_restantes = forms.IntegerField(label="Clases Restantes", required=False, widget=forms.NumberInput())

    def __init__(self, *args, **kwargs):
        initial_socio = kwargs.pop('initial_socio', None)
        initial_mensualidad = kwargs.pop('initial_mensualidad', None)
        gimnasio = kwargs.pop('gimnasio', None)
        super().__init__(*args, **kwargs)
        if gimnasio or (initial_socio and initial_socio.gimnasio):
            gym = gimnasio or initial_socio.gimnasio
            from .models import CategoriaMensualidad
            qs = TipoMensualidad.objects.filter(categoria__gimnasio=gym)
            self.fields['tipo_mensualidad'].queryset = qs.distinct().order_by('categoria__nombre', 'tipo')
        if initial_socio:
            self.initial['socio'] = f"{initial_socio.nombre} {initial_socio.apellido}"
            self.fields['socio'].widget.attrs['value'] = f"{initial_socio.nombre} {initial_socio.apellido}"
        if initial_mensualidad:
            self.initial['tipo_mensualidad'] = initial_mensualidad
            self.fields['tipo_mensualidad'].initial = initial_mensualidad
    
    def clean(self):
        cleaned_data = super().clean()
        tipo_mensualidad_seleccionada = cleaned_data.get('tipo_mensualidad')
        socio_value = cleaned_data.get('socio')
        monto = cleaned_data.get('monto')
        clases_restantes = cleaned_data.get('clases_restantes')
        
        if socio_value:
            cleaned_data['socio'] =  self.initial['socio']
            try:
                socio_id = self.initial.get('socio_id')
                socio = Socio.objects.get(pk=socio_id)
                
                if socio.tipo_mensualidad:
                     # Si el socio ya tiene una mensualidad asignada
                     tipo_mensualidad_actual = socio.tipo_mensualidad
                     if not tipo_mensualidad_seleccionada:
                         # si no se selecciono una nueva mensualidad, uso la actual
                         cleaned_data['tipo_mensualidad'] = tipo_mensualidad_actual
                     
                     #Validacion del monto, tanto si selecciono una nueva mensualidad como si usa la misma
                     if monto is None:
                                  self.add_error('monto', 'Este campo es obligatorio al seleccionar una mensualidad')
                     elif cleaned_data['tipo_mensualidad'].precio != monto:
                                  self.add_error('monto', 'El monto recibido no coincide con el precio de la mensualidad seleccionada.')
                     #Validacion de clases restantes
                     if cleaned_data['tipo_mensualidad'].frecuencia == 'clases':
                           self.fields['clases_restantes'].required = True
                           if clases_restantes is None:
                                self.add_error('clases_restantes', 'Obligatorio para mensualidad por clases.')
                     else:
                        self.fields['clases_restantes'].required = False
                        
                else:#Si el socio no tiene una mensualidad asignada
                     
                     if not tipo_mensualidad_seleccionada:
                          self.add_error('tipo_mensualidad', 'Debe Seleccionar una Mensualidad.')
                     elif tipo_mensualidad_seleccionada:
                           if monto is None:
                                  self.add_error('monto', 'Este campo es obligatorio al seleccionar una nueva mensualidad')
                           elif tipo_mensualidad_seleccionada.precio != monto:
                                  self.add_error('monto', 'El monto recibido no coincide con el precio de la mensualidad seleccionada.')
                           
                           if cleaned_data['tipo_mensualidad'].frecuencia == 'clases':
                              self.fields['clases_restantes'].required = True
                              if clases_restantes is None:
                                self.add_error('clases_restantes', 'Obligatorio para mensualidad por clases.')
                           else:
                                 self.fields['clases_restantes'].required = False

            except Socio.DoesNotExist:
                 self.add_error('socio', 'Socio no encontrado')
        return cleaned_data

    
class CobrarMensualidadForm(forms.Form):
    """Permite una o varias formas de pago. La suma debe igualar al total."""
    efectivo = forms.DecimalField(
        required=False, initial=0, min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control monto-pago', 'placeholder': '0', 'step': '0.01'}),
        label="Efectivo ($)"
    )
    transferencia = forms.DecimalField(
        required=False, initial=0, min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control monto-pago', 'placeholder': '0', 'step': '0.01'}),
        label="Transferencia ($)"
    )
    tarjeta_credito = forms.DecimalField(
        required=False, initial=0, min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control monto-pago', 'placeholder': '0', 'step': '0.01'}),
        label="Tarjeta ($)"
    )
    nombre_titular = forms.CharField(
        max_length=255,
        required=False,
        label="Nombre del titular (obligatorio si usás transferencia)",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Juan Pérez'})
    )

    def __init__(self, *args, precio_total=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.precio_total = precio_total

    def clean(self):
        cleaned = super().clean()
        ef = float(cleaned.get('efectivo') or 0)
        tr = float(cleaned.get('transferencia') or 0)
        tc = float(cleaned.get('tarjeta_credito') or 0)
        total = ef + tr + tc
        precio = float(self.precio_total or 0)
        if precio and abs(total - precio) > 0.01:
            raise ValidationError(f'La suma de los pagos (${total:.2f}) debe ser igual al total (${precio:.2f}).')
        if tr > 0 and not (cleaned.get('nombre_titular') or '').strip():
            raise ValidationError('Debe ingresar el nombre del titular cuando hay pago por transferencia.')
        return cleaned


class SeleccionarFechaRenovacionForm(forms.Form):
    fecha_renovacion = forms.DateField(widget=DateInput(attrs={'type': 'date', 'min': str(date.today())}))


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['descripcion', 'cantidad', 'gimnasio', 'precio']


class ProfesorForm(forms.ModelForm):
    class Meta:
        model = Profesor
        fields = ['nombre', 'apellido', 'telefono', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apellido'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Teléfono (opcional)'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class AdelantoForm(forms.ModelForm):
    class Meta:
        model = Adelanto
        fields = ['monto', 'descripcion', 'fecha']
        widgets = {
            'monto': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01', 'min': '0.01', 'placeholder': '0'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Adelanto'}),
            'fecha': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fecha'].initial = date.today()


class PagoProfesorForm(forms.Form):
    """Formulario para registrar el pago que hace el profesor (cuando abona su deuda)."""
    METODO_CHOICES = [
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia'),
        ('tarjeta_credito', 'Tarjeta'),
    ]
    monto = forms.DecimalField(
        min_value=0.01,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0'}),
        label='Monto a pagar'
    )
    metodo_pago = forms.ChoiceField(
        choices=METODO_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Forma de pago'
    )
    nombre_titular = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del titular', 'id': 'id_titular_pago'}),
        label='Titular'
    )

    def clean(self):
        cleaned = super().clean()
        metodo = cleaned.get('metodo_pago')
        titular = (cleaned.get('nombre_titular') or '').strip()
        if metodo in ('transferencia', 'tarjeta_credito') and not titular:
            raise ValidationError('Ingresá el nombre del titular cuando usás transferencia o tarjeta.')
        return cleaned


class VentaForm(forms.ModelForm):
    total = forms.DecimalField(
        required=False,
        widget=forms.TextInput(attrs={'readonly': True, 'id': 'id_total'}),
        initial=0
    )
    
    efectivo = forms.DecimalField(required=False, initial=0)
    transferencia = forms.DecimalField(required=False, initial=0)
    tarjeta_credito = forms.DecimalField(required=False, initial=0)
    nombre_titular = forms.CharField(required=False, label='Nombre del titular', widget=forms.TextInput(attrs={'placeholder': 'Ej: Juan Pérez'}))

    class Meta:
        model = Venta
        fields = ['producto', 'cantidad', 'profesor', 'efectivo', 'transferencia', 'tarjeta_credito', 'nombre_titular']

    def __init__(self, *args, gimnasio=None, **kwargs):
        super(VentaForm, self).__init__(*args, **kwargs)
        qs = Producto.objects.filter(gimnasio=gimnasio) if gimnasio else Producto.objects.all()
        self.fields['producto'].queryset = qs
        self.fields['producto'].label_from_instance = self.producto_label_from_instance
        # Profesores del gimnasio (opcional)
        from .models import Profesor
        prof_qs = Profesor.objects.filter(gimnasio=gimnasio, activo=True).order_by('apellido', 'nombre') if gimnasio else Profesor.objects.filter(activo=True)
        self.fields['profesor'].queryset = prof_qs
        self.fields['profesor'].required = False
        self.fields['profesor'].empty_label = '— Sin profesor (venta general)'

    def producto_label_from_instance(self, obj):
       return f"{obj.descripcion} - ${obj.precio}"
    
    def clean(self):
        cleaned_data = super().clean()
        producto = cleaned_data.get('producto')
        cantidad = cleaned_data.get('cantidad')
        profesor = cleaned_data.get('profesor')
        efectivo = cleaned_data.get('efectivo') or 0
        transferencia = cleaned_data.get('transferencia') or 0
        tarjeta_credito = cleaned_data.get('tarjeta_credito') or 0
        total = self.data.get('total')
        
        if producto and cantidad:
            if cantidad > producto.cantidad:
                raise ValidationError(
                     f'No hay suficiente stock para este producto. Hay {producto.cantidad} disponibles.'
                )
        
        # Si es venta a profesor (cuenta), no validar pagos; se carga a su cuenta
        if profesor:
            cleaned_data['efectivo'] = 0
            cleaned_data['transferencia'] = 0
            cleaned_data['tarjeta_credito'] = 0
        elif total is not None:
            total = float(total)
            suma_pagos = float(efectivo) + float(transferencia) + float(tarjeta_credito)
            if suma_pagos != total:
                raise ValidationError("La suma de los pagos debe ser igual al total.")
            if (float(transferencia) > 0 or float(tarjeta_credito) > 0):
                nombre_titular = (cleaned_data.get('nombre_titular') or '').strip()
                if not nombre_titular:
                    raise ValidationError("El nombre del titular es obligatorio cuando usás transferencia o tarjeta.")
           
        return cleaned_data

class ExtrasForm(forms.ModelForm):
    TIPO_CHOICES = [
        ('ingreso', 'Ingreso'),
        ('egreso', 'Egreso'),
    ]
    tipo = forms.ChoiceField(choices=TIPO_CHOICES, widget=forms.RadioSelect, label='Tipo')
    fecha = forms.DateField(widget=forms.HiddenInput(), initial=timezone.now().date())
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.all(),
        required=False,
        empty_label="--- Seleccionar Producto (Opcional) ---",
        label="Producto (Opcional)"
    )

    class Meta:
        model = extras
        fields = ['descripcion', 'monto', 'gimnasio', 'tipo', 'producto']

    def __init__(self, *args, gimnasio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if gimnasio:
            self.fields['gimnasio'].queryset = Gimnasio.objects.filter(pk=gimnasio.pk)
            self.initial['gimnasio'] = gimnasio
            self.fields['producto'].queryset = Producto.objects.filter(gimnasio=gimnasio)

    def clean(self):
        cleaned_data = super().clean()
        # Asignamos la fecha inicial si aún no está en el cleaned_data (en caso de que ya tenga un valor predefinido)
        if 'fecha' not in cleaned_data:
            cleaned_data['fecha'] = self.fields['fecha'].initial
        return cleaned_data
    


##historial de ingrso 
class HistorialIngresosForm(forms.Form):
    fecha_inicio = forms.DateField(
        label='Fecha Inicio',
        widget=forms.DateInput(attrs={'type': 'date'}),
        initial=date.today(),
        required = False,
    )
    fecha_fin = forms.DateField(
        label='Fecha Fin',
        widget=forms.DateInput(attrs={'type': 'date'}),
          initial=date.today(),
        required = False,
    )

class GastoForm(forms.Form):
    """Formulario para registrar un gasto (luz, alquiler, etc.)."""
    descripcion = forms.CharField(max_length=255, label="Descripción", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Pago de luz'}))
    monto = forms.FloatField(label="Monto", min_value=0.01, widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}))
    forma_pago = forms.ChoiceField(
        choices=[('efectivo', 'Efectivo'), ('transferencia', 'Transferencia'), ('tarjeta_credito', 'Tarjeta de Crédito')],
        label="Forma de pago",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    fecha = forms.DateField(label="Fecha", widget=forms.HiddenInput(), initial=date.today)


## SELECCIONAR GYM DENTRO DEL DIARIO

class SeleccionGimnasioForm(forms.Form):
    gimnasio = forms.ModelChoiceField(queryset=Gimnasio.objects.all(), label="Seleccionar Gimnasio")