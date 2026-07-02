import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from .forms_puerta import ConfiguracionPuertaForm
from .models import ConfiguracionPuerta
from .puerta_utils import agente_json_local, datos_puerta_api, obtener_config_puerta
from .views import get_gimnasio_actual


@login_required
def configuracion_puerta(request):
    gym = get_gimnasio_actual(request)
    if not gym:
        return redirect('gimnasio_lista')

    config = obtener_config_puerta(gym)
    if request.method == 'POST':
        if request.POST.get('accion') == 'regenerar_token':
            config.regenerar_token()
            messages.success(request, 'Token renovado. Descargá de nuevo el archivo para la PC de ingreso.')
            return redirect('configuracion_puerta')

        form = ConfiguracionPuertaForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configuración de puerta guardada.')
            return redirect('configuracion_puerta')
    else:
        form = ConfiguracionPuertaForm(instance=config)

    return render(request, 'configuracion_puerta.html', {
        'form': form,
        'gimnasio': gym,
        'config': config,
        'gimnasio_actual': gym,
    })


@login_required
def descargar_agente_puerta_json(request):
    gym = get_gimnasio_actual(request)
    if not gym:
        return redirect('gimnasio_lista')
    config = obtener_config_puerta(gym)
    payload = agente_json_local(request, gym, config)
    content = json.dumps(payload, indent=2, ensure_ascii=False)
    response = HttpResponse(content, content_type='application/json; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="door.local.json"'
    return response


@csrf_exempt
@require_GET
def api_puerta_agente_config(request):
    """El agente en la PC de ingreso obtiene la config desde acá (sin .env)."""
    gimnasio_id = request.GET.get('gimnasio_id')
    token = (request.headers.get('X-Gym-Door-Token') or request.GET.get('token') or '').strip()
    if not gimnasio_id or not token:
        return JsonResponse({'ok': False, 'error': 'gimnasio_id y token requeridos'}, status=400)
    try:
        config = ConfiguracionPuerta.objects.select_related('gimnasio').get(
            gimnasio_id=int(gimnasio_id),
            token_agente=token,
        )
    except (ValueError, ConfiguracionPuerta.DoesNotExist):
        return JsonResponse({'ok': False, 'error': 'Configuración no encontrada'}, status=403)

    return JsonResponse({
        'ok': True,
        'gimnasio': config.gimnasio.nombre or config.gimnasio.direccion,
        'config': datos_puerta_api(config),
    })
