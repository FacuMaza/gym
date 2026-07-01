from django import forms as django_forms
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.hashers import check_password
from django.contrib.auth.hashers import make_password
from django.contrib.auth import login, logout,authenticate
from django.urls import reverse
from datetime import date, datetime, timedelta
from django.http import JsonResponse
from django.http import HttpResponseForbidden
from django.contrib import messages
from django.db import transaction
from django.db.models import F
import json
import math
from django.db.models import Count, Exists, OuterRef, Q, Subquery, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone as tz
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from .models import *
from .forms import *
from .twilio_utils import send_sms, send_whatsapp, send_email
from django.db.models import Sum
from .context_processors import gimnasio_context
from django.utils import timezone as tz


def get_gimnasio_actual(request):
    """Obtiene el gimnasio actual de la sesión. Si no hay, None (superuser ve todo hasta que filtre)."""
    from .context_processors import gimnasio_context
    ctx = gimnasio_context(request)
    return ctx.get('gimnasio_actual')


def get_usuario_actual(request):
    """Obtiene el Usuario (modelo) del request.user. Para superuser crea/obtiene uno."""
    if request.user.is_superuser:
        admin_tipo = TipoUsuario.objects.filter(tipousuario='admin').first() or TipoUsuario.objects.first()
        u, _ = Usuario.objects.get_or_create(usuario=request.user.username, defaults={'tipo_usuario': admin_tipo, 'contrasena': request.user.password})
        return u
    return Usuario.objects.filter(usuario=request.user.username).first()


def get_caja_abierta(gym):
    """Retorna la caja abierta para el gimnasio, o None si no hay."""
    if not gym:
        return None
    return Caja.objects.filter(gimnasio=gym, fecha_cierre__isnull=True).select_related('usuario_apertura').first()


def usuario_puede_operar_caja(request, caja):
    """True si es super usuario, o si el usuario logueado abrió la caja."""
    if request.user.is_superuser:
        return True
    if not caja:
        return False
    usuario = get_usuario_actual(request)
    return bool(usuario and caja.usuario_apertura_id == usuario.id)


def calcular_totales_caja(caja):
    """Totales de ingresos/egresos de una sesión de caja."""
    ing_qs = ingresos.objects.filter(caja=caja).exclude(tipo_ingreso='Pago profesor')
    egr_qs = egreso.objects.filter(caja=caja)
    gast_qs = Gasto.objects.filter(caja=caja)
    ti = sum(i.monto for i in ing_qs if i.monto)
    te = sum(e.monto for e in egr_qs if e.monto) + sum(g.monto for g in gast_qs if g.monto)
    return ti, te, ti - te


def movimientos_caja_abierta(caja):
    """Querysets de movimientos de la sesión de caja actual."""
    if not caja:
        return {
            'ingresos': ingresos.objects.none(),
            'egresos': egreso.objects.none(),
            'gastos': Gasto.objects.none(),
            'cuotas': Cuota.objects.none(),
            'ventas': Venta.objects.none(),
            'ventas_profesores': Venta.objects.none(),
            'pagos_profesor': PagoProfesor.objects.none(),
        }
    return {
        'ingresos': ingresos.objects.filter(caja=caja).exclude(tipo_ingreso='Pago profesor'),
        'egresos': egreso.objects.filter(caja=caja),
        'gastos': Gasto.objects.filter(caja=caja),
        'cuotas': Cuota.objects.filter(caja=caja).select_related('socio', 'tipo_mensualidad'),
        'ventas': Venta.objects.filter(caja=caja, profesor__isnull=True).select_related('producto', 'usuario'),
        'ventas_profesores': Venta.objects.filter(caja=caja).exclude(profesor__isnull=True).select_related('producto', 'profesor', 'usuario'),
        'pagos_profesor': PagoProfesor.objects.filter(caja=caja).select_related('profesor'),
    }


def requiere_caja_abierta(view_func):
    """Decorador: exige caja abierta y que la haya abierto el usuario actual."""
    from functools import wraps
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        gym = get_gimnasio_actual(request)
        if not gym:
            messages.warning(request, 'Seleccioná un gimnasio primero.')
            return redirect('index')
        caja = get_caja_abierta(gym)
        if not caja:
            messages.warning(request, 'Debés abrir la caja antes de realizar ventas o movimientos de dinero. Andá a Caja Diaria.')
            return redirect('balance_diario')
        if not usuario_puede_operar_caja(request, caja):
            dueno = caja.usuario_apertura.usuario if caja.usuario_apertura else 'otro usuario'
            messages.error(
                request,
                f'Solo {dueno} puede vender y registrar movimientos mientras su caja esté abierta.'
            )
            return redirect('balance_diario')
        return view_func(request, *args, **kwargs)
    return _wrapped


@login_required
def set_gimnasio_actual(request, gimnasio_id):
    """Establece el gimnasio actual en sesión y redirige a index."""
    gym = get_object_or_404(Gimnasio, pk=gimnasio_id)
    request.session['gimnasio_actual_id'] = gym.id
    next_url = request.GET.get('next', reverse('index'))
    return redirect(next_url)


# Create your views here.

@never_cache
def login_view(request):
    gym_id = request.GET.get('gym') or request.POST.get('gym')
    if request.user.is_authenticated:
        if Socio.objects.filter(auth_user=request.user).exists():
            return redirect('socio_portal')
        return redirect('index')
    error = None
    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        password = request.POST.get('password') or ''
        user = authenticate(request, username=username, password=password)

        if user is not None:
            if EstadoAccesoSistema.get_estado().pausado and not user.is_superuser:
                return redirect('sistema_pausado')
            if Socio.objects.filter(auth_user=user).exists():
                login(request, user)
                return redirect('socio_portal')
            login(request, user)

            # Establecer el tipo de usuario en la sesión: super_usuario, admin, empleado
            if user.is_superuser:
                request.session['tipo_usuario'] = 'super_usuario'
            else:
                try:
                    usuario_modelo = Usuario.objects.get(usuario=username)
                    request.session['tipo_usuario'] = usuario_modelo.tipo_usuario.tipousuario
                    # Asignar gimnasio actual: si tiene gyms asignados, llevar al primero
                    primero = UsuarioGimnasio.objects.filter(usuario=usuario_modelo).select_related('gimnasio').first()
                    if primero:
                        request.session['gimnasio_actual_id'] = primero.gimnasio_id
                except Usuario.DoesNotExist:
                    request.session['tipo_usuario'] = 'miembro'  # Valor por defecto si no existe en la tabla Usuario

            # Obtener el parámetro 'next' de la URL
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            else:
                return redirect('index')
        else:
            qs = Socio.objects.filter(dni=username).select_related('auth_user')
            if gym_id:
                qs = qs.filter(gimnasio_id=gym_id)
            socio = qs.first()
            if socio and socio.auth_user and socio.auth_user.check_password(password):
                if EstadoAccesoSistema.get_estado().pausado:
                    return redirect('sistema_pausado')
                login(request, socio.auth_user)
                return redirect('socio_portal')
            error = 'Usuario o contraseña incorrecta'
    return render(request, 'login.html', {'error': error, 'gym_id': gym_id})


def logout_view(request):
    logout(request)
    return redirect('login')


def sistema_pausado(request):
    return render(request, 'sistema_pausado.html')


@login_required
@require_POST
def toggle_sistema_pausa(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden()
    estado = EstadoAccesoSistema.get_estado()
    estado.pausado = not estado.pausado
    if estado.pausado:
        estado.pausado_en = tz.now()
        estado.pausado_por = request.user
        estado.pausado_por_vencimiento = False
        messages.warning(request, 'Sistema pausado. Solo Super Usuario puede ingresar.')
    else:
        estado.pausado_en = None
        estado.pausado_por = None
        estado.pausado_por_vencimiento = False
        messages.success(request, 'Sistema despausado. Todos pueden ingresar con normalidad.')
    estado.save()
    return redirect(request.POST.get('next') or request.META.get('HTTP_REFERER') or reverse('index'))


@login_required
@require_POST
def marcar_sistema_pagado(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden()
    from .sistema_vencimiento import (
        referencia_periodo,
        periodos_pagados_set,
        _periodo_key,
        debe_pausar_por_vencimiento,
    )
    estado = EstadoAccesoSistema.get_estado()
    ref = referencia_periodo()
    pagados = periodos_pagados_set(estado.periodos_pagados)
    pagados.add(_periodo_key(ref))
    estado.periodos_pagados = ','.join(sorted(pagados))
    if not debe_pausar_por_vencimiento(estado.periodos_pagados) and estado.pausado_por_vencimiento:
        estado.pausado = False
        estado.pausado_por_vencimiento = False
        estado.pausado_en = None
        estado.pausado_por = None
        messages.success(request, 'Pago registrado. Sistema despausado.')
    else:
        messages.success(request, f'Pago registrado para {ref.strftime("%m/%Y")}.')
    estado.save()
    return redirect(request.POST.get('next') or request.META.get('HTTP_REFERER') or reverse('index'))


@login_required
def index(request):
    if Socio.objects.filter(auth_user=request.user).exists():
        return redirect('socio_portal')
    usuario = request.user.username
    tipo_usuario_valor = None # Inicializar la variable

    if request.user.is_superuser:
        tipo_usuario_valor = 'super_usuario'
    elif request.user.groups.filter(name='empleado').exists():
        tipo_usuario_valor = 'empleado'
    else:
        # Intenta obtener el tipo de usuario de tu modelo Usuario
        try:
            usuario_obj = Usuario.objects.get(usuario=request.user.username)
            tipo_usuario_valor = usuario_obj.tipo_usuario.tipousuario  # Obtén el valor del campo tipousuario
        except Usuario.DoesNotExist:
            tipo_usuario_valor = 'miembro'

    request.session['tipo_usuario'] = tipo_usuario_valor
    gym = get_gimnasio_actual(request)

    if tipo_usuario_valor == 'empleado':
        socios = Socio.objects.filter(gimnasio=gym).order_by('apellido', 'nombre') if gym else []
        hoy = date.today()
        proximos_vencer = []
        for s in socios:
            fv = s.fecha_vencimiento
            if fv:
                dias = (fv - hoy).days
                if dias <= 5:
                    if dias < 0:
                        alerta = 'vencido'
                    elif dias <= 1:
                        alerta = 'rojo'
                    else:
                        alerta = 'amarillo'
                    proximos_vencer.append({'socio': s, 'dias': dias, 'alerta': alerta})
        proximos_vencer.sort(key=lambda x: x['dias'])
        return render(request, 'index_empleado.html', {
            'usuario': usuario, 'socios': socios, 'proximos_vencer': proximos_vencer, 'gimnasio_actual': gym,
        })

    gimnasios = list(gimnasio_context(request).get('gimnasios_disponibles', []))
    if not gimnasios:
        gimnasios = list(Gimnasio.objects.all().order_by('nombre', 'direccion'))

    return render(request, 'index.html', {
        'usuario': usuario,
        'tipo_usuario': tipo_usuario_valor,
        'gimnasios': gimnasios
    })


##SOCIOS

def _conteo_socios_por_categoria(socios_qs):
    filas = (
        socios_qs.values('tipo_mensualidad__categoria__id', 'tipo_mensualidad__categoria__nombre')
        .annotate(cantidad=Count('pk'))
        .order_by('tipo_mensualidad__categoria__nombre')
    )
    por_categoria = []
    sin_categoria = 0
    for fila in filas:
        if fila['tipo_mensualidad__categoria__id'] is None:
            sin_categoria = fila['cantidad']
        else:
            por_categoria.append({
                'id': fila['tipo_mensualidad__categoria__id'],
                'nombre': fila['tipo_mensualidad__categoria__nombre'],
                'cantidad': fila['cantidad'],
            })
    return por_categoria, sin_categoria


def _conteo_ingresos_por_categoria(ingresos):
    por_categoria = {}
    sin_categoria = 0
    for ingreso in ingresos:
        cat_id = ingreso.get('categoria_id')
        if cat_id is None:
            sin_categoria += 1
        else:
            nombre = ingreso.get('categoria') or '-'
            por_categoria[nombre] = por_categoria.get(nombre, 0) + 1
    conteo = [{'nombre': k, 'cantidad': v} for k, v in sorted(por_categoria.items(), key=lambda x: x[0].lower())]
    return conteo, sin_categoria


@login_required
def lista_socios(request):
    gym = get_gimnasio_actual(request)
    q_buscar = (request.GET.get('q') or '').strip()
    categoria_filtro = (request.GET.get('categoria') or '').strip()
    if gym:
        ultima_cuota_subq = Cuota.objects.filter(socio=OuterRef('pk')).order_by('-fecha_inicio')
        socios_base = Socio.objects.filter(gimnasio=gym).select_related(
            'tipo_mensualidad', 'tipo_mensualidad__categoria',
        ).annotate(
            tiene_cuota=Exists(Cuota.objects.filter(socio=OuterRef('pk'))),
            fecha_inicio_cuota=Subquery(ultima_cuota_subq.values('fecha_inicio')[:1]),
        )
        total_socios_gym = socios_base.count()
        conteo_por_categoria, conteo_sin_categoria = _conteo_socios_por_categoria(socios_base)
        categorias_filtro = CategoriaMensualidad.objects.filter(gimnasio=gym).order_by('nombre')
        socios = socios_base.order_by('apellido', 'nombre')
        if q_buscar:
            q_filtro = Q()
            for term in q_buscar.split():
                q_filtro &= (Q(nombre__icontains=term) | Q(apellido__icontains=term) | Q(dni__icontains=term))
            socios = socios.filter(q_filtro)
        if categoria_filtro == 'sin':
            socios = socios.filter(tipo_mensualidad__categoria__isnull=True)
        elif categoria_filtro.isdigit():
            socios = socios.filter(tipo_mensualidad__categoria_id=int(categoria_filtro))
    else:
        socios = Socio.objects.none()
        total_socios_gym = 0
        conteo_por_categoria = []
        conteo_sin_categoria = 0
        categorias_filtro = CategoriaMensualidad.objects.none()
    try:
        nuevo_id = int(request.GET.get('nuevo')) if request.GET.get('nuevo') else None
    except (ValueError, TypeError):
        nuevo_id = None
    return render(request, 'lista_socios.html', {
        'socios': socios,
        'socio_nuevo_id': nuevo_id,
        'q_buscar': q_buscar,
        'categoria_filtro': categoria_filtro,
        'categorias_filtro': categorias_filtro,
        'total_socios_gym': total_socios_gym,
        'conteo_por_categoria': conteo_por_categoria,
        'conteo_sin_categoria': conteo_sin_categoria,
    })


@login_required
def crear_socio(request):
    # Superusuarios no están en Usuario: creamos/obtenemos uno para que puedan crear socios
    if request.user.is_superuser:
        admin_tipo = TipoUsuario.objects.filter(tipousuario='admin').first() or TipoUsuario.objects.first()
        current_user, _ = Usuario.objects.get_or_create(
            usuario=request.user.username,
            defaults={'tipo_usuario': admin_tipo, 'contrasena': request.user.password}
        )
    else:
        current_user = Usuario.objects.filter(usuario=request.user.username).first()
    gym = get_gimnasio_actual(request)
    if not gym:
        return redirect('gimnasio_lista')

    if request.method == 'POST':
        form = SocioForm(request.POST, gimnasio=gym)
        if form.is_valid() and current_user:
            nuevo_socio = form.save(commit=False)
            nuevo_socio.usuario = current_user
            nuevo_socio.gimnasio = gym
            # No asignar clases ni vencimiento: eso se hace solo cuando PAGA (cobrar_mensualidad)
            nuevo_socio.clases_restantes = 0
            nuevo_socio.fecha_vencimiento = None
            nuevo_socio.save()
            from .socio_portal_utils import crear_o_actualizar_cuenta_socio
            crear_o_actualizar_cuenta_socio(nuevo_socio)
            return redirect('cobrar_mensualidad', socio_id=nuevo_socio.id)
        elif not current_user:
            form = SocioForm(request.POST, gimnasio=gym)
            form.add_error(None, 'El usuario actual no está registrado.')
    else:
        form = SocioForm(gimnasio=gym)
    return render(request, 'crear_socio.html', {'form': form, 'current_user': current_user, 'gimnasio_actual': gym})


@login_required
def editar_socio(request, pk):
    gym = get_gimnasio_actual(request)
    socio = get_object_or_404(Socio, pk=pk, gimnasio=gym) if gym else get_object_or_404(Socio, pk=pk)
    if request.method == 'POST':
        form = SocioForm(request.POST, instance=socio, gimnasio=gym)
        if form.is_valid():
            socio = form.save()
            from .socio_portal_utils import crear_o_actualizar_cuenta_socio
            crear_o_actualizar_cuenta_socio(socio)
            return redirect('lista_socios')
    else:
        form = SocioForm(instance=socio, gimnasio=gym)
    return render(request, 'editar_socio.html', {'form': form, 'socio': socio})

@login_required
def eliminar_socio(request, pk):
    gym = get_gimnasio_actual(request)
    socio = get_object_or_404(Socio, pk=pk, gimnasio=gym) if gym else get_object_or_404(Socio, pk=pk)
    
    if request.method == 'POST':
        socio.delete()
        return redirect('lista_socios')
    return render(request, 'eliminar_socio.html', {'socio': socio})

@login_required
def detalle_socio(request, pk):
    gym = get_gimnasio_actual(request)
    socio = get_object_or_404(Socio, pk=pk, gimnasio=gym) if gym else get_object_or_404(Socio, pk=pk)
    ultima_cuota = Cuota.objects.filter(socio=socio).order_by('-id').first()
    return render(request, 'detalle_socio.html', {'socio': socio, 'ultima_cuota': ultima_cuota})


@login_required
def enviar_mensaje_socio(request, pk):
    """
    Envía un mensaje a un socio por SMS, WhatsApp o Email usando Twilio/utilidades de correo.
    """
    gym = get_gimnasio_actual(request)
    socio = get_object_or_404(Socio, pk=pk, gimnasio=gym) if gym else get_object_or_404(Socio, pk=pk)

    if request.method == "POST":
        canal = request.POST.get("canal")
        mensaje = (request.POST.get("mensaje") or "").strip()
        email_destino = (request.POST.get("email") or "").strip()
        ok = False

        if mensaje:
            if canal == "sms":
                ok = send_sms(socio.celular or "", mensaje)
            elif canal == "whatsapp":
                ok = send_whatsapp(socio.celular or "", mensaje)
            elif canal == "email":
                ok = send_email(email_destino, "Mensaje del gimnasio", mensaje)

        if ok:
            messages.success(request, "Mensaje enviado correctamente.")
        else:
            messages.error(request, "No se pudo enviar el mensaje. Verificá el canal, número/email y la configuración de Twilio/Email.")
        return redirect("detalle_socio", pk=socio.pk)

    return render(request, "enviar_mensaje_socio.html", {"socio": socio})

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

@login_required
def usuario_create(request):
    if request.method == 'POST':
        form = UsuarioForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('usuario_list')
    else:
        form = UsuarioForm()
    return render(request, 'usuario_form.html', {'form': form})

@login_required
def usuario_list(request):
    # Super usuarios (Django): se muestran pero no son editables/eliminables
    superusers = list(User.objects.filter(is_superuser=True).order_by('username'))
    superuser_usernames = {u.username for u in superusers}
    usuarios = list(Usuario.objects.exclude(usuario__in=superuser_usernames)
        .select_related('tipo_usuario').prefetch_related('gimnasios_asignados__gimnasio').order_by('usuario'))
    return render(request, 'usuario_list.html', {
        'usuarios': usuarios,
        'superusers': superusers,
    })


@login_required
def usuario_update(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    if User.objects.filter(username=usuario.usuario, is_superuser=True).exists():
        messages.error(request, 'No se puede editar la cuenta super usuario.')
        return redirect('usuario_list')
    if request.method == 'POST':
        form = UsuarioForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            return redirect('usuario_list')
    else:
        form = UsuarioForm(instance=usuario)
    return render(request, 'usuario_form.html', {'form': form})

@login_required
def usuario_delete(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    if User.objects.filter(username=usuario.usuario, is_superuser=True).exists():
        messages.error(request, 'No se puede eliminar la cuenta super usuario.')
        return redirect('usuario_list')
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

@login_required
def gimnasio_lista(request):
    gimnasios = Gimnasio.objects.all()
    return render(request, 'gimnasio_lista.html', {'gimnasios': gimnasios})

@login_required
def gimnasio_crear(request):
    if request.method == 'POST':
        form = GimnasioForm(request.POST)
        if form.is_valid():
            gym = form.save()
            for u in Usuario.objects.all():
                UsuarioGimnasio.objects.get_or_create(usuario=u, gimnasio=gym)
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
@login_required
def lista_tipos_mensualidad(request):
    gym = get_gimnasio_actual(request)
    categorias = CategoriaMensualidad.objects.filter(gimnasio=gym).order_by('nombre') if gym else CategoriaMensualidad.objects.none()
    return render(request, 'lista_tipos_mensualidad.html', {'categorias': categorias})

@login_required
def crear_plan_mensualidad(request):
    gym = get_gimnasio_actual(request)
    if not gym:
        messages.error(request, 'Seleccione un gimnasio.')
        return redirect('index')
    if request.method == 'POST':
        form = CrearPlanMensualidadForm(request.POST)
        if form.is_valid():
            cat = CategoriaMensualidad.objects.create(
                nombre=form.cleaned_data['nombre'].strip(),
                gimnasio=gym
            )
            messages.success(request, f'Plan "{cat.nombre}" creado. Ahora agregá las opciones (libre, 12 clases, etc.).')
            return redirect('detalle_plan_mensualidad', categoria_id=cat.pk)
    else:
        form = CrearPlanMensualidadForm()
    return render(request, 'crear_plan_mensualidad.html', {'form': form})

@login_required
def detalle_plan_mensualidad(request, categoria_id):
    cat = get_object_or_404(CategoriaMensualidad, pk=categoria_id)
    opciones = TipoMensualidad.objects.filter(categoria=cat).order_by('tipo')
    return render(request, 'detalle_plan_mensualidad.html', {'categoria': cat, 'opciones': opciones})

@login_required
def crear_opcion_mensualidad(request, categoria_id):
    cat = get_object_or_404(CategoriaMensualidad, pk=categoria_id)
    if request.method == 'POST':
        form = CrearOpcionMensualidadForm(request.POST)
        if form.is_valid():
            nombre = form.cleaned_data['nombre'].strip()
            precio = form.cleaned_data['precio']
            clases = form.cleaned_data.get('clases_incluidas')
            frecuencia = 'clases' if (clases is not None and clases > 0) else 'pase_libre'
            TipoMensualidad.objects.create(
                categoria=cat,
                tipo=nombre,
                frecuencia=frecuencia,
                precio=precio,
                clases_incluidas=clases if clases else None
            )
            messages.success(request, f'Opción "{nombre}" agregada.')
            return redirect('detalle_plan_mensualidad', categoria_id=cat.pk)
    else:
        form = CrearOpcionMensualidadForm()
    return render(request, 'crear_opcion_mensualidad.html', {'form': form, 'categoria': cat})

@login_required
def editar_tipo_mensualidad(request, pk):
    tipo = get_object_or_404(TipoMensualidad, pk=pk)
    if request.method == 'POST':
        form = TipoMensualidadForm(request.POST, instance=tipo)
        if form.is_valid():
            obj = form.save(commit=False)
            cls = obj.clases_incluidas
            obj.frecuencia = 'clases' if (cls is not None and cls > 0) else 'pase_libre'
            obj.save()
            return redirect('detalle_plan_mensualidad', categoria_id=tipo.categoria_id)
    else:
        form = TipoMensualidadForm(instance=tipo)
    return render(request, 'editar_tipo_mensualidad.html', {'form': form, 'tipo': tipo})

def eliminar_tipo_mensualidad(request, pk):
    tipo = get_object_or_404(TipoMensualidad, pk=pk)
    cat_id = tipo.categoria_id
    if request.method == 'POST':
        tipo.delete()
        return redirect('detalle_plan_mensualidad', categoria_id=cat_id)
    return render(request, 'eliminar_tipo_mensualidad.html', {'tipo': tipo})


##cuotas

@login_required
@requiere_caja_abierta
def cobrar_mensualidad(request, socio_id):
    """Cobrar o renovar mensualidad. Permite múltiples formas de pago."""
    gym = get_gimnasio_actual(request)
    caja = get_caja_abierta(gym) if gym else None
    socio = get_object_or_404(Socio, pk=socio_id, gimnasio=gym) if gym else get_object_or_404(Socio, pk=socio_id)
    if not socio.tipo_mensualidad:
        messages.warning(request, 'El socio no tiene mensualidad asignada. Asigná una primero.')
        return redirect(reverse('asignar_mensualidad') + f'?socio={socio_id}')
    precio = float(socio.tipo_mensualidad.precio)
    tm = socio.tipo_mensualidad
    es_por_clases = tm.frecuencia == 'clases' and (tm.clases_incluidas or 0) > 0
    clases_a_dar = tm.clases_incluidas if es_por_clases else 0

    # ¿Es renovación? (ya tiene cuota previa)
    tiene_cuota_previa = Cuota.objects.filter(socio=socio).exists()
    es_renovacion = tiene_cuota_previa

    if request.method == 'POST':
        form = CobrarMensualidadForm(request.POST, precio_total=precio)
        if form.is_valid():
            ef = float(form.cleaned_data.get('efectivo') or 0)
            tr = float(form.cleaned_data.get('transferencia') or 0)
            tc = float(form.cleaned_data.get('tarjeta_credito') or 0)
            nombre_titular = (form.cleaned_data.get('nombre_titular') or '').strip() or None
            fecha_cobro = date.today()

            cuota = Cuota.objects.create(
                socio=socio, tipo_mensualidad=tm, precio=precio, gimnasio=socio.gimnasio,
                fecha_inicio=fecha_cobro, nombre_titular_transferencia=nombre_titular,
                efectivo=ef, transferencia=tr, tarjeta_credito=tc, caja=caja,
            )

            socio.fecha_vencimiento = fecha_cobro + timedelta(days=30)
            if es_por_clases:
                socio.clases_restantes = clases_a_dar
            socio.save()

            ingresos.objects.create(
                descripcion=f"Mensualidad {socio.nombre} {socio.apellido}",
                monto=precio, tipo_ingreso='Mensualidad', fecha=fecha_cobro, gimnasio=socio.gimnasio, caja=caja,
            )

            msg = 'Renovación registrada.' if es_renovacion else 'Pago registrado.'
            if es_por_clases:
                msg += f' Quedó con {clases_a_dar} clases del plan.'
            else:
                msg += ' Se agregó 1 mes de servicio.'
            messages.success(request, msg)
            return redirect('lista_socios')
    else:
        form = CobrarMensualidadForm(precio_total=precio)

    fecha_venc_nueva = date.today() + timedelta(days=30)
    return render(request, 'cobrar_mensualidad.html', {
        'socio': socio, 'form': form, 'precio': precio, 'fecha_hoy': date.today(),
        'es_renovacion': es_renovacion, 'es_por_clases': es_por_clases,
        'clases_a_dar': clases_a_dar, 'fecha_venc_nueva': fecha_venc_nueva,
    })


@login_required
def asignar_mensualidad(request):
    gym = get_gimnasio_actual(request)
    socio_id = request.GET.get('socio')
    socio = None
    initial_data = {}
    mensualidad_actual = None

    if socio_id and gym:
        socio = get_object_or_404(Socio, id=socio_id, gimnasio=gym)
        initial_data['socio'] = f"{socio.nombre} {socio.apellido}"
        initial_data['socio_id'] = socio.id

        if socio.tipo_mensualidad:
            initial_data['tipo_mensualidad_display'] = str(socio.tipo_mensualidad)
            mensualidad_actual = socio.tipo_mensualidad
            
    if request.method == 'POST':
        form = AsignarMensualidadForm(request.POST, initial=initial_data, initial_socio=socio, initial_mensualidad=mensualidad_actual, gimnasio=gym)
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
        form = AsignarMensualidadForm(initial=initial_data, initial_socio=socio, initial_mensualidad=mensualidad_actual, gimnasio=gym)

    initial_tipo_id = mensualidad_actual.id if mensualidad_actual else None
    initial_categoria_id = mensualidad_actual.categoria_id if mensualidad_actual and mensualidad_actual.categoria_id else None
    return render(request, 'asignar_mensualidad.html', {
        'form': form, 'socio_id': socio_id,
        'initial_tipo_id': initial_tipo_id, 'initial_categoria_id': initial_categoria_id,
        'gimnasio_actual': gym
    })


@login_required
def lista_cuotas(request):
    gym = get_gimnasio_actual(request)
    socios = Socio.objects.filter(gimnasio=gym) if gym else Socio.objects.none()
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
            
            if cuota.tipo_mensualidad and cuota.tipo_mensualidad.frecuencia == 'clases' and cuota.tipo_mensualidad.clases_incluidas:
                socio.clases_restantes = cuota.tipo_mensualidad.clases_incluidas
                socio.save(update_fields=['clases_restantes'])
                
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
             
             if cuota.tipo_mensualidad and cuota.tipo_mensualidad.frecuencia == 'clases' and cuota.tipo_mensualidad.clases_incluidas:
                socio.clases_restantes = cuota.tipo_mensualidad.clases_incluidas
                socio.save(update_fields=['clases_restantes'])
             
             cuota.delete()
           return redirect(reverse('asignar_mensualidad') + f'?socio={socio_id}&cuota={nueva_cuota.id}')
    else:
        form = SeleccionarFechaRenovacionForm()
    return render(request, 'seleccionar_fecha_renovacion.html', {'form': form, 'socio': socio})



##PRODUCTOS

@login_required
def producto_list(request):
    gym = get_gimnasio_actual(request)
    q_buscar = (request.GET.get('q') or '').strip()
    if gym:
        productos = Producto.objects.filter(gimnasio=gym).order_by('descripcion')
        if q_buscar:
            productos = productos.filter(descripcion__icontains=q_buscar)
    else:
        productos = Producto.objects.none()
    return render(request, 'producto_list.html', {'productos': productos, 'q_buscar': q_buscar})

@login_required
def producto_crear(request):
    gym = get_gimnasio_actual(request)
    if not gym:
        return redirect('gimnasio_lista')
    if request.method == 'POST':
        form = ProductoForm(request.POST)
        if form.is_valid():
            prod = form.save(commit=False)
            prod.gimnasio = gym
            prod.save()
            return redirect('producto_list')
    else:
        form = ProductoForm(initial={'gimnasio': gym})
        form.fields['gimnasio'].queryset = Gimnasio.objects.filter(pk=gym.pk)
        form.fields['gimnasio'].widget = django_forms.HiddenInput()
    return render(request, 'producto_form.html', {'form': form})

@login_required
def producto_editar(request, pk):
    gym = get_gimnasio_actual(request)
    producto = get_object_or_404(Producto, pk=pk, gimnasio=gym) if gym else get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        # El template de edición no envía cantidad/precio del modelo; los armamos acá.
        agregar_raw = (request.POST.get('agregar_cantidad') or '0').strip()
        nuevo_precio_raw = (request.POST.get('nuevo_precio') or '').strip().replace(',', '.')

        errores = []
        try:
            agregar_cantidad = int(agregar_raw) if agregar_raw != '' else 0
            if agregar_cantidad < 0:
                raise ValueError
        except ValueError:
            agregar_cantidad = None
            errores.append('La cantidad a agregar debe ser un número entero mayor o igual a 0.')

        nuevo_precio = None
        if nuevo_precio_raw:
            try:
                nuevo_precio = float(nuevo_precio_raw)
                if nuevo_precio < 0:
                    raise ValueError
            except ValueError:
                errores.append('El nuevo precio debe ser un número mayor o igual a 0.')

        post = request.POST.copy()
        post['cantidad'] = str((producto.cantidad or 0) + (agregar_cantidad or 0))
        post['precio'] = str(nuevo_precio if nuevo_precio is not None else (producto.precio or 0))

        form = ProductoForm(post, instance=producto)
        form.fields['gimnasio'].required = False
        for msg in errores:
            form.add_error(None, msg)

        if not errores and form.is_valid():
            prod = form.save(commit=False)
            prod.gimnasio = producto.gimnasio
            prod.save()
            messages.success(request, 'Producto actualizado correctamente.')
            return redirect('producto_list')
    else:
        form = ProductoForm(instance=producto)
    form.fields['gimnasio'].widget = django_forms.HiddenInput()
    form.fields['gimnasio'].queryset = Gimnasio.objects.filter(pk=producto.gimnasio_id)
    return render(request, 'producto_form.html', {'form': form})

def producto_eliminar(request, pk):
    producto = get_object_or_404(Producto, id=pk)
    if request.method == 'POST':
        producto.delete()
        return redirect('producto_list')  # Redirige a la lista después de eliminar
    return render(request, 'producto_confirmar_eliminar.html', {'producto': producto})


## PROFESORES

@login_required
def profesor_list(request):
    """Lista de profesores del gimnasio actual."""
    gym = get_gimnasio_actual(request)
    q_buscar = (request.GET.get('q') or '').strip()
    if gym:
        profesores = Profesor.objects.filter(gimnasio=gym).order_by('apellido', 'nombre')
        if q_buscar:
            from django.db.models import Q
            profesores = profesores.filter(
                Q(nombre__icontains=q_buscar) | Q(apellido__icontains=q_buscar)
            )
    else:
        profesores = Profesor.objects.none()
    return render(request, 'profesor_list.html', {'profesores': profesores, 'q_buscar': q_buscar})


@login_required
def profesor_crear(request):
    gym = get_gimnasio_actual(request)
    if not gym:
        messages.warning(request, 'Seleccioná un gimnasio primero.')
        return redirect('index')
    if request.method == 'POST':
        form = ProfesorForm(request.POST)
        if form.is_valid():
            prof = form.save(commit=False)
            prof.gimnasio = gym
            prof.save()
            messages.success(request, f'Profesor {prof.nombre} {prof.apellido} creado.')
            return redirect('profesor_list')
    else:
        form = ProfesorForm()
    return render(request, 'profesor_form.html', {'form': form, 'accion': 'Crear'})


@login_required
def profesor_editar(request, pk):
    gym = get_gimnasio_actual(request)
    profesor = get_object_or_404(Profesor, pk=pk, gimnasio=gym) if gym else get_object_or_404(Profesor, pk=pk)
    if request.method == 'POST':
        form = ProfesorForm(request.POST, instance=profesor)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profesor actualizado.')
            return redirect('profesor_detalle', pk=profesor.pk)
    else:
        form = ProfesorForm(instance=profesor)
    return render(request, 'profesor_form.html', {'form': form, 'profesor': profesor, 'accion': 'Editar'})


@login_required
def profesor_detalle(request, pk):
    """Detalle del profesor: productos vendidos, adelantos, pagos, calculador. Maneja adelanto inline y pago."""
    gym = get_gimnasio_actual(request)
    profesor = get_object_or_404(Profesor, pk=pk, gimnasio=gym) if gym else get_object_or_404(Profesor, pk=pk)
    form_adel = AdelantoForm(initial={'fecha': date.today()})
    form_pago = PagoProfesorForm()

    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'adelanto':
            form_adel = AdelantoForm(request.POST)
            if form_adel.is_valid():
                adel = form_adel.save(commit=False)
                adel.profesor = profesor
                adel.gimnasio = profesor.gimnasio
                adel.save()
                messages.success(request, f'Adelanto de ${adel.monto:.2f} registrado.')
                return redirect('profesor_detalle', pk=profesor.pk)
        elif accion == 'pagar':
            form_pago = PagoProfesorForm(request.POST)
            if form_pago.is_valid():
                pago = pago_profesor_guardar(request, profesor, form_pago.cleaned_data)
                if pago:
                    messages.success(request, f'Pago de ${pago.monto:.2f} registrado. Ingresó a caja.')
                    return redirect('profesor_detalle', pk=profesor.pk)

    ventas = Venta.objects.filter(profesor=profesor).select_related('producto').order_by('-fecha', '-id')
    adelantos = Adelanto.objects.filter(profesor=profesor).order_by('-fecha', '-id')
    pagos = PagoProfesor.objects.filter(profesor=profesor).order_by('-fecha', '-id')
    total_ventas_profesor = sum(v.monto_total for v in ventas)
    total_adelantos = adelantos.aggregate(s=Sum('monto'))['s'] or 0
    total_pagos = pagos.aggregate(s=Sum('monto'))['s'] or 0

    return render(request, 'profesor_detalle.html', {
        'profesor': profesor,
        'ventas': ventas,
        'adelantos': adelantos,
        'pagos': pagos,
        'total_ventas_profesor': total_ventas_profesor,
        'total_adelantos': total_adelantos,
        'total_pagos': total_pagos,
        'form_adelanto': form_adel,
        'form_pago': form_pago,
        'caja_abierta': get_caja_abierta(gym) if gym else None,
        'puede_operar_caja': usuario_puede_operar_caja(request, get_caja_abierta(gym) if gym else None),
    })


def pago_profesor_guardar(request, profesor, data):
    """Registra el pago del profesor y crea el ingreso. Requiere caja abierta (excepto super usuario)."""
    gym = profesor.gimnasio
    caja = get_caja_abierta(gym) if gym else None
    if not usuario_puede_operar_caja(request, caja):
        if not caja:
            messages.warning(request, 'Debés abrir la caja antes de registrar pagos.')
        else:
            dueno = caja.usuario_apertura.usuario if caja.usuario_apertura else 'otro usuario'
            messages.error(request, f'Solo {dueno} puede registrar pagos mientras su caja esté abierta.')
        return None
    monto = float(data['monto'])
    metodo = data.get('metodo_pago', 'efectivo')
    ef = monto if metodo == 'efectivo' else 0
    tr = monto if metodo == 'transferencia' else 0
    tc = monto if metodo == 'tarjeta_credito' else 0
    titular = (data.get('nombre_titular') or '').strip() or None

    ventas_pendientes = Venta.objects.filter(profesor=profesor)
    adelantos_pendientes = Adelanto.objects.filter(profesor=profesor)
    total_productos = sum(v.monto_total for v in ventas_pendientes)
    total_adelantos = adelantos_pendientes.aggregate(s=Sum('monto'))['s'] or 0

    pago = PagoProfesor.objects.create(
        profesor=profesor,
        monto=monto,
        efectivo=ef, transferencia=tr, tarjeta_credito=tc,
        nombre_titular=titular,
        descripcion=f'Pago de {profesor.nombre} {profesor.apellido}',
        fecha=date.today(),
        gimnasio=gym,
        caja=caja,
        adelantos_liquidados=total_adelantos,
        productos_liquidados=total_productos,
    )
    ventas_pendientes.update(profesor=None, caja=caja)
    adelantos_pendientes.delete()

    egreso.objects.create(
        descripcion=f'Pago de sueldo a {profesor.nombre} {profesor.apellido}',
        monto=monto,
        tipo_ingreso='Pago profesor',
        fecha=date.today(),
        gimnasio=gym,
        caja=caja,
    )
    return pago


@login_required
def adelanto_crear(request, profesor_id):
    """Redirige a profesor_detalle (adelanto ahora es inline)."""
    return redirect('profesor_detalle', pk=profesor_id)


@login_required
def pago_profesor_detalle(request, pk):
    """Detalle de un pago registrado al profesor: productos, adelantos y el pago."""
    gym = get_gimnasio_actual(request)
    pago = get_object_or_404(PagoProfesor, pk=pk)
    if gym and pago.gimnasio_id != gym.id:
        return redirect('profesor_detalle', pk=pago.profesor_id)
    profesor = pago.profesor
    return render(request, 'pago_profesor_detalle.html', {
        'pago': pago,
        'profesor': profesor,
        'total_ventas': pago.productos_liquidados,
        'total_adelantos': pago.adelantos_liquidados,
    })


##venta

@login_required
def venta_list(request):
    gym = get_gimnasio_actual(request)
    q_buscar = (request.GET.get('q') or '').strip()
    filtro_profesor = request.GET.get('profesor')
    if gym:
        ventas = Venta.objects.filter(gimnasio=gym).select_related('producto', 'usuario', 'profesor').order_by('-fecha', '-id')
        if q_buscar:
            ventas = ventas.filter(producto__descripcion__icontains=q_buscar)
        if filtro_profesor:
            ventas = ventas.filter(profesor_id=filtro_profesor)
    else:
        ventas = Venta.objects.none()
    profesores = Profesor.objects.filter(gimnasio=gym, activo=True).order_by('apellido', 'nombre') if gym else []
    caja = get_caja_abierta(gym) if gym else None
    return render(request, 'venta_list.html', {
        'ventas': ventas, 'q_buscar': q_buscar,
        'profesores': profesores, 'filtro_profesor': filtro_profesor,
        'puede_operar_caja': usuario_puede_operar_caja(request, caja),
        'caja_abierta': caja,
    })

@login_required
@requiere_caja_abierta
def venta_crear(request):
    gym = get_gimnasio_actual(request)
    caja = get_caja_abierta(gym) if gym else None
    if request.method == 'POST':
        form = VentaForm(request.POST, gimnasio=gym)
        if form.is_valid():
            venta = form.save(commit=False)
            venta.profesor = form.cleaned_data.get('profesor')
            # Obtenemos el usuario de Django logueado
            django_user = request.user
            # Obtenemos nuestro usuario personalizado con el mismo nombre de usuario
            try:
                usuario_personalizado = get_usuario_actual(request)
                if not usuario_personalizado:
                    raise Usuario.DoesNotExist
                venta.usuario = usuario_personalizado
                venta.gimnasio = form.cleaned_data['producto'].gimnasio
                venta.fecha = date.today()
                venta.caja = caja
                venta.efectivo = float(form.cleaned_data.get('efectivo') or 0)
                venta.transferencia = float(form.cleaned_data.get('transferencia') or 0)
                venta.tarjeta_credito = float(form.cleaned_data.get('tarjeta_credito') or 0)
                venta.nombre_titular = (form.cleaned_data.get('nombre_titular') or '').strip() or None
                venta.save()
                producto = venta.producto
                producto.cantidad -= venta.cantidad
                producto.save()

                if not venta.profesor:
                    monto_ingreso = venta.efectivo + venta.transferencia + venta.tarjeta_credito
                    ingresos.objects.create(
                        descripcion=f'Venta de {producto.descripcion}',
                        monto=monto_ingreso,
                        tipo_ingreso='Venta',
                        fecha=date.today(),
                        gimnasio=venta.gimnasio,
                        caja=caja,
                    )

                return redirect('venta_list')
            except Usuario.DoesNotExist:
                # En caso de que no exista un Usuario personalizado asociado, puedes manejarlo aquí,
                # ya sea creando uno nuevo o mostrando un mensaje de error
                # Por ejemplo, aquí lo redirigimos a una pantalla de error
                return render(request, 'error/usuario_no_encontrado.html')  # Redirigir a una plantilla de error.
    else:
        gym = get_gimnasio_actual(request)
        form = VentaForm(gimnasio=gym)
        profesor_id = request.GET.get('profesor')
        if profesor_id and gym:
            try:
                prof = Profesor.objects.get(pk=profesor_id, gimnasio=gym)
                form.initial['profesor'] = prof
            except Profesor.DoesNotExist:
                pass
    return render(request, 'venta_form.html', {'form': form})

def producto_precio(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    return JsonResponse({'precio': producto.precio})


## extras

@login_required
def extras_list(request):
    gym = get_gimnasio_actual(request)
    extras_lista = extras.objects.filter(gimnasio=gym) if gym else extras.objects.none()
    return render(request, 'extras_list.html', {'extras_lista': extras_lista})

@login_required
def extras_create(request):
    gym = get_gimnasio_actual(request)
    if request.method == 'POST':
        form = ExtrasForm(request.POST, gimnasio=gym)
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
        form = ExtrasForm(gimnasio=gym)
    return render(request, 'extras_form.html', {'form': form, 'title': 'Crear Extra'})

@login_required
def extras_update(request, pk):
    gym = get_gimnasio_actual(request)
    extra = get_object_or_404(extras, pk=pk, gimnasio=gym) if gym else get_object_or_404(extras, pk=pk)
    if request.method == 'POST':
        form = ExtrasForm(request.POST, instance=extra, gimnasio=gym)
        if form.is_valid():
            form.save()
            messages.success(request, 'Extra actualizado correctamente.')
            return redirect('extras_list')
    else:
        form = ExtrasForm(instance=extra, gimnasio=gym)
    return render(request, 'extras_form.html', {'form': form, 'title': 'Editar Extra'})


@login_required
def extras_delete(request, pk):
    gym = get_gimnasio_actual(request)
    extra = get_object_or_404(extras, pk=pk, gimnasio=gym) if gym else get_object_or_404(extras, pk=pk)
    if request.method == 'POST':
        extra.delete()
        messages.success(request, 'Extra eliminado correctamente.')
        return redirect('extras_list')
    return render(request, 'extras_confirm_delete.html', {'extra': extra})


## gastos

@login_required
def gastos_list(request):
    gym = get_gimnasio_actual(request)
    gastos_lista = Gasto.objects.filter(gimnasio=gym).order_by('-fecha', '-id') if gym else Gasto.objects.none()
    puede_eliminar_gastos = request.user.is_superuser or (request.session.get('tipo_usuario') == 'admin')
    return render(request, 'gastos_list.html', {
        'gastos_lista': gastos_lista,
        'puede_eliminar_gastos': puede_eliminar_gastos,
    })


@login_required
@requiere_caja_abierta
def gastos_crear(request):
    gym = get_gimnasio_actual(request)
    if not gym:
        messages.error(request, 'Seleccione un gimnasio desde el inicio.')
        return redirect('index')
    if request.method == 'POST':
        form = GastoForm(request.POST)
        if form.is_valid():
            Gasto.objects.create(
                descripcion=form.cleaned_data['descripcion'],
                monto=form.cleaned_data['monto'],
                forma_pago=form.cleaned_data['forma_pago'],
                fecha=date.today(),
                gimnasio=gym,
                caja=get_caja_abierta(gym),
            )
            messages.success(request, 'Gasto registrado correctamente.')
            return redirect('gastos_list')
    else:
        form = GastoForm()
    return render(request, 'gastos_form.html', {'form': form, 'fecha_hoy': date.today()})


@login_required
def gastos_eliminar(request, pk):
    es_admin = request.user.is_superuser or (request.session.get('tipo_usuario') == 'admin')
    if not es_admin:
        messages.error(request, 'No tenés permisos para eliminar gastos.')
        return redirect('gastos_list')
    gym = get_gimnasio_actual(request)
    gasto = get_object_or_404(Gasto, pk=pk, gimnasio=gym) if gym else get_object_or_404(Gasto, pk=pk)
    if request.method == 'POST':
        gasto.delete()
        messages.success(request, 'Gasto eliminado.')
        return redirect('gastos_list')
    return render(request, 'gastos_confirm_delete.html', {'gasto': gasto})


## historiales

@login_required
def historiales_index(request):
    """Selector de período y gimnasio para historiales."""
    gym = get_gimnasio_actual(request)
    gimnasios = list(gimnasios_disponibles(request))
    context = {
        'gimnasios': gimnasios,
        'gimnasio_actual': gym,
    }
    return render(request, 'historiales_index.html', context)


def gimnasios_disponibles(request):
    """Devuelve gimnasios disponibles para el usuario."""
    if request.user.is_superuser:
        return Gimnasio.objects.all().order_by('nombre', 'direccion')
    try:
        usuario = Usuario.objects.get(usuario=request.user.username)
        return Gimnasio.objects.filter(usuarios_asignados__usuario=usuario).distinct().order_by('nombre', 'direccion')
    except Usuario.DoesNotExist:
        return Gimnasio.objects.all().order_by('nombre', 'direccion')


@login_required
def historiales_reporte(request):
    """Reporte de historiales: ingresos mensualidades, ventas, gastos por forma de pago."""
    periodo = request.GET.get('periodo', 'diario')  # diario, mensual, anual
    gimnasio_id = request.GET.get('gimnasio')
    fecha_str = request.GET.get('fecha', date.today().isoformat())
    año = request.GET.get('anio', str(date.today().year))
    mes = request.GET.get('mes', str(date.today().month))

    gimnasios_qs = gimnasios_disponibles(request)
    gimnasios_lista = list(gimnasios_qs)
    gimnasio_seleccionado = None
    if gimnasio_id:
        gimnasio_seleccionado = next((g for g in gimnasios_lista if str(g.id) == gimnasio_id), None)
    if not gimnasio_seleccionado and gimnasios_lista:
        gimnasio_seleccionado = gimnasios_lista[0]

    reportes = []
    gimnasios_a_revisar = [gimnasio_seleccionado] if gimnasio_seleccionado else gimnasios_lista

    for gym in gimnasios_a_revisar:
        rep = _construir_reporte(gym, periodo, fecha_str, año, mes)
        reportes.append(rep)

    context = {
        'reportes': reportes,
        'periodo': periodo,
        'fecha': fecha_str,
        'anio': año,
        'mes': mes,
        'gimnasios': gimnasios_lista,
        'gimnasio_seleccionado': gimnasio_seleccionado,
    }
    return render(request, 'historiales_reporte.html', context)


def _construir_reporte(gym, periodo, fecha_str, año, mes):
    """Construye el dict con datos del reporte para un gimnasio."""
    from datetime import datetime
    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        fecha = date.today()
    año_i = int(año) if año else date.today().year
    mes_i = int(mes) if mes else date.today().month

    if periodo == 'diario':
        inicio = fin = fecha
    elif periodo == 'mensual':
        inicio = date(año_i, mes_i, 1)
        if mes_i == 12:
            fin = date(año_i, 12, 31)
        else:
            fin = date(año_i, mes_i + 1, 1) - timedelta(days=1)
    else:  # anual
        inicio = date(año_i, 1, 1)
        fin = date(año_i, 12, 31)

    # Cuotas (mensualidades)
    cuotas = Cuota.objects.filter(gimnasio=gym, fecha_inicio__gte=inicio, fecha_inicio__lte=fin)
    mens_ef = cuotas.aggregate(s=Sum('efectivo'))['s'] or 0
    mens_tr = cuotas.aggregate(s=Sum('transferencia'))['s'] or 0
    mens_tc = cuotas.aggregate(s=Sum('tarjeta_credito'))['s'] or 0
    mens_total = mens_ef + mens_tr + mens_tc

    # Ventas
    ventas = Venta.objects.filter(gimnasio=gym, fecha__gte=inicio, fecha__lte=fin)
    ven_ef = ventas.aggregate(s=Sum('efectivo'))['s'] or 0
    ven_tr = ventas.aggregate(s=Sum('transferencia'))['s'] or 0
    ven_tc = ventas.aggregate(s=Sum('tarjeta_credito'))['s'] or 0
    ven_total = ven_ef + ven_tr + ven_tc

    # Gastos (Gasto + egreso legacy)
    gastos = Gasto.objects.filter(gimnasio=gym, fecha__gte=inicio, fecha__lte=fin)
    gas_ef = gastos.filter(forma_pago='efectivo').aggregate(s=Sum('monto'))['s'] or 0
    gas_tr = gastos.filter(forma_pago='transferencia').aggregate(s=Sum('monto'))['s'] or 0
    gas_tc = gastos.filter(forma_pago='tarjeta_credito').aggregate(s=Sum('monto'))['s'] or 0
    gas_total_g = gas_ef + gas_tr + gas_tc

    egresos = egreso.objects.filter(gimnasio=gym, fecha__gte=inicio, fecha__lte=fin)
    gas_total_e = egresos.aggregate(s=Sum('monto'))['s'] or 0

    gas_total = gas_total_g + gas_total_e

    total_ingresos = mens_total + ven_total
    balance = total_ingresos - gas_total

    return {
        'gym': gym,
        'periodo': periodo,
        'inicio': inicio,
        'fin': fin,
        'mensualidades': {'efectivo': mens_ef, 'transferencia': mens_tr, 'tarjeta': mens_tc, 'total': mens_total},
        'ventas': {'efectivo': ven_ef, 'transferencia': ven_tr, 'tarjeta': ven_tc, 'total': ven_total},
        'gastos': gas_total,
        'total_ingresos': total_ingresos,
        'balance': balance,
    }


## caja diaria

@login_required
def balance_diario(request):
    gym = get_gimnasio_actual(request)
    if request.method == 'POST':
        form = SeleccionGimnasioForm(request.POST)
        if form.is_valid():
            gimnasio_seleccionado = form.cleaned_data['gimnasio']
            return redirect('mostrar_balance', gimnasio_id=gimnasio_seleccionado.id)
    else:
        if gym:
            return redirect('mostrar_balance', gimnasio_id=gym.id)
        form = SeleccionGimnasioForm()
    return render(request, 'seleccionar_gimnasio.html', {'form': form})


@login_required
def caja_abrir(request, gimnasio_id):
    gym = get_object_or_404(Gimnasio, pk=gimnasio_id)
    caja_existente = get_caja_abierta(gym)
    if caja_existente:
        messages.warning(request, f'Ya hay una caja abierta por {caja_existente.usuario_apertura.usuario}. Solo puede haber una caja abierta a la vez.')
        return redirect('mostrar_balance', gimnasio_id=gimnasio_id)
    usuario = get_usuario_actual(request)
    if not usuario:
        messages.error(request, 'Usuario no encontrado.')
        return redirect('mostrar_balance', gimnasio_id=gimnasio_id)
    Caja.objects.create(gimnasio=gym, usuario_apertura=usuario)
    messages.success(request, f'Caja abierta correctamente por {usuario.usuario}.')
    return redirect('mostrar_balance', gimnasio_id=gimnasio_id)


@login_required
def caja_cerrar(request, gimnasio_id):
    gym = get_object_or_404(Gimnasio, pk=gimnasio_id)
    caja = get_caja_abierta(gym)
    if not caja:
        messages.info(request, 'No hay caja abierta para cerrar.')
        return redirect('mostrar_balance', gimnasio_id=gimnasio_id)
    usuario = get_usuario_actual(request)
    es_admin = request.user.is_superuser or (request.session.get('tipo_usuario') == 'admin')
    es_mismo = usuario and caja.usuario_apertura_id == usuario.id
    if not (es_admin or es_mismo):
        messages.error(request, 'Solo el empleado que abrió la caja o un administrador puede cerrarla.')
        return redirect('mostrar_balance', gimnasio_id=gimnasio_id)
    from django.utils import timezone
    caja.fecha_cierre = timezone.now()
    ti, te, bal = calcular_totales_caja(caja)
    caja.total_ingresos = ti
    caja.total_egresos = te
    caja.balance = bal
    caja.save()
    hoy = date.today()
    BalanceDiario.objects.update_or_create(
        gimnasio=gym, fecha=hoy,
        defaults={'total_ingresos': ti, 'total_egresos': te, 'balance': bal}
    )
    messages.success(request, 'Caja cerrada correctamente. Los movimientos quedaron registrados en historiales.')
    return redirect('mostrar_balance', gimnasio_id=gimnasio_id)


@login_required
def mostrar_balance(request, gimnasio_id):
    try:
        request.session['gimnasio_actual_id'] = int(gimnasio_id)
        hoy = date.today()
        gimnasio_seleccionado = get_object_or_404(Gimnasio, pk=gimnasio_id)
        gimnasio_nombre = gimnasio_seleccionado.nombre or gimnasio_seleccionado.direccion

        caja_abierta = get_caja_abierta(gimnasio_seleccionado)
        movs = movimientos_caja_abierta(caja_abierta)
        ingresos_hoy = movs['ingresos']
        egresos_hoy = movs['egresos']
        gastos_hoy = movs['gastos']
        cuotas_hoy = movs['cuotas']
        ventas_hoy = movs['ventas']
        ventas_profesores_hoy = movs['ventas_profesores']
        pagos_profesor_hoy = movs['pagos_profesor']

        total_ingresos = sum(i.monto for i in ingresos_hoy if i.monto)
        total_egresos = sum(e.monto for e in egresos_hoy if e.monto)
        total_egresos += sum(g.monto for g in gastos_hoy if g.monto)
        balance = total_ingresos - total_egresos

        ing_efectivo = (
            sum((c.efectivo or 0) for c in cuotas_hoy)
            + sum((v.efectivo or 0) for v in ventas_hoy)
        )
        ing_transferencia = (
            sum((c.transferencia or 0) for c in cuotas_hoy)
            + sum((v.transferencia or 0) for v in ventas_hoy)
        )
        ing_tarjeta = (
            sum((c.tarjeta_credito or 0) for c in cuotas_hoy)
            + sum((v.tarjeta_credito or 0) for v in ventas_hoy)
        )

        usuario = get_usuario_actual(request)
        es_admin = request.user.is_superuser or (request.session.get('tipo_usuario') == 'admin')
        puede_cerrar = caja_abierta and (es_admin or (usuario and caja_abierta.usuario_apertura_id == usuario.id))
        puede_operar_caja = usuario_puede_operar_caja(request, caja_abierta)

        context = {
            'gimnasio_id': gimnasio_id,
            'gimnasio_nombre': gimnasio_nombre,
            'ingresos': ingresos_hoy,
            'egresos': egresos_hoy,
            'gastos': gastos_hoy,
            'cuotas': cuotas_hoy,
            'ventas': ventas_hoy,
            'ventas_profesores': ventas_profesores_hoy,
            'pagos_profesor_hoy': pagos_profesor_hoy,
            'total_ingresos': total_ingresos,
            'total_egresos': total_egresos,
            'balance': balance,
            'ing_efectivo': ing_efectivo,
            'ing_transferencia': ing_transferencia,
            'ing_tarjeta': ing_tarjeta,
            'fecha': hoy,
            'caja_abierta': caja_abierta,
            'puede_cerrar': puede_cerrar,
            'puede_operar_caja': puede_operar_caja,
        }
        return render(request, 'mostrar_balance.html', context)
    except Exception as e:
        print(e)
        return render(request, 'error.html',{'error':e})


def historial_balances(request):
    """Solo admin/super: historial de balances diarios. Empleados no acceden."""
    es_admin = request.user.is_superuser or (request.session.get('tipo_usuario') == 'admin')
    if not es_admin:
        return redirect('historial_cajas')
    balances = BalanceDiario.objects.all().order_by('-fecha')
    grouped_balances = {}
    for balance in balances:
        nom_gym = balance.gimnasio.nombre or balance.gimnasio.direccion or f'Gimnasio {balance.gimnasio.id}'
        key = (balance.gimnasio_id, nom_gym, balance.fecha.year, balance.fecha.month)
        if key not in grouped_balances:
            grouped_balances[key] = []
        grouped_balances[key].append(balance)
    gimnasios_con_historial = list(set(balance.gimnasio for balance in balances))
    all_gimnasios = Gimnasio.objects.all()
    context = {
        'grouped_balances': grouped_balances,
        'gimnasios_con_historial': gimnasios_con_historial,
        'all_gimnasios': all_gimnasios,
    }
    return render(request, 'historial_balances.html', context)


@login_required
def historial_cajas(request):
    """Admin: cajas agrupadas por empleado (nombre de cuenta). Empleado: solo sus cajas."""
    es_admin = request.user.is_superuser or (request.session.get('tipo_usuario') == 'admin')
    usuario = get_usuario_actual(request)

    if es_admin:
        cajas = Caja.objects.all().select_related('gimnasio', 'usuario_apertura').order_by('-fecha_apertura')
        cajas_por_empleado = {}
        for c in cajas:
            nom = (c.usuario_apertura.usuario if c.usuario_apertura else 'Sin usuario')
            if nom not in cajas_por_empleado:
                cajas_por_empleado[nom] = {'empleado': nom, 'cajas': []}
            cajas_por_empleado[nom]['cajas'].append(c)
        context = {'es_admin': True, 'cajas_por_empleado': list(cajas_por_empleado.values()), 'mis_cajas': None}
    else:
        if not usuario:
            context = {'es_admin': False, 'cajas_por_empleado': [], 'mis_cajas': []}
        else:
            mis_cajas = Caja.objects.filter(usuario_apertura=usuario).select_related('gimnasio').order_by('-fecha_apertura')
            context = {'es_admin': False, 'cajas_por_empleado': [], 'mis_cajas': mis_cajas}
    return render(request, 'historial_cajas.html', context)


@login_required
def detalle_caja(request, caja_id):
    """Detalle de movimientos de una caja (mensualidades, ventas, egresos, gastos)."""
    caja = get_object_or_404(Caja, pk=caja_id)
    gym = caja.gimnasio
    fin = caja.fecha_cierre.date() if caja.fecha_cierre else date.today()
    inicio = caja.fecha_apertura.date()

    def _por_caja(model, **extra):
        qs = model.objects.filter(caja=caja, **extra)
        if qs.exists():
            return qs
        return model.objects.filter(gimnasio=gym, caja__isnull=True, **extra)

    cuotas = _por_caja(Cuota, fecha_inicio__gte=inicio, fecha_inicio__lte=fin).select_related('socio', 'tipo_mensualidad').order_by('fecha_inicio')
    ventas = _por_caja(Venta, fecha__gte=inicio, fecha__lte=fin, profesor__isnull=True).select_related('producto').order_by('fecha')
    pagos_prof = _por_caja(PagoProfesor, fecha__gte=inicio, fecha__lte=fin).select_related('profesor').order_by('fecha')
    ing_otros = _por_caja(ingresos, fecha__gte=inicio, fecha__lte=fin).exclude(tipo_ingreso__in=['Mensualidad', 'Venta', 'Pago profesor']).order_by('fecha')
    egresos_list = _por_caja(egreso, fecha__gte=inicio, fecha__lte=fin).order_by('fecha')
    gastos_list = _por_caja(Gasto, fecha__gte=inicio, fecha__lte=fin).order_by('fecha')

    if caja.total_ingresos is not None and caja.fecha_cierre:
        tot_ing = caja.total_ingresos
        tot_egr = caja.total_egresos or 0
        balance = caja.balance if caja.balance is not None else tot_ing - tot_egr
        tot_mens = sum(c.precio or 0 for c in cuotas)
        tot_ventas = sum(v.monto_total for v in ventas)
        tot_pagos_prof = sum(p.monto for p in pagos_prof)
        tot_otros = sum(i.monto or 0 for i in ing_otros)
    else:
        tot_mens = sum(c.precio or 0 for c in cuotas)
        tot_ventas = sum(v.monto_total for v in ventas)
        tot_pagos_prof = sum(p.monto for p in pagos_prof)
        tot_otros = sum(i.monto or 0 for i in ing_otros)
        tot_egr = sum(e.monto or 0 for e in egresos_list) + sum(g.monto for g in gastos_list)
        tot_ing = tot_mens + tot_ventas + tot_otros
        balance = tot_ing - tot_egr

    mens_ef = sum(c.efectivo or 0 for c in cuotas)
    mens_tr = sum(c.transferencia or 0 for c in cuotas)
    mens_tc = sum(c.tarjeta_credito or 0 for c in cuotas)
    ven_ef = sum(v.efectivo or 0 for v in ventas)
    ven_tr = sum(v.transferencia or 0 for v in ventas)
    ven_tc = sum(v.tarjeta_credito or 0 for v in ventas)

    context = {
        'caja': caja,
        'cuotas': cuotas,
        'ventas': ventas,
        'pagos_profesor': pagos_prof,
        'ing_otros': ing_otros,
        'egresos': egresos_list,
        'gastos': gastos_list,
        'inicio': inicio, 'fin': fin,
        'tot_mens': tot_mens, 'tot_ventas': tot_ventas, 'tot_pagos_prof': tot_pagos_prof, 'tot_otros': tot_otros,
        'tot_ing': tot_ing, 'tot_egr': tot_egr, 'balance': balance,
        'mens_ef': mens_ef, 'mens_tr': mens_tr, 'mens_tc': mens_tc,
        'ven_ef': ven_ef, 'ven_tr': ven_tr, 'ven_tc': ven_tc,
    }
    return render(request, 'detalle_caja.html', context)


def detalle_balance(request, balance_id):
    balance = get_object_or_404(BalanceDiario, id=balance_id)
    gym = balance.gimnasio
    f = balance.fecha

    ingresos_hoy = ingresos.objects.filter(gimnasio=gym, fecha=f)
    cuotas_hoy = Cuota.objects.filter(gimnasio=gym, fecha_inicio=f).select_related('socio', 'tipo_mensualidad')
    ventas_hoy = Venta.objects.filter(gimnasio=gym, fecha=f, profesor__isnull=True).select_related('producto')
    pagos_profesor_hoy = PagoProfesor.objects.filter(gimnasio=gym, fecha=f).select_related('profesor')
    egresos_hoy = egreso.objects.filter(gimnasio=gym, fecha=f)
    gastos_hoy = Gasto.objects.filter(gimnasio=gym, fecha=f)

    ing_mens = sum(c.precio or 0 for c in cuotas_hoy)
    ing_ven = sum(v.monto_total for v in ventas_hoy)
    ing_pagos_prof = sum(p.monto for p in pagos_profesor_hoy)
    ing_otros = ingresos_hoy.exclude(tipo_ingreso__in=['Mensualidad', 'Venta', 'Renovación']).aggregate(s=Sum('monto'))['s'] or 0
    ing_renov = ingresos_hoy.filter(tipo_ingreso='Renovación').aggregate(s=Sum('monto'))['s'] or 0

    ef_ing = sum((c.efectivo or 0) for c in cuotas_hoy) + sum((v.efectivo or 0) for v in ventas_hoy)
    tr_ing = sum((c.transferencia or 0) for c in cuotas_hoy) + sum((v.transferencia or 0) for v in ventas_hoy)
    tc_ing = sum((c.tarjeta_credito or 0) for c in cuotas_hoy) + sum((v.tarjeta_credito or 0) for v in ventas_hoy)

    tot_egr = (egresos_hoy.aggregate(s=Sum('monto'))['s'] or 0) + (gastos_hoy.aggregate(s=Sum('monto'))['s'] or 0)
    ef_egr = sum(g.monto for g in gastos_hoy if g.forma_pago == 'efectivo') + sum((p.efectivo or 0) for p in pagos_profesor_hoy)
    tr_egr = sum(g.monto for g in gastos_hoy if g.forma_pago == 'transferencia') + sum((p.transferencia or 0) for p in pagos_profesor_hoy)
    tc_egr = sum(g.monto for g in gastos_hoy if g.forma_pago == 'tarjeta_credito') + sum((p.tarjeta_credito or 0) for p in pagos_profesor_hoy)
    egresos_sin_fp = egresos_hoy.exclude(tipo_ingreso='Pago profesor').aggregate(s=Sum('monto'))['s'] or 0

    context = {
        'balance': balance,
        'ingresos': ingresos_hoy,
        'cuotas': cuotas_hoy,
        'ventas': ventas_hoy,
        'pagos_profesor': pagos_profesor_hoy,
        'egresos': egresos_hoy,
        'gastos': gastos_hoy,
        'ing_mens': ing_mens,
        'ing_ventas': ing_ven,
        'ing_renov': ing_renov,
        'ing_pagos_prof': ing_pagos_prof,
        'ing_otros': ing_otros,
        'ef_ing': ef_ing, 'tr_ing': tr_ing, 'tc_ing': tc_ing,
        'tot_egr': tot_egr,
        'ef_egr': ef_egr, 'tr_egr': tr_egr, 'tc_egr': tc_egr,
        'egresos_sin_fp': egresos_sin_fp,
    }
    return render(request, 'detalle_balance.html', context)




##lista de ingresos

def _ingreso_desde_registro(registro, socio, fecha_referencia):
    """Arma el dict de fila para listados de ingreso (vencido / pendiente de pago)."""
    pendiente_pago = not Cuota.objects.filter(socio=socio).exists()
    fecha_vencimiento = socio.fecha_vencimiento
    if not fecha_vencimiento and not pendiente_pago:
        try:
            ultima_cuota = Cuota.objects.filter(socio=socio).latest('fecha_inicio')
            fecha_vencimiento = ultima_cuota.fecha_inicio + timedelta(days=30)
        except Cuota.DoesNotExist:
            fecha_vencimiento = None
    cr = registro.clases_restantes_al_ingresar
    clases_despues = (cr - 1) if cr is not None and cr > 0 else (None if cr is None else 0)
    vencido_por_fecha = bool(fecha_vencimiento and fecha_vencimiento < fecha_referencia)
    cat = socio.tipo_mensualidad.categoria if socio.tipo_mensualidad else None
    return {
        'nombre': registro.nombre_socio,
        'apellido': registro.apellido_socio,
        'dni': registro.dni_socio,
        'fecha_ingreso': registro.fecha_ingreso,
        'fecha_vencimiento': fecha_vencimiento,
        'pendiente_pago': pendiente_pago,
        'vencido': pendiente_pago or vencido_por_fecha,
        'clases_restantes': clases_despues,
        'tipo_mensualidad': socio.tipo_mensualidad.tipo if socio.tipo_mensualidad else 'Sin mensualidad',
        'categoria': cat.nombre if cat else '-',
        'categoria_id': cat.pk if cat else None,
    }


@login_required
def listado_ingresos_diarios(request):
    gym = get_gimnasio_actual(request)
    fecha = request.GET.get('fecha', date.today().isoformat())
    categoria_filtro = (request.GET.get('categoria') or '').strip()
    try:
        fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date() if fecha else date.today()
    except (ValueError, TypeError):
        fecha_obj = date.today()
    qs = RegistroIngreso.objects.filter(fecha_ingreso__date=fecha)
    if gym:
        qs = qs.filter(gimnasio=gym)
    registros_ingreso = qs.order_by('-fecha_ingreso')
    ingresos_con_socio = []

    for registro in registros_ingreso:
        try:
            socio = Socio.objects.select_related(
                'tipo_mensualidad', 'tipo_mensualidad__categoria',
            ).get(dni=registro.dni_socio, gimnasio=gym) if gym else Socio.objects.select_related(
                'tipo_mensualidad', 'tipo_mensualidad__categoria',
            ).get(dni=registro.dni_socio)
            ingresos_con_socio.append(_ingreso_desde_registro(registro, socio, fecha_obj))
        except Socio.DoesNotExist:
            cr = registro.clases_restantes_al_ingresar
            clases_despues = (cr - 1) if cr is not None and cr > 0 else (None if cr is None else 0)
            ingresos_con_socio.append({
                'nombre': registro.nombre_socio,
                'apellido': registro.apellido_socio,
                'dni': registro.dni_socio,
                'fecha_ingreso': registro.fecha_ingreso,
                'fecha_vencimiento': None,
                'pendiente_pago': False,
                'vencido': False,
                'clases_restantes': clases_despues,
                'tipo_mensualidad': 'Socio no encontrado',
                'categoria': '-',
                'categoria_id': None,
            })
        except Exception as e:
            cr = registro.clases_restantes_al_ingresar
            clases_despues = (cr - 1) if cr is not None and cr > 0 else (None if cr is None else 0)
            ingresos_con_socio.append({
                'nombre': registro.nombre_socio,
                'apellido': registro.apellido_socio,
                'dni': registro.dni_socio,
                'fecha_ingreso': registro.fecha_ingreso,
                'fecha_vencimiento': None,
                'pendiente_pago': False,
                'vencido': False,
                'clases_restantes': clases_despues,
                'tipo_mensualidad': 'Error al obtener mensualidad',
                'categoria': '-',
                'categoria_id': None,
            })

    total_ingresos = len(ingresos_con_socio)
    conteo_por_categoria, conteo_sin_categoria = _conteo_ingresos_por_categoria(ingresos_con_socio)
    if categoria_filtro == 'sin':
        ingresos_con_socio = [i for i in ingresos_con_socio if i.get('categoria_id') is None]
    elif categoria_filtro.isdigit():
        cat_id = int(categoria_filtro)
        ingresos_con_socio = [i for i in ingresos_con_socio if i.get('categoria_id') == cat_id]

    categorias_filtro = CategoriaMensualidad.objects.filter(gimnasio=gym).order_by('nombre') if gym else CategoriaMensualidad.objects.none()
    context = {
        'ingresos': ingresos_con_socio,
        'fecha': fecha,
        'fecha_obj': fecha_obj,
        'categoria_filtro': categoria_filtro,
        'categorias_filtro': categorias_filtro,
        'total_ingresos': total_ingresos,
        'conteo_por_categoria': conteo_por_categoria,
        'conteo_sin_categoria': conteo_sin_categoria,
    }
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
    try:
        fecha_obj = fecha if hasattr(fecha, 'year') else datetime.strptime(str(fecha), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        fecha_obj = date.today()
    registros_ingreso = RegistroIngreso.objects.filter(fecha_ingreso__date=fecha).order_by('-fecha_ingreso')
    ingresos_con_socio = []

    for registro in registros_ingreso:
        try:
            socio = Socio.objects.get(dni=registro.dni_socio)
            ingresos_con_socio.append(_ingreso_desde_registro(registro, socio, fecha_obj))
        except Socio.DoesNotExist:
            cr = registro.clases_restantes_al_ingresar
            clases_despues = (cr - 1) if cr is not None and cr > 0 else (None if cr is None else 0)
            ingresos_con_socio.append({
                'nombre': registro.nombre_socio,
                'apellido': registro.apellido_socio,
                'dni': registro.dni_socio,
                'fecha_ingreso': registro.fecha_ingreso,
                'fecha_vencimiento': None,
                'pendiente_pago': False,
                'vencido': False,
                'clases_restantes': clases_despues,
                'tipo_mensualidad': 'Socio no encontrado',
            })
        except Exception as e:
            cr = registro.clases_restantes_al_ingresar
            clases_despues = (cr - 1) if cr is not None and cr > 0 else (None if cr is None else 0)
            ingresos_con_socio.append({
                'nombre': registro.nombre_socio,
                'apellido': registro.apellido_socio,
                'dni': registro.dni_socio,
                'fecha_ingreso': registro.fecha_ingreso,
                'fecha_vencimiento': None,
                'pendiente_pago': False,
                'vencido': False,
                'clases_restantes': clases_despues,
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
                'celular': socio.celular,
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
                         'celular': socio.celular,
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


# API: categorías y mensualidades por categoría (filtradas por gimnasio)
@csrf_exempt
def api_categorias(request):
    if request.method == 'GET':
        gimnasio_id = request.GET.get('gimnasio_id')
        qs = CategoriaMensualidad.objects.all().order_by('nombre')
        if gimnasio_id:
            qs = qs.filter(gimnasio_id=gimnasio_id)
        data = [{'id': c.id, 'nombre': c.nombre} for c in qs.distinct()]
        return JsonResponse(data, safe=False)
    return JsonResponse({'error': 'Método no permitido'}, status=405)


@csrf_exempt
def api_mensualidades_por_categoria(request):
    if request.method == 'GET':
        categoria_id = request.GET.get('categoria_id')
        if not categoria_id:
            return JsonResponse({'error': 'categoria_id requerido'}, status=400)
        tipos = TipoMensualidad.objects.filter(categoria_id=categoria_id).order_by('tipo')
        data = [{
            'id': t.id,
            'tipo': t.tipo,
            'precio': float(t.precio),
            'frecuencia': t.get_frecuencia_display() if t.frecuencia else '',
            'clases_incluidas': t.clases_incluidas
        } for t in tipos]
        return JsonResponse(data, safe=False)
    return JsonResponse({'error': 'Método no permitido'}, status=405)


# API: ingreso por DNI - busca socio, registra ingreso, devuelve datos para pantalla
@csrf_exempt
def api_ingreso_por_dni(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.body else {}
            dni = (data.get('dni') or '').strip()
            if not dni:
                return JsonResponse({'error': 'DNI requerido', 'ok': False}, status=400)
            gimnasio_id = data.get('gimnasio_id')
            qs = Socio.objects.filter(dni=dni)
            if gimnasio_id:
                qs = qs.filter(gimnasio_id=gimnasio_id)
            try:
                socio = qs.get()
            except Socio.DoesNotExist:
                return JsonResponse({
                    'ok': False,
                    'encontrado': False,
                    'mensaje': 'Socio no encontrado'
                })
            hoy = date.today()
            pendiente_pago = not Cuota.objects.filter(socio=socio).exists()
            vigente = True
            mensaje_vigencia = ''
            if pendiente_pago:
                vigente = False
                mensaje_vigencia = 'SOCIO PENDIENTE DE PAGO'
            elif socio.fecha_vencimiento and socio.fecha_vencimiento < hoy:
                vigente = False
                mensaje_vigencia = 'Mensualidad vencida'
            elif socio.tipo_mensualidad and socio.tipo_mensualidad.frecuencia == 'clases' and socio.clases_restantes <= 0:
                vigente = False
                mensaje_vigencia = 'Sin clases restantes'
            tipo_mens = socio.tipo_mensualidad
            mes_vencido = pendiente_pago or bool(socio.fecha_vencimiento and socio.fecha_vencimiento < hoy)
            es_plan_clases = bool(tipo_mens and tipo_mens.frecuencia == 'clases')
            usa_contador_clases = bool(
                tipo_mens
                and tipo_mens.frecuencia != 'pase_libre'
                and (es_plan_clases or (socio.clases_restantes or 0) > 0 or tipo_mens.clases_incluidas)
            )
            dias_restantes = None
            if socio.fecha_vencimiento:
                delta = socio.fecha_vencimiento - hoy
                dias_restantes = max(0, delta.days)
            RegistroIngreso.objects.create(
                gimnasio=socio.gimnasio,
                dni_socio=socio.dni,
                fecha_ingreso=tz.now(),
                clases_restantes_al_ingresar=socio.clases_restantes,
                nombre_socio=socio.nombre,
                apellido_socio=socio.apellido
            )
            if vigente and tipo_mens and tipo_mens.frecuencia == 'clases' and socio.clases_restantes > 0:
                socio.clases_restantes = F('clases_restantes') - 1
                socio.save(update_fields=['clases_restantes'])
                socio.refresh_from_db()
            from .turnos_utils import info_turno_kiosk
            turno_kiosk = info_turno_kiosk(socio, hoy)
            return JsonResponse({
                'ok': True,
                'encontrado': True,
                'vigente': vigente,
                'pendiente_pago': pendiente_pago,
                'nombre': socio.nombre,
                'apellido': socio.apellido,
                'tipo_mensualidad': tipo_mens.tipo if tipo_mens else 'Sin mensualidad',
                'categoria': tipo_mens.categoria.nombre if tipo_mens and tipo_mens.categoria else '',
                'clases_restantes': socio.clases_restantes,
                'fecha_vencimiento': socio.fecha_vencimiento.isoformat() if socio.fecha_vencimiento else None,
                'dias_restantes': dias_restantes,
                'mes_vencido': mes_vencido,
                'es_plan_clases': es_plan_clases,
                'usa_contador_clases': usa_contador_clases,
                'frecuencia': tipo_mens.frecuencia if tipo_mens else None,
                'mensaje_vigencia': mensaje_vigencia,
                'usa_turnos': turno_kiosk.get('usa_turnos', False),
                'turnos_hoy': turno_kiosk.get('turnos_hoy', []),
                'tiene_turno_hoy': turno_kiosk.get('tiene_turno_hoy', False),
            })
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido', 'ok': False}, status=400)
    return JsonResponse({'error': 'Método no permitido'}, status=405)


@login_required
def pantalla_ingreso(request):
    """Página que abre la pantalla de ingreso en nueva ventana."""
    return render(request, 'pantalla_ingreso.html')


def pantalla_ingreso_kiosk(request):
    """Vista fullscreen para kiosco: ingreso por DNI con cartel de bienvenida. Sin login para uso en pantalla dedicada."""
    gym_id = request.GET.get('gym')
    return render(request, 'pantalla_ingreso_kiosk.html', {'gimnasio_id': gym_id or ''})