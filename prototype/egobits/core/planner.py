from __future__ import annotations
import math
import re
from typing import Any
from .models import Track, PlanOptions, PlanningError

_KEYS = {
    'abm': '1A', 'g#m': '1A', 'ebm': '2A', 'd#m': '2A', 'bbm': '3A', 'a#m': '3A',
    'fm': '4A', 'cm': '5A', 'gm': '6A', 'dm': '7A', 'am': '8A', 'em': '9A',
    'bm': '10A', 'f#m': '11A', 'gbm': '11A', 'c#m': '12A', 'dbm': '12A',
    'b': '1B', 'cb': '1B', 'f#': '2B', 'gb': '2B', 'db': '3B', 'c#': '3B',
    'ab': '4B', 'g#': '4B', 'eb': '5B', 'd#': '5B', 'bb': '6B', 'a#': '6B',
    'f': '7B', 'c': '8B', 'g': '9B', 'd': '10B', 'a': '11B', 'e': '12B'
}

def normalize_key(raw: str | None) -> str | None:
    """Normaliza notaciones tradicionales y Camelot a formato Camelot estándar (1A..12B)."""
    s = (raw or '').strip()
    if not s:
        return None
    if re.fullmatch(r'(?:[1-9]|1[0-2])[ABab]', s):
        return s.upper()
    s = s.lower().replace('♯', '#').replace('♭', 'b')
    s = re.sub(r'\s*(minor|min)$', 'm', s)
    s = re.sub(r'\s*(major|maj)$', '', s)
    return _KEYS.get(s.replace(' ', ''))

def harmonic_score(a: str | None, b: str | None) -> float | None:
    """Calcula compatibilidad armónica heurística según la rueda de Camelot.
    1.0 = Misma tonalidad
    0.9 = Relativo mayor/menor (mismo número, diferente letra)
    0.85 = Vecino armónico adyacente (+1 o -1 en rueda)
    0.0 = Salto armónico no adyacente
    None = Al menos una tonalidad es desconocida
    """
    a_norm, b_norm = normalize_key(a), normalize_key(b)
    if not a_norm or not b_norm:
        return None
    na, nb = int(a_norm[:-1]), int(b_norm[:-1])
    if a_norm == b_norm:
        return 1.0
    if na == nb:
        return 0.9
    if a_norm[-1] == b_norm[-1] and (na - nb) % 12 in (1, 11):
        return 0.85
    return 0.0

def number(raw: str | float | None, *, minimum: float = 0) -> float | None:
    if raw is None or raw == '':
        return None
    try:
        x = float(raw)
    except (ValueError, TypeError):
        return None
    return x if math.isfinite(x) and x > minimum else None

def plan(tracks: list[Track], opt: PlanOptions) -> dict[str, Any]:
    """Genera una secuencia ordenada con restricciones deterministas (BPM o Energía).
    Nunca relaja restricciones en silencio; reporta exclusiones con causa exacta.
    """
    # Deduplicación por id conservando orden
    unique_tracks = list({t.id: t for t in tracks}.values())
    excluded: dict[str, str] = {}
    valid: list[Track] = []

    for t in unique_tracks:
        reason = None
        if t.bpm is None:
            reason = 'BPM desconocido'
        elif opt.mode == 'energy' and t.energy is None:
            reason = 'Energía desconocida'
        elif opt.harmonic and not t.key:
            reason = 'Tonalidad desconocida'
        elif opt.same_genre and not t.genre:
            reason = 'Género desconocido'

        if reason:
            excluded[t.id] = reason
        else:
            valid.append(t)

    if len(valid) < opt.count:
        raise PlanningError(
            f'Candidatos válidos insuficientes: {len(valid)}; pedidos: {opt.count}; exclusiones: {excluded}'
        )
    if len(valid) > 1000:
        raise PlanningError('Acotá el conjunto a 1000 pistas para este prototipo')

    def axis(t: Track) -> float:
        val = t.bpm if opt.mode == 'bpm' else t.energy
        return val if val is not None else 0.0

    valid.sort(key=lambda t: (axis(t), t.id))
    lo, hi = axis(valid[0]), axis(valid[-1])
    span = max(hi - lo, 1.0)
    beams: list[tuple[float, tuple[Track, ...]]] = [(0.0, tuple())]

    for pos in range(opt.count):
        target = lo + (hi - lo) * pos / max(opt.count - 1, 1)
        next_beams: list[tuple[float, tuple[Track, ...]]] = []
        for score, path in beams:
            used = {t.id for t in path}
            prev = path[-1] if path else None
            for t in valid:
                if t.id in used:
                    continue
                hs: float | None = None
                if prev:
                    # En modo bpm o energy, el eje debe ser monótonamente no decreciente
                    if axis(t) < axis(prev):
                        continue
                    if abs((t.bpm or 0) - (prev.bpm or 0)) > opt.max_bpm_step:
                        continue
                    if opt.avoid_adjacent_artist and t.artist and prev.artist and t.artist.casefold() == prev.artist.casefold():
                        continue
                    if opt.same_genre and t.genre != prev.genre:
                        continue
                    hs = harmonic_score(prev.key, t.key)
                    if opt.harmonic and (hs is None or hs == 0):
                        continue
                s = score - abs(axis(t) - target) / span + (0.25 * (hs or 0) if prev else 0)
                next_beams.append((s, path + (t,)))
        if not next_beams:
            raise PlanningError(
                'No se encontró una secuencia completa con esta búsqueda limitada; no se relajaron las restricciones. Ampliá el conjunto o cambiá una condición.'
            )
        next_beams.sort(key=lambda x: (-x[0], tuple(t.id for t in x[1])))
        beams = next_beams[:opt.beam_width]

    score, chosen = beams[0]
    transitions = []
    for a, b in zip(chosen, chosen[1:]):
        transitions.append({
            'from': a.id,
            'to': b.id,
            'bpm_delta': round((b.bpm or 0) - (a.bpm or 0), 3),
            'harmonic': harmonic_score(a.key, b.key),
            'energy_delta': None if a.energy is None or b.energy is None else round(b.energy - a.energy, 3)
        })
    durations = [t.duration for t in chosen]
    return {
        'track_ids': [t.id for t in chosen],
        'mode': opt.mode,
        'score': round(score, 4),
        'transitions': transitions,
        'excluded': excluded,
        'algorithm': 'bounded_beam_v1',
        'duration_sum_seconds': sum(durations) if all(x is not None for x in durations) else None,
        'warnings': [
            'La duración suma pistas completas; no calcula solapamientos.',
            'La compatibilidad armónica es una regla de selección, no una garantía perceptual.'
        ],
        'tracks': [vars(t) for t in chosen]
    }
