"""Structured offline search. Missing energy is never invented or silently matched."""
import math
import re
import unicodedata
from .models import PlanningError


def normalized_genre(text):
    text = ''.join(c for c in unicodedata.normalize('NFD', text.casefold()) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]', '', text)


def validate_search(intent):
    if any(not isinstance(v, str) or len(v) > 500 for v in (intent.query, intent.genre, intent.key)):
        raise PlanningError('Texto de búsqueda inválido.')
    if type(intent.limit) is not int or not 1 <= intent.limit <= 100 or type(intent.offset) is not int or not 0 <= intent.offset <= 1000000:
        raise PlanningError('Paginación de búsqueda inválida.')
    for low, high, maximum, label in ((intent.bpm_min, intent.bpm_max, 400, 'BPM'),
                                     (intent.energy_min, intent.energy_max, 10, 'energía')):
        for value in (low, high):
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= maximum):
                raise PlanningError(f'Filtro de {label} inválido.')
        if low is not None and high is not None and low > high:
            raise PlanningError(f'Rango de {label} invertido.')
    if intent.key and not re.fullmatch(r'(?:[1-9]|1[0-2])[AB]', intent.key.upper()):
        raise PlanningError('Indicá una tonalidad Camelot de 1A a 12B.')


def search_library(lib, intent):
    validate_search(intent)
    genre, query, key = normalized_genre(intent.genre), intent.query.strip().casefold(), intent.key.upper()
    base = []
    for track in lib.tracks.values():
        if query and query not in f'{track.title} {track.artist} {track.genre}'.casefold() and normalized_genre(query) != normalized_genre(track.genre): continue
        if genre and normalized_genre(track.genre) != genre: continue
        if key and track.key != key: continue
        if intent.bpm_min is not None and (track.bpm is None or track.bpm < intent.bpm_min): continue
        if intent.bpm_max is not None and (track.bpm is None or track.bpm > intent.bpm_max): continue
        base.append(track)
    wants_energy = intent.energy_min is not None or intent.energy_max is not None
    missing_energy = [t for t in base if t.energy is None or not t.energy_source] if wants_energy else []
    found = [t for t in base if not wants_energy or (t.energy is not None and t.energy_source
             and (intent.energy_min is None or t.energy >= intent.energy_min)
             and (intent.energy_max is None or t.energy <= intent.energy_max))]
    if wants_energy: found.sort(key=lambda t: (-t.energy, t.id))
    selected = found[intent.offset:intent.offset + intent.limit]
    alternatives = missing_energy[:intent.limit] if wants_energy and not found else []
    filters = {k: getattr(intent, k) for k in ('genre', 'bpm_min', 'bpm_max', 'key', 'energy_min', 'energy_max')
               if getattr(intent, k) not in (None, '')}
    return {'tracks': [vars(t) for t in selected], 'total': len(found), 'filters': filters,
            'missing_energy_count': len(missing_energy), 'alternatives': [vars(t) for t in alternatives],
            'source_revision': lib.revision}
