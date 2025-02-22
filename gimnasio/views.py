from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.hashers import check_password
from django.contrib.auth.hashers import make_password
from django.contrib.auth import login, logout,authenticate
from django.urls import reverse
from datetime import date, timedelta
from django.http import JsonResponse
from django.contrib import messages
from django.db import transaction
from django.db.models import F
import json
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache
from .models import *
from .forms import *
# Create your views here.

@never_cache
def login_view(request):
    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # Establecer el tipo de usuario en la sesión
            if user.is_superuser:
                request.session['tipo_usuario'] = 'admin'  # <---- AQUI
            else:
                try:
                    usuario_modelo = Usuario.objects.get(usuario=username)
                    request.session['tipo_usuario'] = usuario_modelo.tipo_usuario.tipousuario
                except Usuario.DoesNotExist:
                    request.session['tipo_usuario'] = 'miembro' #Valor por defecto si no existe en la tabla Usuario

            # Obtener el parámetro 'next' de la URL
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            else:
                return redirect('index')
        else:
            error = 'Usuario o contraseña incorrecta'
    return render(request, 'login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('login')




@login_required
def index(request):
    usuario = request.user.username
    tipo_usuario_valor = None # Inicializar la variable

    if request.user.is_superuser:
        tipo_usuario_valor = 'admin'
    elif request.user.groups.filter(name='empleado').exists():
        tipo_usuario_valor = 'empleado'
    else:
        # Intenta obtener el tipo de usuario de tu modelo Usuario
        try:
            usuario_obj = Usuario.objects.get(usuario=request.user.username)
            tipo_usuario_valor = usuario_obj.tipo_usuario.tipousuario  # Obtén el valor del campo tipousuario
        except Usuario.DoesNotExist:
            tipo_usuario_valor = 'miembro'

    # ESTABLECER LA VARIABLE DE SESSION, AHORA ES EL LUGAR CORRECTO
    request.session['tipo_usuario'] = tipo_usuario_valor

    # Obtener los últimos socios, cuotas y ventas
    ultimos_socios = Socio.objects.order_by('-id')[:2]
    ultimas_cuotas = Cuota.objects.order_by('-id')[:2]
    ultimas_ventas = Venta.objects.order_by('-id')[:2]

    return render(request, 'index.html', {
        'usuario': usuario,
        'tipo_usuario': tipo_usuario_valor,
        'ultimos_socios': ultimos_socios,
        'ultimas_cuotas': ultimas_cuotas,
        'ultimas_ventas': ultimas_ventas
    })


##SOCIOS

def lista_socios(request):
    socios = Socio.objects.all()
    return render(request, 'lista_socios.html', {'socios': socios})


@login_required
def crear_socio(request):
    current_user = None  # Inicializamos current_user como None

    if request.user.username:  # Verificamos si el usuario autenticado tiene username
        current_user = Usuario.objects.filter(usuario=request.user.username).first()  # obtenemos un objeto usuario o None

    if request.method == 'POST':
        form = SocioForm(request.POST)
        if form.is_valid():
            if current_user:  # Verificamos que current_user tenga un valor
                nuevo_socio = form.save(commit=False)
                nuevo_socio.usuario = current_user  # Asignamos el usuario
                nuevo_socio.save()  # Guardamos el socio (ahora con tipo_mensualidad)
                return redirect('lista_socios')
            else:
                form.add_error(None, 'El usuario actual no está registrado en el sistema.')  # Error si no se encuentra el usuario
    else:
        form = SocioForm()
    return render(request, 'crear_socio.html', {'form': form, 'current_user': current_user})


def editar_socio(request, pk):
    """Edita un socio existente."""
    socio = get_object_or_404(Socio, pk=pk)
    if request.method == 'POST':
        form = SocioForm(request.POST, instance=socio)
        if form.is_valid():
            form.save()
            return redirect('lista_socios')
    else:
        form = SocioForm(instance=socio)
    return render(request, 'editar_socio.html', {'form': form, 'socio': socio})

def eliminar_socio(request, pk):
    """Elimina un socio existente."""
    socio = get_object_or_404(Socio, pk=pk)
    
    if request.method == 'POST':
        socio.delete()
        return redirect('lista_socios')
    return render(request, 'eliminar_socio.html', {'socio': socio})

def detalle_socio(request, pk):
    socio = get_object_or_404(Socio, pk=pk)
    ultima_cuota = Cuota.objects.filter(socio=socio).order_by('-id').first()
    return render(request, 'detalle_socio.html', {'socio': socio, 'ultima_cuota': ultima_cuota})

## TIPO DE USUARIOS

def tipo_usuario_list(request):
    tipos_usuario = TipoUsuario.objects.all()
    return render(request, 'tipo_usuario_list.html', {'tipos_usuario': tipos_usuario})

def tipo_usuario_create(request):
    if request.method == 'POST':
        form = TipoUsuarioForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('tipo_usuario_list')
    else:
        form = TipoUsuarioForm()
    return render(request, 'tipo_usuario_form.html', {'form': form})

def tipo_usuario_update(request, pk):
    tipo_usuario = get_object_or_404(TipoUsuario, pk=pk)
    if request.method == 'POST':
        form = TipoUsuarioForm(request.POST, instance=tipo_usuario)
        if form.is_valid():
            form.save()
            return redirect('tipo_usuario_list')
    else:
        form = TipoUsuarioForm(instance=tipo_usuario)
    return render(request, 'tipo_usuario_form.html', {'form': form})

def tipo_usuario_delete(request, pk):
    tipo_usuario = get_object_or_404(TipoUsuario, pk=pk)
    if request.method == 'POST':
        tipo_usuario.delete()
        return redirect('tipo_usuario_list')
    return render(request, 'tipo_usuario_confirm_delete.html', {'tipo_usuario': tipo_usuario})



##USUARIOS

def usuario_create(request):
    if request.method == 'POST':
        form = UsuarioForm(request.POST)
        if form.is_valid():
            form.save() #Formulario seguro
            return redirect('usuario_list')
    else:
        form = UsuarioForm()
    return render(request, 'usuario_form.html', {'form': form})

def usuario_list(request):
    usuarios = Usuario.objects.all()
    return render(request, 'usuario_list.html', {'usuarios': usuarios})


def usuario_update(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    if request.method == 'POST':
        form = UsuarioForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            return redirect('usuario_list')
    else:
        form = UsuarioForm(instance=usuario)
    return render(request, 'usuario_form.html', {'form': form})

def usuario_delete(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    try:
        user = User.objects.get(username=usuario.usuario)
    except User.DoesNotExist:
        # Log the error or handle the case where the User doesn't exist.
        print(f"Warning: User with username '{usuario.usuario}' not found in auth_user.")
        user = None

    if request.method == 'POST':
        # Delete the Usuario first
        username = usuario.usuario  # Store username before deleting
        usuario.delete()

        # Then delete the corresponding User if it exists and if not, this does not generate error
        if user:
            user.delete()
            print(f"User with username '{username}' deleted successfully from auth_user.")

        return redirect('usuario_list')

    return render(request, 'usuario_confirm_delete.html', {'usuario': usuario})



##login
def password_reset_request(request):
    if request.method == 'POST':
        username = request.POST.get('usuario')
        try:
            usuario = Usuario.objects.get(usuario=username)
            # Redirige directamente a la vista de confirmación de restablecimiento
            return redirect('password_reset_confirm', pk=usuario.pk)
        except Usuario.DoesNotExist:
            return render(request, 'password_reset_request.html', {'error': 'Usuario no encontrado'})
    return render(request, 'password_reset_request.html')

def password_reset_confirm(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        if new_password != confirm_password:
            return render(request, 'password_reset_confirm.html', {'error': 'Las contraseñas no coinciden', 'pk': pk})

        # Hashear la contraseña
        hashed_password = make_password(new_password)
        usuario.contrasena = hashed_password
        usuario.save()

        # Actualizar la contraseña en el sistema de autenticación de Django
        django_user = User.objects.get(username=usuario.usuario)
        django_user.password = make_password(new_password)
        django_user.save()

        return render(request, 'password_reset_complete.html')
    return render(request, 'password_reset_confirm.html', {'pk': pk})


## gym

def gimnasio_lista(request):
    gimnasios = Gimnasio.objects.all()
    return render(request, 'gimnasio_lista.html', {'gimnasios': gimnasios})

def gimnasio_crear(request):
    if request.method == 'POST':
        form = GimnasioForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('gimnasio_lista')
    else:
        form = GimnasioForm()
    return render(request, 'gimnasio_form.html', {'form': form, 'accion':'Crear'})

def gimnasio_editar(request, pk):
    gimnasio = get_object_or_404(Gimnasio, pk=pk)
    if request.method == 'POST':
        form = GimnasioForm(request.POST, instance=gimnasio)
        if form.is_valid():
            form.save()
            return redirect('gimnasio_lista')
    else:
        form = GimnasioForm(instance=gimnasio)
    return render(request, 'gimnasio_form.html', {'form': form, 'accion':'Editar'})

def gimnasio_eliminar(request, pk):
    gimnasio = get_object_or_404(Gimnasio, pk=pk)
    if request.method == 'POST':
        gimnasio.delete()
        return redirect('gimnasio_lista')
    return render(request, 'gimnasio_confirm_delete.html', {'gimnasio': gimnasio})

def gimnasio_detalle(request, pk):
    gimnasio = get_object_or_404(Gimnasio, pk=pk)
    return render(request, 'gimnasio_detalle.html', {'gimnasio': gimnasio})



##tipo de mensualidad 
def lista_tipos_mensualidad(request):
    tipos = TipoMensualidad.objects.all()
    return render(request, 'lista_tipos_mensualidad.html', {'tipos': tipos})

def crear_tipo_mensualidad(request):
    if request.method == 'POST':
        form = TipoMensualidadForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('lista_tipos_mensualidad') # Redirige a la vista lista_tipos_mensualidad
    else:
        form = TipoMensualidadForm()
    return render(request, 'crear_tipo_mensualidad.html', {'form': form})

def editar_tipo_mensualidad(request, pk):
    tipo = get_object_or_404(TipoMensualidad, pk=pk)
    if request.method == 'POST':
        form = TipoMensualidadForm(request.POST, instance=tipo)
        if form.is_valid():
            form.save()
            return redirect('lista_tipos_mensualidad') # Redirige a la vista lista_tipos_mensualidad
    else:
        form = TipoMensualidadForm(instance=tipo)
    return render(request, 'editar_tipo_mensualidad.html', {'form': form, 'tipo': tipo})

def eliminar_tipo_mensualidad(request, pk):
    tipo = get_object_or_404(TipoMensualidad, pk=pk)
    if request.method == 'POST':
        tipo.delete()
        return redirect('lista_tipos_mensualidad') # Redirige a la vista lista_tipos_mensualidad
    return render(request, 'eliminar_tipo_mensualidad.html', {'tipo': tipo})


##cuotas

@login_required
def asignar_mensualidad(request):
    socio_id = request.GET.get('socio')
    socio = None
    initial_data = {}
    mensualidad_actual = None

    if socio_id:
        socio = get_object_or_404(Socio, id=socio_id)
        initial_data['socio'] = f"{socio.nombre} {socio.apellido}"
        initial_data['socio_id'] = socio.id

        if socio.tipo_mensualidad:
            initial_data['tipo_mensualidad_display'] = str(socio.tipo_mensualidad)
            mensualidad_actual = socio.tipo_mensualidad
            
    if request.method == 'POST':
        form = AsignarMensualidadForm(request.POST, initial=initial_data)
        if form.is_valid():
            socio_id = form.initial.get('socio_id')
            socio = Socio.objects.get(pk=socio_id)
            tipo_mensualidad = form.cleaned_data['tipo_mensualidad']
            metodo_pago = form.cleaned_data['metodo_pago']
            monto = form.cleaned_data['monto']
            clases_restantes = form.cleaned_data.get('clases_restantes')

            # Actualizar clases restantes
            if clases_restantes is not None:
                socio.clases_restantes = clases_restantes

            # Obtener la última cuota (si existe)
            try:
                cuota_anterior = Cuota.objects.filter(socio=socio).latest('fecha_inicio')
            except Cuota.DoesNotExist:
                cuota_anterior = None
            
            # Eliminar la cuota anterior
            if cuota_anterior:
                cuota_anterior.delete()
            
            # Actualizar el tipo de mensualidad del socio
            if tipo_mensualidad:
                socio.tipo_mensualidad = tipo_mensualidad
            
            socio.save()

            # Crear la nueva cuota
            cuota = Cuota.objects.create(
                socio=socio,
                tipo_mensualidad=tipo_mensualidad,
                precio=monto,
                gimnasio=socio.gimnasio,
                fecha_inicio=date.today()
            )
            
            # Registrar el ingreso
            ingresos.objects.create(
              descripcion=f"Mensualidad de {socio.nombre} {socio.apellido}",
              monto=monto,
              tipo_ingreso=metodo_pago,
              fecha=date.today(),
              gimnasio = socio.gimnasio
            )

            if metodo_pago == "efectivo":
              cuota.efectivo = monto
            elif metodo_pago =="transferencia":
              cuota.transferencia = monto
            elif metodo_pago == "tarjeta_credito":
              cuota.tarjeta_credito = monto
            cuota.save()

            return redirect('lista_cuotas')
    else:
        form = AsignarMensualidadForm(initial=initial_data)

    return render(request, 'asignar_mensualidad.html', {'form': form, 'socio_id': socio_id})


@login_required
def lista_cuotas(request):
    socios = Socio.objects.all()
    cuotas_por_socio = []
    for socio in socios:
       try:
            cuota = Cuota.objects.filter(socio=socio).latest('fecha_inicio') # Obtenemos la última cuota
            fecha_vencimiento = cuota.fecha_inicio + timedelta(days=30) if cuota.fecha_inicio else None # calculamos el vencimiento
            cuotas_por_socio.append({'socio':socio, 'cuota': cuota, 'fecha_vencimiento': fecha_vencimiento})  # agregamos a la lista
       except Cuota.DoesNotExist:
            cuotas_por_socio.append({'socio':socio, 'cuota': None, 'fecha_vencimiento': None})
       except Cuota.MultipleObjectsReturned:
            cuota = Cuota.objects.filter(socio=socio).order_by('-fecha_inicio').first()
            fecha_vencimiento = cuota.fecha_inicio + timedelta(days=30) if cuota.fecha_inicio else None  # calculamos el vencimiento
            cuotas_por_socio.append({'socio': socio, 'cuota': cuota, 'fecha_vencimiento': fecha_vencimiento})  # agregamos a la lista

    return render(request, 'listar_cuotas.html', {'cuotas_por_socio': cuotas_por_socio})



@login_required
def renovar_mensualidad(request):
    socio_id = request.GET.get('socio')
    cuota_id = request.GET.get('cuota')
    socio = get_object_or_404(Socio, pk=socio_id)
    cuota = get_object_or_404(Cuota, pk=cuota_id, socio=socio)
    
    if request.method == 'GET' and 'confirmar_renovacion' in request.GET:
            nueva_fecha_inicio = cuota.fecha_inicio + timedelta(days=30)
            
            nueva_cuota = Cuota.objects.create(
                socio=socio,
                tipo_mensualidad=cuota.tipo_mensualidad,  # Mantener el mismo tipo de mensualidad
                precio=cuota.precio,
                gimnasio=cuota.gimnasio,
                fecha_inicio=nueva_fecha_inicio
            )
            if cuota.efectivo:
                nueva_cuota.efectivo = cuota.efectivo
            if cuota.transferencia:
                nueva_cuota.transferencia = cuota.transferencia
            if cuota.tarjeta_credito:
                nueva_cuota.tarjeta_credito = cuota.tarjeta_credito
            nueva_cuota.save()
            
            # Sumar 12 clases SI Y SOLO SI el tipo de mensualidad es "12 clases"
            # Se obtiene el id del tipo de mensualidad para comparar
            tipo_mensualidad_12_clases = TipoMensualidad.objects.get(tipo="12 clases")
            if cuota.tipo_mensualidad and cuota.tipo_mensualidad.id == tipo_mensualidad_12_clases.id:
                socio.clases_restantes = F('clases_restantes') + 12
                socio.save()
                
            # Registrar el ingreso
            ingresos.objects.create(
                descripcion=f"Renovación automática de mensualidad para {socio.nombre} {socio.apellido}, cuota {cuota.tipo_mensualidad}",
                monto=cuota.precio,
                tipo_ingreso="Renovación",
                fecha=date.today(),
                gimnasio=cuota.gimnasio
            )

            cuota.delete()
            return redirect(reverse('asignar_mensualidad') + f'?socio={socio_id}&cuota={nueva_cuota.id}')
        
    return render(request, 'renovar_mensualidad.html', {'socio': socio})


@login_required
def renovar_mensualidad_manual(request):
    socio_id = request.GET.get('socio')
    cuota_id = request.GET.get('cuota')
    socio = get_object_or_404(Socio, pk=socio_id)
    cuota = get_object_or_404(Cuota, pk=cuota_id, socio=socio)

    if request.method == 'POST':
        form = SeleccionarFechaRenovacionForm(request.POST)
        if form.is_valid():
           nueva_fecha_inicio = form.cleaned_data['fecha_renovacion']
           if cuota:
             nueva_cuota = Cuota.objects.create(
                 socio=socio,
                 tipo_mensualidad=cuota.tipo_mensualidad,
                 precio=cuota.precio,
                 gimnasio=cuota.gimnasio,
                 fecha_inicio=nueva_fecha_inicio
             )
             if cuota.efectivo:
              nueva_cuota.efectivo = cuota.efectivo
             if cuota.transferencia:
              nueva_cuota.transferencia = cuota.transferencia
             if cuota.tarjeta_credito:
              nueva_cuota.tarjeta_credito = cuota.tarjeta_credito
             nueva_cuota.save()
             
             # Sumar 12 clases si es tipo_mensualidad "12 clases"
             if cuota.tipo_mensualidad and cuota.tipo_mensualidad.tipo == "12 clases":
                socio.clases_restantes += 12
                socio.save()
             
             cuota.delete()
           return redirect(reverse('asignar_mensualidad') + f'?socio={socio_id}&cuota={nueva_cuota.id}')
    else:
        form = SeleccionarFechaRenovacionForm()
    return render(request, 'seleccionar_fecha_renovacion.html', {'form': form, 'socio': socio})



##PRODUCTOS

def producto_list(request):
    productos = Producto.objects.all()
    return render(request, 'producto_list.html', {'productos': productos})

def producto_crear(request):
    if request.method == 'POST':
        form = ProductoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('producto_list')
    else:
        form = ProductoForm()
    return render(request, 'producto_form.html', {'form': form})
def producto_editar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            form.save()
            return redirect('producto_list')
    else:
        form = ProductoForm(instance=producto)
    return render(request, 'producto_form.html', {'form': form})

def producto_eliminar(request, pk):
    producto = get_object_or_404(Producto, id=pk)
    if request.method == 'POST':
        producto.delete()
        return redirect('producto_list')  # Redirige a la lista después de eliminar
    return render(request, 'producto_confirmar_eliminar.html', {'producto': producto})


##venta

@login_required
def venta_list(request):
    ventas = Venta.objects.all()
    return render(request, 'venta_list.html', {'ventas': ventas})

@login_required
def venta_crear(request):
    if request.method == 'POST':
        form = VentaForm(request.POST)
        if form.is_valid():
            venta = form.save(commit=False)
            # Obtenemos el usuario de Django logueado
            django_user = request.user
            # Obtenemos nuestro usuario personalizado con el mismo nombre de usuario
            try:
                usuario_personalizado = Usuario.objects.get(usuario=django_user.username)
                venta.usuario = usuario_personalizado
                venta.gimnasio = form.cleaned_data['producto'].gimnasio
                venta.save()  # Guardar venta en la base de datos
                producto = venta.producto
                producto.cantidad -= venta.cantidad  # se modifica el stock del producto
                producto.save()  # se guarda la modificación del stock

                # --- CREACIÓN DEL INGRESO ---
                monto_ingreso = venta.cantidad * producto.precio  # Calcula el ingreso total de la venta
                ingreso = ingresos.objects.create(
                    descripcion=f'Venta de {producto.descripcion}',  # Ejemplo de descripción
                    monto=monto_ingreso,  # El monto total de la venta
                    tipo_ingreso='Venta',  # Puede ser 'Venta' o lo que corresponda
                    fecha=date.today(),  # La fecha actual
                    gimnasio=venta.gimnasio
                )

                return redirect('venta_list')
            except Usuario.DoesNotExist:
                # En caso de que no exista un Usuario personalizado asociado, puedes manejarlo aquí,
                # ya sea creando uno nuevo o mostrando un mensaje de error
                # Por ejemplo, aquí lo redirigimos a una pantalla de error
                return render(request, 'error/usuario_no_encontrado.html')  # Redirigir a una plantilla de error.
    else:
        form = VentaForm()
    return render(request, 'venta_form.html', {'form': form})

def producto_precio(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    return JsonResponse({'precio': producto.precio})


## extras

def extras_list(request):
    extras_lista = extras.objects.all()
    return render(request, 'extras_list.html', {'extras_lista': extras_lista})

def extras_create(request):
    if request.method == 'POST':
        form = ExtrasForm(request.POST)
        if form.is_valid():
            tipo = form.cleaned_data['tipo']
            descripcion = form.cleaned_data['descripcion']
            monto = form.cleaned_data['monto']
            fecha = form.cleaned_data['fecha']
            gimnasio_id = form.cleaned_data['gimnasio']
            producto = form.cleaned_data.get('producto') # Obtenemos el producto seleccionado del formulario

            with transaction.atomic(): # Transaccion atomica, para que no se modifique un valor si falla otro
                if tipo == 'ingreso':
                    ingreso = ingresos.objects.create(
                        descripcion=descripcion,
                        monto=monto,
                        tipo_ingreso='extra',
                        fecha=fecha,
                        gimnasio=gimnasio_id
                    )
                    extra_obj = extras.objects.create(
                        ingreso = ingreso,
                        descripcion=descripcion,
                        monto=monto,
                        fecha=fecha,
                        gimnasio=gimnasio_id,
                        producto = producto if producto else None

                    )
                    messages.success(request, 'Ingreso extra creado correctamente.')
                elif tipo == 'egreso':
                    egreso_obj = egreso.objects.create(
                        descripcion=descripcion,
                        monto=monto,
                        tipo_ingreso='extra',
                        fecha=fecha,
                        gimnasio = gimnasio_id
                    )

                    extra_obj = extras.objects.create(
                        egreso = egreso_obj,
                        descripcion=descripcion,
                        monto=monto,
                        fecha=fecha,
                        gimnasio=gimnasio_id,
                        producto=producto if producto else None
                    )

                    messages.success(request, 'Egreso extra creado correctamente.')

                if producto:
                    if tipo == 'egreso':
                        if producto.cantidad >= 1:
                            producto.cantidad -= 1
                            producto.save()
                            messages.success(request, 'cantidad descontado correctamente.')
                        else:
                            messages.error(request, 'No hay suficiente cantidad para descontar')
                    elif tipo == 'ingreso':
                        producto.cantidad += 1
                        producto.save()
                        messages.success(request, 'cantidad sumado correctamente')

            return redirect('extras_list')


    else:
        form = ExtrasForm()
    return render(request, 'extras_form.html', {'form': form, 'title': 'Crear Extra'})

def extras_update(request, pk):
    extra = get_object_or_404(extras, pk=pk)
    if request.method == 'POST':
        form = ExtrasForm(request.POST, instance=extra)
        if form.is_valid():
            form.save()
            messages.success(request, 'Extra actualizado correctamente.')
            return redirect('extras_list')
    else:
        form = ExtrasForm(instance=extra)
    return render(request, 'extras_form.html', {'form': form, 'title': 'Editar Extra'})


def extras_delete(request, pk):
    extra = get_object_or_404(extras, pk=pk)
    if request.method == 'POST':
        extra.delete()
        messages.success(request, 'Extra eliminado correctamente.')
        return redirect('extras_list')
    return render(request, 'extras_confirm_delete.html', {'extra': extra})



## caja diaria 

def balance_diario(request):
    if request.method == 'POST':
        form = SeleccionGimnasioForm(request.POST)
        if form.is_valid():
            gimnasio_seleccionado = form.cleaned_data['gimnasio']
            return redirect('mostrar_balance', gimnasio_id=gimnasio_seleccionado.id)
    else:
        form = SeleccionGimnasioForm()
    return render(request, 'seleccionar_gimnasio.html', {'form': form})


def mostrar_balance(request, gimnasio_id):
    try:
        hoy = date.today()
        ingresos_hoy = ingresos.objects.filter(gimnasio_id=gimnasio_id, fecha=hoy)
        egresos_hoy = egreso.objects.filter(gimnasio_id=gimnasio_id, fecha=hoy)

        total_ingresos = sum(ingreso.monto for ingreso in ingresos_hoy if ingreso.monto)
        total_egresos = sum(egreso.monto for egreso in egresos_hoy if egreso.monto)
        balance = total_ingresos - total_egresos
        
        # Obtener el gimnasio directamente desde el ID
        try:
             gimnasio_seleccionado = Gimnasio.objects.get(id=gimnasio_id)
             gimnasio_nombre = gimnasio_seleccionado.direccion
        except Gimnasio.DoesNotExist:
             gimnasio_seleccionado = None
             gimnasio_nombre = None
        
        # Guardar el balance diario (con `get_or_create` y manejo de update)
        if gimnasio_seleccionado:
            balance_diario, created = BalanceDiario.objects.get_or_create(
                gimnasio=gimnasio_seleccionado,
                fecha=hoy,
                defaults={'total_ingresos': total_ingresos,
                          'total_egresos': total_egresos,
                          'balance': balance}
            )
            if not created:
                balance_diario.total_ingresos = total_ingresos
                balance_diario.total_egresos = total_egresos
                balance_diario.balance = balance
                balance_diario.save()

        context = {
            'gimnasio_id': gimnasio_id,
            'gimnasio_nombre': gimnasio_nombre,
            'ingresos': ingresos_hoy,
            'egresos': egresos_hoy,
            'total_ingresos': total_ingresos,
            'total_egresos': total_egresos,
            'balance': balance,
            'fecha': hoy,
        }
        return render(request, 'mostrar_balance.html', context)
    except Exception as e:
        print(e)
        return render(request, 'error.html',{'error':e})


def historial_balances(request):
    balances = BalanceDiario.objects.all().order_by('-fecha')
    
    # Agrupar balances por gimnasio, mes y año
    grouped_balances = {}
    for balance in balances:
        key = (balance.gimnasio.direccion, balance.fecha.year, balance.fecha.month)
        if key not in grouped_balances:
            grouped_balances[key] = []
        grouped_balances[key].append(balance)

    gimnasios_con_historial = [balance.gimnasio for balance in balances]
    
    
    all_gimnasios = Gimnasio.objects.all()
    context = {
        'grouped_balances': grouped_balances,
        'gimnasios_con_historial': gimnasios_con_historial,
        'all_gimnasios' : all_gimnasios,
    }

    return render(request, 'historial_balances.html', context)


def detalle_balance(request, balance_id):
    balance = get_object_or_404(BalanceDiario, id=balance_id)
    
    ingresos_hoy = ingresos.objects.filter(gimnasio=balance.gimnasio, fecha=balance.fecha)
    egresos_hoy = egreso.objects.filter(gimnasio=balance.gimnasio, fecha=balance.fecha)
    
    context = {
        'balance': balance,
        'ingresos': ingresos_hoy,
        'egresos': egresos_hoy,
    }
    return render(request, 'detalle_balance.html', context)




##lista de ingresos

def listado_ingresos_diarios(request):
    fecha = request.GET.get('fecha', date.today().isoformat())
    registros_ingreso = RegistroIngreso.objects.filter(fecha_ingreso__date=fecha).order_by('-fecha_ingreso')
    ingresos_con_socio = []

    for registro in registros_ingreso:
        try:
            socio = Socio.objects.get(dni=registro.dni_socio)
            try:
                ultima_cuota = Cuota.objects.filter(socio=socio).latest('fecha_inicio')
                fecha_vencimiento = ultima_cuota.fecha_inicio + timedelta(days=30)
            except Cuota.DoesNotExist:
                fecha_vencimiento = None
            
            ingresos_con_socio.append({
                'nombre': registro.nombre_socio,
                'apellido': registro.apellido_socio,
                'dni': registro.dni_socio, # DNI agregado aquí
                'fecha_ingreso': registro.fecha_ingreso,
                'fecha_vencimiento': fecha_vencimiento,
                'clases_restantes': registro.clases_restantes_al_ingresar, #Obtenemos las clases restantes del registro.
                'tipo_mensualidad': socio.tipo_mensualidad.tipo if socio.tipo_mensualidad else 'Sin mensualidad',
            })
            print(f"Clases restantes de {registro.nombre_socio} {registro.apellido_socio}: {registro.clases_restantes_al_ingresar}")
        except Socio.DoesNotExist:
            ingresos_con_socio.append({
                'nombre': registro.nombre_socio,
                'apellido': registro.apellido_socio,
                'dni': registro.dni_socio,
                'fecha_ingreso': registro.fecha_ingreso,
                'fecha_vencimiento': None,
                'clases_restantes': registro.clases_restantes_al_ingresar,
                 'tipo_mensualidad': 'Socio no encontrado',
                
            })
            print(f"Socio no encontrado con DNI: {registro.dni_socio}")
        except Exception as e:
             ingresos_con_socio.append({
                'nombre': registro.nombre_socio,
                'apellido': registro.apellido_socio,
                'dni': registro.dni_socio,
                'fecha_ingreso': registro.fecha_ingreso,
                'fecha_vencimiento': None,
                'clases_restantes': registro.clases_restantes_al_ingresar,
                 'tipo_mensualidad': 'Error al obtener mensualidad',
             })
             print(f"Error al procesar registro de ingreso: {e}")

    context = {'ingresos': ingresos_con_socio, 'fecha': fecha}
    return render(request, 'listado_ingresos.html', context)

def historial_ingresos(request):
    form = HistorialIngresosForm(request.GET)
    fecha_inicio = None
    fecha_fin= None
    if form.is_valid():
         fecha_inicio = form.cleaned_data.get('fecha_inicio')
         fecha_fin = form.cleaned_data.get('fecha_fin')

    if fecha_inicio and fecha_fin:
        registros = RegistroIngreso.objects.filter(fecha_ingreso__date__gte=fecha_inicio,fecha_ingreso__date__lte=fecha_fin).annotate(fecha_truncada=TruncDate('fecha_ingreso')).values('fecha_truncada').annotate(cantidad=Count('id')).order_by('-fecha_truncada')
    else:
        registros = RegistroIngreso.objects.all().annotate(fecha_truncada=TruncDate('fecha_ingreso')).values('fecha_truncada').annotate(cantidad=Count('id')).order_by('-fecha_truncada')
   
    ingresos_por_fecha = {item['fecha_truncada']: item['cantidad'] for item in registros}

    context = {
        'ingresos_por_fecha': ingresos_por_fecha,
        'form': form,
        'fecha_inicio': fecha_inicio.strftime('%Y-%m-%d') if fecha_inicio else None,
        'fecha_fin':fecha_fin.strftime('%Y-%m-%d') if fecha_fin else None,
    }

    return render(request, 'historial_ingresos.html', context)

def detalle_ingresos_dia(request, fecha):
    registros_ingreso = RegistroIngreso.objects.filter(fecha_ingreso__date=fecha).order_by('-fecha_ingreso')
    ingresos_con_socio = []

    for registro in registros_ingreso:
        try:
            socio = Socio.objects.get(dni=registro.dni_socio)
            try:
                ultima_cuota = Cuota.objects.filter(socio=socio).latest('fecha_inicio')
                fecha_vencimiento = ultima_cuota.fecha_inicio + timedelta(days=30)
            except Cuota.DoesNotExist:
                fecha_vencimiento = None
            
            ingresos_con_socio.append({
                'nombre': registro.nombre_socio,
                'apellido': registro.apellido_socio,
                'dni': registro.dni_socio,
                'fecha_ingreso': registro.fecha_ingreso,
                'fecha_vencimiento': fecha_vencimiento,
                'clases_restantes': registro.clases_restantes_al_ingresar,
                 'tipo_mensualidad': socio.tipo_mensualidad.tipo if socio.tipo_mensualidad else 'Sin mensualidad',
            })
        except Socio.DoesNotExist:
              ingresos_con_socio.append({
                'nombre': registro.nombre_socio,
                'apellido': registro.apellido_socio,
                'dni': registro.dni_socio,
                'fecha_ingreso': registro.fecha_ingreso,
                'fecha_vencimiento': None,
                'clases_restantes': registro.clases_restantes_al_ingresar,
                 'tipo_mensualidad': 'Socio no encontrado',
            })
        except Exception as e:
             ingresos_con_socio.append({
                'nombre': registro.nombre_socio,
                'apellido': registro.apellido_socio,
                'dni': registro.dni_socio,
                'fecha_ingreso': registro.fecha_ingreso,
                'fecha_vencimiento': None,
                'clases_restantes': registro.clases_restantes_al_ingresar,
                 'tipo_mensualidad': 'Error al obtener mensualidad',
             })


    context = {
        'ingresos': ingresos_con_socio,
        'fecha': fecha,
    }
    return render(request, 'detalle_ingresos_dia.html', context)


    
@csrf_exempt
def api_socios(request, socio_id=None):
    if request.method == 'GET':
        socios = Socio.objects.all()
        data = []
        for socio in socios:
            tipo_mensualidad = None
            if socio.tipo_mensualidad:
                tipo_mensualidad = {'tipo': socio.tipo_mensualidad.tipo}
            data.append({
                'id': socio.id,
                'dni': socio.dni,
                'nombre': socio.nombre,
                'apellido': socio.apellido,
                'tipo_mensualidad': tipo_mensualidad,
                'clases_restantes': socio.clases_restantes,
                'fecha_vencimiento' : socio.fecha_vencimiento
            })
        return JsonResponse(data, safe=False)
    elif request.method == 'PATCH':
        try:
            if socio_id is not None:
                  socio = get_object_or_404(Socio, pk=socio_id)
                  data = json.loads(request.body)
                  clases_restantes = data.get('clases_restantes')
                  if clases_restantes is not None:
                     socio.clases_restantes = clases_restantes
                     socio.save()
                     tipo_mensualidad = None
                     if socio.tipo_mensualidad:
                          tipo_mensualidad = {'tipo': socio.tipo_mensualidad.tipo}
                     response_data = {
                         'id': socio.id,
                         'dni': socio.dni,
                         'nombre': socio.nombre,
                         'apellido': socio.apellido,
                         'tipo_mensualidad': tipo_mensualidad,
                         'clases_restantes': socio.clases_restantes,
                         'fecha_vencimiento': socio.fecha_vencimiento
                    }
                     return JsonResponse(response_data, status=200)
                  else:
                       return JsonResponse({'error': 'clases_restantes es un campo requerido'}, status=400)
            else:
                   return JsonResponse({'error': 'id es un campo requerido'}, status=400)
        except json.JSONDecodeError:
             return JsonResponse({'error': 'JSON invalido'}, status=400)
        return JsonResponse({'error': 'Metodo no permitido'}, status=405)
   
@csrf_exempt
def registrar_ingreso(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            dni_socio = data.get('dni_socio')
            fecha_ingreso = data.get('fecha_ingreso')
            clases_restantes_al_ingresar = data.get('clases_restantes_al_ingresar')
            nombre_socio = data.get('nombre_socio')
            apellido_socio = data.get('apellido_socio')
            
            if dni_socio and fecha_ingreso and clases_restantes_al_ingresar is not None and nombre_socio and apellido_socio :
              
                RegistroIngreso.objects.create(dni_socio=dni_socio, 
                                              fecha_ingreso=fecha_ingreso,
                                              clases_restantes_al_ingresar=clases_restantes_al_ingresar,
                                              nombre_socio=nombre_socio,
                                              apellido_socio=apellido_socio
                                              )
                return JsonResponse({'message': 'Ingreso registrado correctamente'}, status=201)
            else:
                 return JsonResponse({'error': 'dni_socio, fecha_ingreso, clases_restantes_al_ingresar, nombre_socio y apellido_socio son requeridos'}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON invalido'}, status=400)
    return JsonResponse({'error': 'Metodo no permitido'}, status=405)