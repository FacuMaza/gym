"""Traducciones ES para metadatos del catálogo ExerciseGymGifsDB (slugs en inglés)."""

from __future__ import annotations

# slug (EN) -> etiqueta visible + alias para búsqueda en español
TERMINOS_CATALOGO: dict[str, dict] = {
    # Músculos
    'abductors': {'label': 'Abductores', 'aliases': ['abductor', 'abduccion']},
    'abs': {'label': 'Abdominales', 'aliases': ['abdomen', 'abdominal', 'core', 'abs']},
    'adductors': {'label': 'Aductores', 'aliases': ['aductor', 'aduccion', 'ingle']},
    'biceps': {'label': 'Bíceps', 'aliases': ['bicep', 'brazo']},
    'calves': {'label': 'Pantorrillas', 'aliases': ['pantorrilla', 'gemelos', 'gemelo', 'pantorrilla']},
    'cardio': {'label': 'Cardio', 'aliases': ['cardiovascular', 'aerobico']},
    'delts': {'label': 'Deltoides', 'aliases': ['deltoides', 'hombro', 'hombros']},
    'forearms': {'label': 'Antebrazos', 'aliases': ['antebrazo', 'muneca', 'munecas']},
    'glutes': {'label': 'Glúteos', 'aliases': ['gluteos', 'gluteo', 'glúteo', 'gluteo']},
    'hamstrings': {'label': 'Isquiotibiales', 'aliases': ['isquio', 'isquios', 'femoral', 'femorales']},
    'lats': {'label': 'Dorsales', 'aliases': ['dorsal', 'latissimus']},
    'levator-scapulae': {'label': 'Elevador de la escápula', 'aliases': ['escapula', 'cuello']},
    'pectorals': {'label': 'Pectorales', 'aliases': ['pectoral', 'pecho', 'pectorales']},
    'quads': {'label': 'Cuádriceps', 'aliases': ['cuadriceps', 'cuadricipital', 'muslo']},
    'serratus-anterior': {'label': 'Serrato anterior', 'aliases': ['serrato']},
    'spine': {'label': 'Columna', 'aliases': ['espina', 'lumbar', 'lumbares']},
    'traps': {'label': 'Trapecios', 'aliases': ['trapecio', 'cuello']},
    'triceps': {'label': 'Tríceps', 'aliases': ['tricep']},
    'upper-back': {'label': 'Espalda alta', 'aliases': ['espalda alta', 'espalda', 'dorsal alto']},
    # Partes del cuerpo
    'arms': {'label': 'Brazos', 'aliases': ['brazo', 'brazos']},
    'back': {'label': 'Espalda', 'aliases': ['espalda', 'dorsal']},
    'chest': {'label': 'Pecho', 'aliases': ['pecho', 'torax', 'tórax']},
    'core': {'label': 'Core', 'aliases': ['abdomen', 'abdominal', 'centro']},
    'legs': {'label': 'Piernas', 'aliases': ['pierna', 'piernas', 'tren inferior']},
    'shoulders': {'label': 'Hombros', 'aliases': ['hombro', 'hombros', 'deltoide']},
    # Equipamiento
    'band': {'label': 'Banda elástica', 'aliases': ['banda', 'elastico', 'elástica', 'resistencia']},
    'barbell': {'label': 'Barra', 'aliases': ['barra', 'barra olimpica', 'barra olímpica']},
    'bodyweight': {'label': 'Peso corporal', 'aliases': ['corporal', 'sin equipo', 'peso propio']},
    'cable': {'label': 'Polea', 'aliases': ['polea', 'cables', 'cable']},
    'dumbbell': {'label': 'Mancuerna', 'aliases': ['mancuerna', 'mancuernas', 'pesa']},
    'ez-bar': {'label': 'Barra EZ', 'aliases': ['barra ez', 'barra z']},
    'kettlebell': {'label': 'Kettlebell', 'aliases': ['pesa rusa', 'kettle']},
    'lever': {'label': 'Máquina de palanca', 'aliases': ['palanca', 'lever']},
    'machine': {'label': 'Máquina', 'aliases': ['maquina', 'máquina', 'aparato']},
    'other': {'label': 'Otro', 'aliases': ['otro', 'otros']},
    'sled': {'label': 'Trineo', 'aliases': ['trineo', 'prowler']},
    'smith': {'label': 'Máquina Smith', 'aliases': ['smith', 'multipower']},
    # Categoría de ejercicio
    'plyometrics': {'label': 'Pliometría', 'aliases': ['pliometria', 'explosivo', 'salto']},
    'strength': {'label': 'Fuerza', 'aliases': ['fuerza', 'musculacion', 'musculación']},
    'stretching': {'label': 'Estiramiento', 'aliases': ['estiramiento', 'flexibilidad', 'stretch']},
}


def _normalizar(texto: str) -> str:
    return (
        texto.lower()
        .replace('á', 'a')
        .replace('é', 'e')
        .replace('í', 'i')
        .replace('ó', 'o')
        .replace('ú', 'u')
        .replace('ü', 'u')
        .strip()
    )


def traducir_termino_catalogo(slug: str) -> str:
    """Devuelve la etiqueta en español; si no hay traducción, humaniza el slug."""
    if not slug:
        return ''
    info = TERMINOS_CATALOGO.get(slug)
    if info:
        return info['label']
    return slug.replace('-', ' ').replace('_', ' ').title()


def slugs_para_termino(termino: str) -> set[str]:
    """Slugs EN que coinciden con una búsqueda en español (pecho → pectorals, chest)."""
    t = _normalizar(termino)
    if not t:
        return set()
    found: set[str] = set()
    for slug, info in TERMINOS_CATALOGO.items():
        slug_norm = _normalizar(slug)
        if t in slug_norm or slug_norm in t:
            found.add(slug)
        label_norm = _normalizar(info['label'])
        if t in label_norm or label_norm in t:
            found.add(slug)
        for alias in info.get('aliases', []):
            alias_norm = _normalizar(alias)
            if t in alias_norm or alias_norm in t:
                found.add(slug)
    return found


def etiquetas_ejercicio_catalogo(ejercicio) -> dict[str, str]:
    """Etiquetas en español para mostrar en la UI."""
    return {
        'musculo': traducir_termino_catalogo(ejercicio.musculo),
        'parte_cuerpo': traducir_termino_catalogo(ejercicio.parte_cuerpo),
        'equipo': traducir_termino_catalogo(ejercicio.equipo),
        'categoria': traducir_termino_catalogo(ejercicio.categoria),
    }
