from __future__ import annotations
import math
import re
import heapq
from collections import Counter
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
        elif opt.mode == 'energy' and (t.energy is None or not t.energy_source):
            reason = 'Energía desconocida'
        elif opt.harmonic and not t.key:
            reason = 'Tonalidad desconocida'
        elif opt.same_genre and not t.genre:
            reason = 'Género desconocido'

        if reason:
            excluded[t.id] = reason
        else:
            valid.append(t)

    target_count = opt.count if opt.count is not None else len(valid)
    adjustments: list[str] = []

    if len(valid) < target_count:
        if not opt.allow_insufficient:
            raise PlanningError(
                f'Candidatos válidos insuficientes: {len(valid)}; pedidos: {target_count}; exclusiones: {dict(Counter(excluded.values()))}'
            )
        if len(valid) < target_count and (opt.harmonic or opt.same_genre):
            recoverable = []
            for t in unique_tracks:
                if t.id not in {v.id for v in valid}:
                    if t.bpm is not None and (opt.mode != 'energy' or (t.energy is not None and t.energy_source)):
                        recoverable.append(t)
            if recoverable:
                to_add = recoverable[:target_count - len(valid)]
                valid.extend(to_add)
                for t in to_add:
                    excluded.pop(t.id, None)
                adjustments.append(
                    f'Se incluyeron {len(to_add)} pistas con metadatos parciales para alcanzar la cantidad pedida.'
                )

        if len(valid) == 0:
            raise PlanningError('No hay candidatos válidos disponibles para planificar.')

        if len(valid) < target_count:
            adjustments.append(
                f'Candidatos insuficientes: se solicitaron {target_count} pistas, pero solo había {len(valid)} disponibles en las fuentes seleccionadas. Se acomodaron las {len(valid)} pistas disponibles.'
            )
            target_count = len(valid)

    def axis(t: Track) -> float:
        val = t.bpm if opt.mode == 'bpm' else t.energy
        return val if val is not None else 0.0

    valid.sort(key=lambda t: (axis(t), t.id))
    candidate_total = len(valid)
    if candidate_total > 1000 and target_count <= 1000:
        # Representative deterministic positions across the complete valid axis.
        # This remains a bounded search and never relaxes a requested constraint.
        valid = [valid[i * (candidate_total - 1) // 999] for i in range(1000)]
    lo, hi = axis(valid[0]), axis(valid[-1])
    span = max(hi - lo, 1.0)
    beams: list[tuple[float, tuple[Track, ...]]] = [(0.0, tuple())]

    for pos in range(target_count):
        target = lo + (hi - lo) * pos / max(target_count - 1, 1)
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
            if not opt.allow_insufficient:
                raise PlanningError(
                    'No se encontró una secuencia completa con esta búsqueda limitada; no se relajaron las restricciones. Ampliá el conjunto o cambiá una condición.'
                )
            for score, path in beams:
                used = {t.id for t in path}
                prev = path[-1] if path else None
                remaining = [t for t in valid if t.id not in used]
                for t in remaining:
                    s = score - abs(axis(t) - target) / span
                    if prev:
                        hs = harmonic_score(prev.key, t.key)
                        if opt.harmonic:
                            if hs is not None and hs > 0:
                                s += 0.25 * hs
                            else:
                                s -= 5.0
                        if opt.avoid_adjacent_artist and t.artist and prev.artist and t.artist.casefold() == prev.artist.casefold():
                            s -= 10.0
                        if opt.same_genre and t.genre != prev.genre:
                            s -= 10.0
                        bpm_delta = abs((t.bpm or 0) - (prev.bpm or 0))
                        if bpm_delta > opt.max_bpm_step:
                            s -= 25.0 + 5.0 * (bpm_delta - opt.max_bpm_step)
                        if axis(t) < axis(prev):
                            s -= 50.0 + 10.0 * (axis(prev) - axis(t))
                    next_beams.append((s, path + (t,)))

        beams = heapq.nsmallest(opt.beam_width, next_beams, key=lambda x: (-x[0], tuple(t.id for t in x[1])))

    score, chosen = beams[0]
    transitions = []
    for i, (a, b) in enumerate(zip(chosen, chosen[1:]), start=1):
        hs = harmonic_score(a.key, b.key)
        bpm_delta = round((b.bpm or 0) - (a.bpm or 0), 3)
        transitions.append({
            'from': a.id,
            'to': b.id,
            'bpm_delta': bpm_delta,
            'harmonic': hs,
            'energy_delta': None if a.energy is None or b.energy is None else round(b.energy - a.energy, 3)
        })
        if opt.allow_insufficient:
            if axis(b) < axis(a):
                adjustments.append(
                    f'Transición #{i} -> #{i+1} («{a.title}» -> «{b.title}»): BPM no ascendente ({a.bpm} -> {b.bpm} BPM) para poder incorporar la pista al set.'
                )
            elif abs((b.bpm or 0) - (a.bpm or 0)) > opt.max_bpm_step:
                adjustments.append(
                    f'Transición #{i} -> #{i+1} («{a.title}» -> «{b.title}»): salto de BPM de {round(abs((b.bpm or 0) - (a.bpm or 0)), 1)} BPM supera el máximo de {opt.max_bpm_step} BPM.'
                )
            if opt.harmonic and (hs is None or hs == 0):
                adjustments.append(
                    f'Transición #{i} -> #{i+1} («{a.title}» -> «{b.title}»): salto armónico ({a.key or "sin clave"} -> {b.key or "sin clave"}) por falta de tonalidad Camelot adyacente.'
                )
            if opt.avoid_adjacent_artist and a.artist and b.artist and a.artist.casefold() == b.artist.casefold():
                adjustments.append(
                    f'Transición #{i} -> #{i+1}: artista repetido de forma consecutiva («{a.artist}»).'
                )
            if opt.same_genre and a.genre != b.genre:
                adjustments.append(
                    f'Transición #{i} -> #{i+1}: cambio de género («{a.genre or "desconocido"}» -> «{b.genre or "desconocido"}»).'
                )

    durations = [t.duration for t in chosen]
    warnings = (
        ([f'La colección tiene {candidate_total} candidatas válidas; se usó una preselección representativa de 1000. Una secuencia posible puede quedar fuera de esta búsqueda acotada.'] if candidate_total > 1000 and target_count <= 1000 else [])
        + adjustments
        + [
            'La duración suma pistas completas; no calcula solapamientos.',
            'La compatibilidad armónica es una regla de selección, no una garantía perceptual.'
        ]
    )
    return {
        'track_ids': [t.id for t in chosen],
        'mode': opt.mode,
        'score': round(score, 4),
        'transitions': transitions,
        'excluded': excluded,
        'adjustments': adjustments,
        'algorithm': 'bounded_beam_v2' if not adjustments else 'bounded_beam_flexible_v2',
        'candidate_total': candidate_total,
        'candidate_count': len(valid),
        'duration_sum_seconds': sum(durations) if all(x is not None for x in durations) else None,
        'warnings': warnings,
        'tracks': [vars(t) for t in chosen]
    }
