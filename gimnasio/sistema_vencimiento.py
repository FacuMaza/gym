"""Vencimiento mensual: aviso del 1 al 10; control de pago el día 10 a las 23:59 (Argentina)."""

from datetime import datetime
from zoneinfo import ZoneInfo

TZ_ARGENTINA = ZoneInfo('America/Argentina/Buenos_Aires')
DIA_AVISO_HASTA = 10
HORA_CONTROL = 23
MINUTO_CONTROL = 59


def ahora_argentina():
    return datetime.now(TZ_ARGENTINA)


def referencia_periodo(ahora=None):
    """Mes de facturación en curso."""
    ahora = ahora or ahora_argentina()
    return ahora.replace(
        day=DIA_AVISO_HASTA, hour=0, minute=0, second=0, microsecond=0,
    )


def instante_control_pago(ahora=None):
    """Control del día 10 a las 23:59:00 hora Argentina."""
    ahora = ahora or ahora_argentina()
    return ahora.replace(
        day=DIA_AVISO_HASTA, hour=HORA_CONTROL, minute=MINUTO_CONTROL,
        second=0, microsecond=0,
    )


def vencimiento_periodo_vigente():
    return referencia_periodo()


def _periodo_key(ref):
    return f'{ref.year}-{ref.month:02d}'


def periodos_pagados_set(periodos_pagados):
    if not periodos_pagados:
        return set()
    return {p for p in periodos_pagados.split(',') if p}


def periodo_esta_pagado(periodos_pagados, ref):
    return _periodo_key(ref) in periodos_pagados_set(periodos_pagados)


def periodo_actual_pagado(periodos_pagados):
    return periodo_esta_pagado(periodos_pagados, referencia_periodo())


def debe_pausar_por_vencimiento(periodos_pagados):
    """A las 23:59 del día 10: IMPAGO → pausa, PAGADO → sigue activo."""
    ahora = ahora_argentina()
    if ahora < instante_control_pago(ahora):
        return False
    return not periodo_esta_pagado(periodos_pagados, referencia_periodo(ahora))


def proximo_instante_pausa():
    ahora = ahora_argentina()
    control = instante_control_pago(ahora)
    if ahora >= control:
        mes, anio = control.month + 1, control.year
        if mes > 12:
            mes, anio = 1, anio + 1
        control = control.replace(year=anio, month=mes)
    return control


def debe_mostrar_aviso_vencimiento():
    return 1 <= ahora_argentina().day <= DIA_AVISO_HASTA


def info_vencimiento_sistema():
    control = proximo_instante_pausa()
    return {
        'fecha_hora': control.strftime('%d/%m/%Y %H:%M'),
        'iso': control.isoformat(),
    }
