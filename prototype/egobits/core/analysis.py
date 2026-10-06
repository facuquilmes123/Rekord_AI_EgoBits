from __future__ import annotations
import math
from typing import Any
from .models import Track, PlanningError
from .planner import harmonic_score

def compare_playlists(tracks_a: list[Track], tracks_b: list[Track], name_a: str = 'A', name_b: str = 'B') -> dict[str, Any]:
    """Compara dos playlists identificando pistas comunes y exclusivas de cada una."""
    map_a = {t.id: t for t in tracks_a}
    map_b = {t.id: t for t in tracks_b}
    set_a = set(map_a.keys())
    set_b = set(map_b.keys())

    common_ids = sorted(set_a & set_b)
    only_a_ids = sorted(set_a - set_b)
    only_b_ids = sorted(set_b - set_a)

    return {
        'total_a': len(tracks_a),
        'total_b': len(tracks_b),
        'common_count': len(common_ids),
        'only_a_count': len(only_a_ids),
        'only_b_count': len(only_b_ids),
        'common_tracks': [vars(map_a[tid]) for tid in common_ids],
        'only_a_tracks': [vars(map_a[tid]) for tid in only_a_ids],
        'only_b_tracks': [vars(map_b[tid]) for tid in only_b_ids],
    }

def find_duplicates(tracks: list[Track]) -> list[dict[str, Any]]:
    """Encuentra posibles pistas duplicadas por coincidencia normalizada de título y artista."""
    groups: dict[str, list[Track]] = {}
    for t in tracks:
        key = f"{t.artist.strip().casefold()} - {t.title.strip().casefold()}"
        groups.setdefault(key, []).append(t)

    duplicates = []
    for key, items in groups.items():
        if len(items) > 1:
            duplicates.append({
                'signature': key,
                'count': len(items),
                'tracks': [vars(t) for t in items]
            })
    return duplicates

def audit_library(tracks: list[Track]) -> dict[str, Any]:
    """Audita metadatos de la colección: pistas sin BPM, sin Key, sin duración o formato atípico."""
    missing_bpm = []
    missing_key = []
    missing_duration = []
    invalid_locations = []

    for t in tracks:
        if t.bpm is None or t.bpm <= 0:
            missing_bpm.append(t.id)
        if not t.key:
            missing_key.append(t.id)
        if t.duration is None or t.duration <= 0:
            missing_duration.append(t.id)
        if not t.location.lower().startswith('file://localhost/'):
            invalid_locations.append(t.id)

    return {
        'total_tracks': len(tracks),
        'missing_bpm_count': len(missing_bpm),
        'missing_bpm_ids': missing_bpm,
        'missing_key_count': len(missing_key),
        'missing_key_ids': missing_key,
        'missing_duration_count': len(missing_duration),
        'missing_duration_ids': missing_duration,
        'invalid_location_count': len(invalid_locations),
        'invalid_location_ids': invalid_locations,
        'health_score': round(100.0 * (1.0 - (len(missing_bpm) + len(missing_key)) / max(len(tracks) * 2, 1)), 1)
    }

def audit_setlist(tracks: list[Track], max_bpm_step: float = 3.0) -> dict[str, Any]:
    """Audita un orden de setlist secuencial buscando saltos bruscos, choques de tono y repeticiones."""
    issues = []
    for track in tracks:
        missing = [label for label, value in (('BPM', track.bpm), ('tonalidad', track.key)) if value is None]
        if missing:
            issues.append({'type': 'missing_metadata', 'track_id': track.id,
                           'detail': 'No se puede validar: ' + ', '.join(missing)})
    for idx, (a, b) in enumerate(zip(tracks, tracks[1:]), start=1):
        if a.bpm is not None and b.bpm is not None:
            bpm_delta = round(b.bpm - a.bpm, 2)
            if abs(bpm_delta) > max_bpm_step:
                issues.append({
                    'transition_index': idx,
                    'type': 'bpm_jump',
                    'from_id': a.id,
                    'to_id': b.id,
                    'detail': f'Salto de {bpm_delta} BPM supera el límite de {max_bpm_step}'
                })
        hs = harmonic_score(a.key, b.key)
        if hs == 0.0:
            issues.append({
                'transition_index': idx,
                'type': 'harmonic_clash',
                'from_id': a.id,
                'to_id': b.id,
                'detail': f'Choque tonal ({a.key} -> {b.key}); compatibilidad 0.0'
            })
        if a.artist and b.artist and a.artist.casefold() == b.artist.casefold():
            issues.append({
                'transition_index': idx,
                'type': 'adjacent_artist',
                'from_id': a.id,
                'to_id': b.id,
                'detail': f'Mismo artista consecutivo: {a.artist}'
            })
        if a.energy is not None and b.energy is not None:
            energy_delta = round(b.energy - a.energy, 2)
            if energy_delta < -2.0:
                issues.append({
                    'transition_index': idx,
                    'type': 'energy_drop',
                    'from_id': a.id,
                    'to_id': b.id,
                    'detail': f'Caída brusca de energía ({a.energy} -> {b.energy})'
                })

    return {
        'track_count': len(tracks),
        'issues_found': len(issues),
        'issues': issues,
        'approved': len(issues) == 0
    }

def explain_transition(track_a: Track, track_b: Track) -> dict[str, Any]:
    """Explica detalladamente la transición técnica y perceptual de A a B."""
    bpm_delta = (None if track_a.bpm is None or track_b.bpm is None
                 else round(track_b.bpm - track_a.bpm, 2))
    hs = harmonic_score(track_a.key, track_b.key)

    if hs == 1.0:
        harmonic_comment = 'Misma tonalidad según metadatos; compatibilidad orientativa.'
    elif hs == 0.9:
        harmonic_comment = 'Relativo mayor/menor: cambio de brillo sin disonancia armónica.'
    elif hs == 0.85:
        harmonic_comment = 'Tonalidad vecina (±1 hora en rueda Camelot): transición armónica estándar.'
    elif hs == 0.0:
        harmonic_comment = 'Salto tonal no armónico: se recomienda mezclar en intro/outro percusivo o con corte limpio.'
    else:
        harmonic_comment = 'Tonalidad no informada en una o ambas pistas.'

    energy_comment = 'Sin datos comparables de energía.'
    if track_a.energy is not None and track_b.energy is not None:
        ed = round(track_b.energy - track_a.energy, 2)
        if ed > 0:
            energy_comment = f'Subida de energía (+{ed}): empuja la pista hacia el pico.'
        elif ed < 0:
            energy_comment = f'Bajada de energía ({ed}): momento de respiro o transición de set.'
        else:
            energy_comment = 'Mismo nivel de energía sostenido.'

    return {
        'from_track': vars(track_a),
        'to_track': vars(track_b),
        'bpm_delta': bpm_delta,
        'harmonic_score': hs,
        'harmonic_explanation': harmonic_comment,
        'energy_explanation': energy_comment
    }
