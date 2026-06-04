from django import template

register = template.Library()


def _format_ar(value, decimales=2):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return '0,00' if decimales else '0'
    try:
        d = int(decimales)
    except (TypeError, ValueError):
        d = 2
    neg = n < 0
    n = abs(n)
    if d <= 0:
        entero_fmt = f'{int(round(n)):,}'.replace(',', '.')
        return f'-{entero_fmt}' if neg else entero_fmt
    entero, dec = f'{n:.{d}f}'.split('.')
    entero_fmt = f'{int(entero):,}'.replace(',', '.')
    if neg:
        entero_fmt = f'-{entero_fmt}'
    return f'{entero_fmt},{dec}'


@register.filter
def moneda_ar(value, decimales=2):
    """Formato argentino: 1.234,56 (decimales=0 para montos sin centavos)."""
    return _format_ar(value, decimales)


@register.filter
def etiqueta_plan_socio(socio):
    """Texto del plan en listados: distingue pase libre, por clases y frecuencias semanales."""
    tm = getattr(socio, 'tipo_mensualidad', None)
    if not tm:
        return '-'
    if tm.frecuencia == 'clases':
        incluidas = tm.clases_incluidas or 0
        pagado = getattr(socio, 'tiene_cuota', False)
        if pagado and socio.clases_restantes is not None:
            return f'{socio.clases_restantes} clases'
        if incluidas:
            return f'{incluidas} clases (pendiente de pago)'
        return tm.tipo or 'Por clases'
    if tm.frecuencia == 'pase_libre':
        return 'Pase libre'
    return tm.get_frecuencia_display() or tm.tipo or '-'


@register.filter
def badge_plan_socio(socio):
    """Clase Bootstrap para el badge del plan."""
    tm = getattr(socio, 'tipo_mensualidad', None)
    if not tm:
        return 'text-muted'
    if tm.frecuencia == 'clases':
        pagado = getattr(socio, 'tiene_cuota', False)
        if pagado and (socio.clases_restantes or 0) > 0:
            return 'bg-info'
        return 'bg-warning text-dark'
    return 'bg-secondary'
