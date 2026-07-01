"""Importación del catálogo ExerciseGymGifsDB (español + GIF)."""
import json
import re
import urllib.error
import urllib.request
from typing import Iterator

CDN_BASE = 'https://cdn.jsdelivr.net/gh/JahelCuadrado/ExerciseGymGifsDB@v1.1.0'
API_ES = f'{CDN_BASE}/api/es'


def _fetch_json(url: str, timeout: int = 90) -> object:
    req = urllib.request.Request(url, headers={'User-Agent': 'GYM-PRO/1.0'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def _slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r'[^a-z0-9]+', '-', value)
    return value.strip('-') or 'ejercicio'


def _muscle_slugs(muscles_payload) -> list[str]:
    if isinstance(muscles_payload, list):
        slugs = []
        for item in muscles_payload:
            if isinstance(item, str):
                slugs.append(item)
            elif isinstance(item, dict):
                slug = item.get('slug') or item.get('id') or item.get('muscle')
                if slug:
                    slugs.append(str(slug))
        return slugs
    if isinstance(muscles_payload, dict):
        if 'muscles' in muscles_payload:
            return _muscle_slugs(muscles_payload['muscles'])
        return list(muscles_payload.keys())
    return []


def _exercises_from_payload(payload) -> list[dict]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ('exercises', 'items', 'data'):
            if key in payload and isinstance(payload[key], list):
                return payload[key]
    return []


def _normalize_exercise(muscle_slug: str, raw: dict) -> dict | None:
    slug = raw.get('slug') or raw.get('id')
    file_path = raw.get('file') or ''
    if not slug and file_path:
        slug = file_path.split('/')[-1].replace('.gif', '')
    if not slug:
        name_for_slug = raw.get('nameEs') or raw.get('name') or raw.get('name_en')
        if not name_for_slug:
            return None
        slug = _slugify(str(name_for_slug))

    clave = raw.get('key') or raw.get('file', '').replace('.gif', '') or f'{muscle_slug}/{slug}'
    clave = clave.replace('\\', '/').strip('/')

    nombre = (
        raw.get('nameEs')
        or raw.get('name_es')
        or raw.get('nombre')
        or raw.get('name')
        or slug.replace('-', ' ').title()
    )
    nombre_en = raw.get('name') or raw.get('nameEn') or raw.get('name_en') or ''

    gif_url = raw.get('gifUrl') or raw.get('gif_url') or ''
    if not gif_url and file_path:
        gif_url = f'{CDN_BASE}/{file_path.lstrip("/")}'
    if not gif_url:
        gif_url = f'{CDN_BASE}/{clave}.gif'

    instrucciones = raw.get('instructions') or raw.get('instrucciones') or []
    if isinstance(instrucciones, str):
        instrucciones = [instrucciones]

    return {
        'clave': clave,
        'slug': _slugify(clave.replace('/', '-')),
        'nombre': str(nombre).strip(),
        'nombre_en': str(nombre_en).strip(),
        'musculo': str(raw.get('muscle') or raw.get('muscleGroup') or muscle_slug or '').strip(),
        'parte_cuerpo': str(raw.get('bodyPart') or raw.get('body_part') or '').strip(),
        'equipo': str(raw.get('equipment') or raw.get('equipo') or '').strip(),
        'categoria': str(raw.get('category') or raw.get('categoria') or '').strip(),
        'instrucciones': instrucciones,
        'gif_url': gif_url,
    }


def iter_catalogo_desde_api(lang: str = 'es') -> Iterator[dict]:
    """Recorre todos los ejercicios del dataset remoto."""
    api_base = f'{CDN_BASE}/api/{lang}'
    muscles_payload = _fetch_json(f'{api_base}/muscles.json')
    for muscle_slug in _muscle_slugs(muscles_payload):
        try:
            muscle_data = _fetch_json(f'{api_base}/muscles/{muscle_slug}.json')
        except urllib.error.HTTPError:
            continue
        for raw in _exercises_from_payload(muscle_data):
            if not isinstance(raw, dict):
                continue
            normalized = _normalize_exercise(muscle_slug, raw)
            if normalized and normalized.get('nombre'):
                yield normalized
