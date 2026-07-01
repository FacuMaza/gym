from django.db import models
from django.utils import timezone
from datetime import date, datetime, timedelta

class CategoriaMensualidad(models.Model):
    """Categorías de planes de mensualidad, definidas por cada gimnasio."""
    gimnasio = models.ForeignKey('Gimnasio', on_delete=models.CASCADE, related_name='categorias_mensualidad', null=True, blank=True)
    nombre = models.CharField(max_length=100)
    usa_turnos = models.BooleanField(
        default=False,
        help_text='Si está activo, los socios de esta categoría reservan turnos por día y hora.',
    )
    
    def __str__(self):
        return self.nombre

    class Meta:
        db_table = 'CategoriaMensualidades'
        verbose_name = 'Categoría de Mensualidad'
        verbose_name_plural = 'Categorías de Mensualidad'
        unique_together = [['gimnasio', 'nombre']]


class TipoMensualidad(models.Model):
    FRECUENCIA_CHOICES = [
        ('3x_semana', '3 veces por semana'),
        ('todos_dias', 'Todos los días'),
        ('2x_semana', '2 veces por semana'),
        ('1x_semana', '1 vez por semana'),
        ('clases', 'Por clases (cantidad fija)'),
        ('pase_libre', 'Pase libre'),
    ]
    categoria = models.ForeignKey(CategoriaMensualidad, on_delete=models.CASCADE, related_name='tipos_mensualidad', null=True, blank=True)
    tipo = models.CharField(max_length=255)
    frecuencia = models.CharField(max_length=50, choices=FRECUENCIA_CHOICES, default='pase_libre', null=True, blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    clases_incluidas = models.PositiveIntegerField(null=True, blank=True, help_text="Cantidad de clases si es por clases")
    
    def __str__(self):
        if self.categoria:
            return f'{self.categoria.nombre} - {self.tipo} (${self.precio})'
        return f'{self.tipo} (${self.precio})'

    class Meta:
        db_table = 'TipoMensualidades'
        verbose_name = 'TipoMensualidad'
        verbose_name_plural = 'TipoMensualidades'


class Gimnasio(models.Model):
    nombre = models.CharField(max_length=255, default='', blank=True)
    direccion = models.CharField(max_length=255)
    
    def __str__(self):
        return self.nombre or self.direccion

    class Meta: 
        db_table = 'Gimnasios'
        verbose_name = 'Gimnasio'
        verbose_name_plural = 'Gimnasios'


class UsuarioGimnasio(models.Model):
    """Relación many-to-many: una cuenta puede tener muchos gimnasios."""
    usuario = models.ForeignKey('Usuario', on_delete=models.CASCADE, related_name='gimnasios_asignados')
    gimnasio = models.ForeignKey(Gimnasio, on_delete=models.CASCADE, related_name='usuarios_asignados')
    
    class Meta:
        db_table = 'UsuarioGimnasios'
        unique_together = ['usuario', 'gimnasio']


class TipoUsuario(models.Model):
    tipousuario = models.CharField(max_length=255)

    def __str__(self):
        return '%s  '%(self.tipousuario)

    class Meta:
        db_table = 'TipoUsuarios'
        verbose_name = 'TipoUsuario'
        verbose_name_plural = 'TipoUsuarios'

class Usuario(models.Model):
    tipo_usuario = models.ForeignKey(TipoUsuario, on_delete=models.CASCADE)  # Ej: "admin", "entrenador", "miembro"
    usuario = models.CharField(max_length=255, unique=True) # Nombre de usuario
    contrasena = models.CharField(max_length=255)  # Considera el hash de contraseñas

    def __str__(self):
        return '%s %s  '%(self.tipo_usuario,self.usuario)
    class Meta:
        db_table = 'Usuarios'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'


class Socio(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)  # Enlace a la tabla de usuarios
    auth_user = models.OneToOneField(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='socio_perfil',
    )
    nombre = models.CharField(max_length=255)
    apellido = models.CharField(max_length=255)
    dni = models.CharField(max_length=20)  # Asumiendo que el DNI es una cadena
    celular = models.CharField(max_length=30, blank=True, null=True)
    gimnasio = models.ForeignKey(Gimnasio, on_delete=models.CASCADE, related_name="socios",default=None)
    tipo_mensualidad = models.ForeignKey('TipoMensualidad', on_delete=models.SET_NULL, null=True, blank=True) # Relación con TipoMensualidad
    clases_restantes = models.IntegerField(default=0)
    fecha_vencimiento = models.DateField(null=True, blank=True) # Nuevo Campo
    
    def __str__(self):
        return '%s %s %s %s %s  '%(self.usuario,self.nombre,self.apellido,self.dni,self.gimnasio)
    class Meta:
        db_table = 'Socios'
        verbose_name = 'Socio'
        verbose_name_plural = 'Socios'

class Cuota(models.Model):
    socio = models.ForeignKey(Socio, on_delete=models.CASCADE)
    tipo_mensualidad = models.ForeignKey(TipoMensualidad, on_delete=models.CASCADE)
    precio = models.FloatField(null=True, blank=True)
    efectivo = models.FloatField(null=True, blank=True)
    fecha_inicio = models.DateField(default=date.today)
    transferencia = models.FloatField(null=True, blank=True)
    tarjeta_credito = models.FloatField(null=True, blank=True)
    nombre_titular_transferencia = models.CharField(max_length=255, blank=True, null=True)
    gimnasio = models.ForeignKey(Gimnasio, on_delete=models.CASCADE, related_name="cuota",default=None)
    caja = models.ForeignKey('Caja', on_delete=models.SET_NULL, null=True, blank=True, related_name='cuotas')
    
    def __str__(self):
        return '%s %s %s %s %s %s %s '%(self.socio,self.tipo_mensualidad,self.precio,self.efectivo,self.transferencia,self.tarjeta_credito,self.gimnasio)
    class Meta:
        db_table = 'Cuotas'
        verbose_name = 'Cuota'
        verbose_name_plural = 'Cuotas'

class Producto(models.Model):
    """Modelo para los productos disponibles para la venta en el gimnasio."""
    descripcion = models.CharField(max_length=255)
    cantidad = models.IntegerField()  # Stock del producto
    gimnasio = models.ForeignKey(Gimnasio, on_delete=models.CASCADE, related_name="producto",default=None)
    precio = models.FloatField(null=True, blank=True)
    
    
    def __str__(self):
        return '%s  %s %s  %s'%(self.descripcion,self.cantidad,self.gimnasio,self.precio)
    class Meta:
        db_table = 'Productos'
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'

class Profesor(models.Model):
    """Profesores/instructores del gimnasio."""
    nombre = models.CharField(max_length=255)
    apellido = models.CharField(max_length=255)
    gimnasio = models.ForeignKey(Gimnasio, on_delete=models.CASCADE, related_name='profesores', null=True, blank=True)
    telefono = models.CharField(max_length=50, blank=True, null=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.nombre} {self.apellido}'

    class Meta:
        db_table = 'Profesores'
        verbose_name = 'Profesor'
        verbose_name_plural = 'Profesores'


class Adelanto(models.Model):
    """Adelantos de sueldo otorgados al profesor."""
    profesor = models.ForeignKey(Profesor, on_delete=models.CASCADE, related_name='adelantos')
    monto = models.FloatField()
    descripcion = models.CharField(max_length=255, blank=True, default='Adelanto')
    fecha = models.DateField(default=date.today)
    gimnasio = models.ForeignKey(Gimnasio, on_delete=models.CASCADE, related_name='adelantos_profesor', null=True, blank=True)

    def __str__(self):
        return f'{self.profesor} - ${self.monto} ({self.fecha})'

    class Meta:
        db_table = 'Adelantos'
        verbose_name = 'Adelanto'
        verbose_name_plural = 'Adelantos'


class PagoProfesor(models.Model):
    """Pago que el profesor hace (cuando cobra su deuda o abona productos). Genera ingreso real."""
    profesor = models.ForeignKey(Profesor, on_delete=models.CASCADE, related_name='pagos')
    monto = models.FloatField()
    efectivo = models.FloatField(null=True, blank=True, default=0)
    transferencia = models.FloatField(null=True, blank=True, default=0)
    tarjeta_credito = models.FloatField(null=True, blank=True, default=0)
    nombre_titular = models.CharField(max_length=255, blank=True, null=True)
    descripcion = models.CharField(max_length=255, blank=True, default='Pago profesor')
    fecha = models.DateField(default=date.today)
    gimnasio = models.ForeignKey(Gimnasio, on_delete=models.CASCADE, related_name='pagos_profesor', null=True, blank=True)
    caja = models.ForeignKey('Caja', on_delete=models.SET_NULL, null=True, blank=True, related_name='pagos_profesor')
    adelantos_liquidados = models.FloatField(default=0, help_text='Adelantos incluidos en esta liquidación')
    productos_liquidados = models.FloatField(default=0, help_text='Productos a cuenta incluidos en esta liquidación')

    def __str__(self):
        return f'{self.profesor} - ${self.monto} ({self.fecha})'

    class Meta:
        db_table = 'PagosProfesor'
        verbose_name = 'Pago Profesor'
        verbose_name_plural = 'Pagos Profesor'


class Venta(models.Model):
    """Modelo para los registros de ventas."""
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    profesor = models.ForeignKey(Profesor, on_delete=models.SET_NULL, null=True, blank=True, related_name='ventas_a_profesor', help_text="Profesor al que se le vendió el producto (cuenta como crédito a su favor)")
    cantidad = models.IntegerField()
    efectivo = models.FloatField(null=True, blank=True)
    transferencia = models.FloatField(null=True, blank=True)
    tarjeta_credito = models.FloatField(null=True, blank=True)
    nombre_titular = models.CharField(max_length=255, blank=True, null=True, help_text="Titular de transferencia o tarjeta")
    fecha = models.DateField(null=True, blank=True)
    gimnasio = models.ForeignKey(Gimnasio, on_delete=models.CASCADE, related_name="venta",default=None)
    caja = models.ForeignKey('Caja', on_delete=models.SET_NULL, null=True, blank=True, related_name='ventas')
    
    def __str__(self):
        return '%s %s %s %s%s %s%s '%(self.producto,self.usuario,self.cantidad,self.gimnasio,self.efectivo,self.transferencia,self.tarjeta_credito)

    @property
    def monto_total(self):
        return (self.cantidad or 0) * (self.producto.precio or 0)

    class Meta:
        db_table = 'Ventas'
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'


class ingresos(models.Model):
    descripcion = models.CharField(max_length=255)
    monto = models.FloatField(null=True, blank=True)
    tipo_ingreso = models.CharField(max_length=20)
    fecha = models.DateField()
    gimnasio = models.ForeignKey(Gimnasio, on_delete=models.CASCADE, related_name="ingresos",default=None)
    caja = models.ForeignKey('Caja', on_delete=models.SET_NULL, null=True, blank=True, related_name='ingresos')

    def __str__(self):
        return '%s%s%s%s%s '%(self.descripcion, self.monto , self.tipo_ingreso , self.fecha,self.gimnasio)
    
    class Meta:
        db_table = 'ingresos'
        verbose_name = 'ingreso'
        verbose_name_plural = 'ingresos'


class egreso(models.Model):
    descripcion = models.CharField(max_length=255)
    monto = models.FloatField(null=True, blank=True)
    tipo_ingreso = models.CharField(max_length=20)
    fecha = models.DateField()
    gimnasio = models.ForeignKey(Gimnasio, on_delete=models.CASCADE, related_name="egreso",default=None)
    caja = models.ForeignKey('Caja', on_delete=models.SET_NULL, null=True, blank=True, related_name='egresos')

    def __str__(self):
        return '%s %s %s %s%s'%(self.descripcion, self.monto , self.tipo_ingreso , self.fecha,self.gimnasio)
    
    class Meta:
        db_table = 'egresos'
        verbose_name = 'egreso'
        verbose_name_plural = 'egresos'

class extras(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.SET_NULL, null=True, blank=True, related_name="extras")  # Cambio aquí
    ingreso = models.ForeignKey(ingresos, on_delete=models.CASCADE, null=True, blank=True)
    egreso = models.ForeignKey(egreso, on_delete=models.CASCADE, null=True, blank=True)
    descripcion = models.CharField(max_length=255)
    monto = models.FloatField(null=True, blank=True)
    fecha = models.DateField()
    hora = models.DateTimeField(default=timezone.now) # Agrega el campo hora
    gimnasio = models.ForeignKey(Gimnasio, on_delete=models.CASCADE, related_name="extras",default=None)

    def __str__(self):
        return '%s %s %s %s %s %s%s%s' % (self.ingreso, self.egreso, self.descripcion, self.monto, self.fecha,self.gimnasio,self.producto,self.hora)

    class Meta:
        db_table = 'extras'
        verbose_name = 'extra'
        verbose_name_plural = 'extras'


class Gasto(models.Model):
    """Gastos del gimnasio (luz, alquiler, etc.) con forma de pago."""
    FORMA_PAGO_CHOICES = [
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia'),
        ('tarjeta_credito', 'Tarjeta de Crédito'),
    ]
    descripcion = models.CharField(max_length=255)
    monto = models.FloatField()
    forma_pago = models.CharField(max_length=20, choices=FORMA_PAGO_CHOICES)
    fecha = models.DateField(default=date.today)
    gimnasio = models.ForeignKey(Gimnasio, on_delete=models.CASCADE, related_name="gastos")
    caja = models.ForeignKey('Caja', on_delete=models.SET_NULL, null=True, blank=True, related_name='gastos')

    def __str__(self):
        return f'{self.descripcion} - ${self.monto} ({self.get_forma_pago_display()})'

    class Meta:
        db_table = 'gastos'
        verbose_name = 'Gasto'
        verbose_name_plural = 'Gastos'


class Caja(models.Model):
    """Caja diaria: solo una abierta por gimnasio a la vez."""
    gimnasio = models.ForeignKey('Gimnasio', on_delete=models.CASCADE, related_name='cajas')
    usuario_apertura = models.ForeignKey('Usuario', on_delete=models.CASCADE, related_name='cajas_abiertas', null=True)
    fecha_apertura = models.DateTimeField(auto_now_add=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)  # null = abierta
    monto_inicial = models.FloatField(default=0, blank=True)
    total_ingresos = models.FloatField(null=True, blank=True)
    total_egresos = models.FloatField(null=True, blank=True)
    balance = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = 'cajas'
        verbose_name = 'Caja'
        verbose_name_plural = 'Cajas'

    @property
    def esta_abierta(self):
        return self.fecha_cierre is None


class BalanceDiario(models.Model):
    gimnasio = models.ForeignKey('Gimnasio', on_delete=models.CASCADE, related_name='balances')
    fecha = models.DateField(default=date.today)
    total_ingresos = models.FloatField(null=True, blank=True)
    total_egresos = models.FloatField(null=True, blank=True)
    balance = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f'Balance de {self.gimnasio.direccion} el {self.fecha}'

    class Meta:
        db_table = 'Balance Diarios'
        verbose_name = 'Balance Diario'
        verbose_name_plural = 'Balance Diarios'


class RegistroIngreso(models.Model):
    gimnasio = models.ForeignKey(Gimnasio, on_delete=models.CASCADE, related_name='registros_ingreso', null=True, blank=True)
    fecha_ingreso = models.DateTimeField(auto_now_add=True)
    dni_socio = models.CharField(max_length=20)
    clases_restantes_al_ingresar = models.PositiveIntegerField(null=True, blank=True)
    nombre_socio = models.CharField(max_length=100, null=True, blank=True) # Nuevo campo
    apellido_socio = models.CharField(max_length=100, null=True, blank=True) # Nuevo campo

    def __str__(self):
        return f"Ingreso de {self.nombre_socio} {self.apellido_socio} el {self.fecha_ingreso}"

    class Meta:
        db_table = 'Registro Ingresos'
        verbose_name = 'RegistroIngreso'
        verbose_name_plural = 'Registro Ingresos'


class Rutina(models.Model):
    gimnasio = models.ForeignKey(Gimnasio, on_delete=models.CASCADE, related_name='rutinas')
    categoria = models.ForeignKey(CategoriaMensualidad, on_delete=models.CASCADE, related_name='rutinas')
    titulo = models.CharField(max_length=200)
    notas = models.TextField(blank=True)
    creada = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.titulo

    class Meta:
        db_table = 'Rutinas'
        verbose_name = 'Rutina'
        verbose_name_plural = 'Rutinas'


class EjercicioRutina(models.Model):
    rutina = models.ForeignKey(Rutina, on_delete=models.CASCADE, related_name='ejercicios')
    nombre = models.CharField(max_length=200)
    series = models.PositiveIntegerField(default=3)
    repeticiones = models.CharField(max_length=50, default='12')
    peso = models.CharField(max_length=80, blank=True)
    descanso = models.CharField(max_length=80, blank=True)
    notas = models.TextField(blank=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'EjerciciosRutina'
        ordering = ['orden', 'id']
        verbose_name = 'Ejercicio de rutina'
        verbose_name_plural = 'Ejercicios de rutina'

    def __str__(self):
        return self.nombre


class ProgramacionEnvio(models.Model):
    FRECUENCIA_CHOICES = [
        ('diaria', 'Diaria'),
        ('semanal', 'Semanal'),
        ('mensual', 'Mensual'),
    ]
    gimnasio = models.ForeignKey(Gimnasio, on_delete=models.CASCADE, related_name='programaciones_rutina')
    rutina = models.ForeignKey(Rutina, on_delete=models.CASCADE, related_name='programaciones')
    frecuencia = models.CharField(max_length=20, choices=FRECUENCIA_CHOICES, default='semanal')
    dias_semana = models.CharField(
        max_length=30,
        blank=True,
        help_text='Días 0-6 (lun-dom), separados por coma. Ej: 0,2,4',
    )
    dia_mes = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Día del mes (1-31) si es mensual')
    activa = models.BooleanField(default=True)
    ultimo_envio = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'ProgramacionesEnvioRutina'
        verbose_name = 'Programación de envío'
        verbose_name_plural = 'Programaciones de envío'

    def __str__(self):
        return f'{self.rutina.titulo} ({self.get_frecuencia_display()})'


class RutinaEntregada(models.Model):
    socio = models.ForeignKey(Socio, on_delete=models.CASCADE, related_name='rutinas_entregadas')
    rutina = models.ForeignKey(Rutina, on_delete=models.CASCADE, related_name='entregas')
    programacion = models.ForeignKey(
        ProgramacionEnvio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='entregas',
    )
    fecha_publicacion = models.DateField(default=date.today)

    class Meta:
        db_table = 'RutinasEntregadas'
        ordering = ['-fecha_publicacion', '-id']
        verbose_name = 'Rutina entregada'
        verbose_name_plural = 'Rutinas entregadas'
        unique_together = [['socio', 'rutina', 'fecha_publicacion']]

    def __str__(self):
        return f'{self.rutina.titulo} → {self.socio} ({self.fecha_publicacion})'


class HorarioTurno(models.Model):
    """Franja horaria fija; una o más categorías comparten el mismo cupo."""
    DIAS_SEMANA = [
        (0, 'Lunes'),
        (1, 'Martes'),
        (2, 'Miércoles'),
        (3, 'Jueves'),
        (4, 'Viernes'),
        (5, 'Sábado'),
        (6, 'Domingo'),
    ]
    gimnasio = models.ForeignKey(Gimnasio, on_delete=models.CASCADE, related_name='horarios_turno')
    categorias = models.ManyToManyField(CategoriaMensualidad, related_name='horarios_turno')
    dia_semana = models.PositiveSmallIntegerField(choices=DIAS_SEMANA)
    hora = models.TimeField()
    cupo_maximo = models.PositiveIntegerField(default=12)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'HorariosTurno'
        ordering = ['dia_semana', 'hora']
        verbose_name = 'Horario de turno'
        verbose_name_plural = 'Horarios de turno'
        unique_together = [['gimnasio', 'dia_semana', 'hora']]

    def __str__(self):
        dias = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
        dia = dias[self.dia_semana] if self.dia_semana <= 6 else str(self.dia_semana)
        cats = self.etiqueta_categorias()
        return f'{cats} {dia} {self.hora.strftime("%H:%M")} (cupo {self.cupo_maximo})'

    def etiqueta_categorias(self):
        nombres = list(self.categorias.order_by('nombre').values_list('nombre', flat=True))
        return ' + '.join(nombres) if nombres else '—'

    @property
    def hora_fin(self):
        fin = datetime.combine(datetime.today(), self.hora) + timedelta(hours=1)
        return fin.time()


class ReservaTurno(models.Model):
    socio = models.ForeignKey(Socio, on_delete=models.CASCADE, related_name='reservas_turno')
    horario_turno = models.ForeignKey(HorarioTurno, on_delete=models.CASCADE, related_name='reservas')
    fecha = models.DateField()
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ReservasTurno'
        ordering = ['fecha', 'horario_turno__hora']
        verbose_name = 'Reserva de turno'
        verbose_name_plural = 'Reservas de turno'
        unique_together = [['socio', 'horario_turno', 'fecha']]

    def __str__(self):
        return f'{self.socio} — {self.horario_turno} ({self.fecha})'


class EstadoAccesoSistema(models.Model):
    """Interruptor global: pausa el ingreso de todos excepto Super Usuario."""
    pausado = models.BooleanField(default=False)
    pausado_en = models.DateTimeField(null=True, blank=True)
    pausado_por = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    pausado_por_vencimiento = models.BooleanField(default=False)
    periodos_pagados = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        verbose_name = 'Estado de acceso al sistema'
        verbose_name_plural = 'Estado de acceso al sistema'

    def __str__(self):
        return 'Pausado' if self.pausado else 'Activo'

    @classmethod
    def get_estado(cls):
        from django.db.utils import OperationalError, ProgrammingError
        try:
            obj, _ = cls.objects.get_or_create(pk=1, defaults={'pausado': False})
            return obj
        except (OperationalError, ProgrammingError):
            return cls(pk=1, pausado=False)

