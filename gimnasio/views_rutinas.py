from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms_rutinas import EjercicioRutinaFormSet, ProgramacionEnvioForm, RutinaForm
from .models import ProgramacionEnvio, Rutina
from .socio_portal_utils import publicar_rutina
from .views import get_gimnasio_actual


@login_required
def rutinas_lista(request):
    gym = get_gimnasio_actual(request)
    if not gym:
        return redirect('gimnasio_lista')
    rutinas = Rutina.objects.filter(gimnasio=gym).select_related('categoria').prefetch_related('ejercicios')
    return render(request, 'rutinas/lista.html', {
        'rutinas': rutinas,
        'gimnasio_actual': gym,
    })


@login_required
def rutina_crear(request):
    gym = get_gimnasio_actual(request)
    if not gym:
        return redirect('gimnasio_lista')
    if request.method == 'POST':
        form = RutinaForm(request.POST, gimnasio=gym)
        formset = EjercicioRutinaFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            rutina = form.save(commit=False)
            rutina.gimnasio = gym
            rutina.save()
            formset.instance = rutina
            formset.save()
            messages.success(request, 'Rutina creada.')
            return redirect('rutinas_lista')
    else:
        form = RutinaForm(gimnasio=gym)
        formset = EjercicioRutinaFormSet()
    return render(request, 'rutinas/form_rutina.html', {
        'form': form,
        'formset': formset,
        'titulo_pagina': 'Nueva rutina',
        'gimnasio_actual': gym,
    })


@login_required
def rutina_editar(request, pk):
    gym = get_gimnasio_actual(request)
    rutina = get_object_or_404(Rutina, pk=pk, gimnasio=gym) if gym else get_object_or_404(Rutina, pk=pk)
    if request.method == 'POST':
        form = RutinaForm(request.POST, instance=rutina, gimnasio=gym)
        formset = EjercicioRutinaFormSet(request.POST, instance=rutina)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'Rutina actualizada.')
            return redirect('rutinas_lista')
    else:
        form = RutinaForm(instance=rutina, gimnasio=gym)
        formset = EjercicioRutinaFormSet(instance=rutina)
    return render(request, 'rutinas/form_rutina.html', {
        'form': form,
        'formset': formset,
        'titulo_pagina': 'Editar rutina',
        'rutina': rutina,
        'gimnasio_actual': gym,
    })


@login_required
def rutina_eliminar(request, pk):
    gym = get_gimnasio_actual(request)
    rutina = get_object_or_404(Rutina, pk=pk, gimnasio=gym) if gym else get_object_or_404(Rutina, pk=pk)
    if request.method == 'POST':
        rutina.delete()
        messages.success(request, 'Rutina eliminada.')
        return redirect('rutinas_lista')
    return render(request, 'rutinas/eliminar_rutina.html', {'rutina': rutina})


@login_required
def rutina_enviar(request, pk):
    gym = get_gimnasio_actual(request)
    rutina = get_object_or_404(Rutina, pk=pk, gimnasio=gym) if gym else get_object_or_404(Rutina, pk=pk)
    if request.method == 'POST':
        n = publicar_rutina(rutina)
        messages.success(request, f'Rutina publicada en {n} cuenta(s) de socio.')
        return redirect('rutinas_lista')
    return render(request, 'rutinas/enviar_rutina.html', {'rutina': rutina})


@login_required
def envios_lista(request):
    gym = get_gimnasio_actual(request)
    if not gym:
        return redirect('gimnasio_lista')
    programaciones = ProgramacionEnvio.objects.filter(gimnasio=gym).select_related('rutina', 'rutina__categoria')
    return render(request, 'rutinas/envios_lista.html', {
        'programaciones': programaciones,
        'gimnasio_actual': gym,
    })


@login_required
def envio_crear(request):
    gym = get_gimnasio_actual(request)
    if not gym:
        return redirect('gimnasio_lista')
    if request.method == 'POST':
        form = ProgramacionEnvioForm(request.POST, gimnasio=gym)
        if form.is_valid():
            prog = form.save(commit=False)
            prog.gimnasio = gym
            prog.save()
            messages.success(request, 'Programación creada.')
            return redirect('envios_lista')
    else:
        form = ProgramacionEnvioForm(gimnasio=gym)
    return render(request, 'rutinas/form_envio.html', {
        'form': form,
        'titulo_pagina': 'Nueva programación',
        'gimnasio_actual': gym,
    })


@login_required
def envio_editar(request, pk):
    gym = get_gimnasio_actual(request)
    prog = get_object_or_404(ProgramacionEnvio, pk=pk, gimnasio=gym) if gym else get_object_or_404(ProgramacionEnvio, pk=pk)
    if request.method == 'POST':
        form = ProgramacionEnvioForm(request.POST, instance=prog, gimnasio=gym)
        if form.is_valid():
            form.save()
            messages.success(request, 'Programación actualizada.')
            return redirect('envios_lista')
    else:
        form = ProgramacionEnvioForm(instance=prog, gimnasio=gym)
    return render(request, 'rutinas/form_envio.html', {
        'form': form,
        'titulo_pagina': 'Editar programación',
        'programacion': prog,
        'gimnasio_actual': gym,
    })


@login_required
def envio_enviar(request, pk):
    gym = get_gimnasio_actual(request)
    prog = get_object_or_404(ProgramacionEnvio, pk=pk, gimnasio=gym) if gym else get_object_or_404(ProgramacionEnvio, pk=pk)
    if request.method == 'POST':
        n = publicar_rutina(prog.rutina, programacion=prog)
        from datetime import date
        prog.ultimo_envio = date.today()
        prog.save(update_fields=['ultimo_envio'])
        messages.success(request, f'Rutina publicada en {n} cuenta(s) de socio.')
        return redirect('envios_lista')
    return render(request, 'rutinas/enviar_programacion.html', {'programacion': prog})
