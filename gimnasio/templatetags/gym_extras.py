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
def categoria_socio(socio):
    """Nombre de la categoría de actividad del socio (crossfit, pesas, etc.)."""
    tm = getattr(socio, 'tipo_mensualidad', None)
    if not tm:
        return '-'
    cat = getattr(tm, 'categoria', None)
    return cat.nombre if cat else '-'


@register.filter
def etiqueta_plan_socio(socio):
    """Texto del plan en listados: distingue pase libre, por clases y frecuencias semanales."""
    tm = getattr(socio, 'tipo_mensualidad', None)
    if not tm:
        return '-'
    pagado = getattr(socio, 'tiene_cuota', False)
    if tm.frecuencia == 'clases':
        incluidas = tm.clases_incluidas or 0
        if pagado and socio.clases_restantes is not None:
            return f'{socio.clases_restantes} clases'
        if incluidas:
            return f'{incluidas} clases (pendiente de pago)'
        return tm.tipo or 'Por clases'
    if tm.frecuencia == 'pase_libre':
        if pagado:
            return 'Pase libre'
        return 'Pase libre (pendiente de pago)'
    label = tm.get_frecuencia_display() or tm.tipo or '-'
    if not pagado:
        return f'{label} (pendiente de pago)'
    return label


@register.filter
def badge_plan_socio(socio):
    """Clase Bootstrap para el badge del plan."""
    tm = getattr(socio, 'tipo_mensualidad', None)
    if not tm:
        return 'text-muted'
    pagado = getattr(socio, 'tiene_cuota', False)
    if not pagado:
        return 'bg-warning text-dark'
    if tm.frecuencia == 'clases' and (socio.clases_restantes or 0) > 0:
        return 'bg-info'
    return 'bg-secondary'
