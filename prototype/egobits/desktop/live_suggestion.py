"""Sugerencias push sólo con telemetría real y audible confirmada."""
from __future__ import annotations

from ..adapters.xml_adapter import Library
from ..core.recommender import recommend, RecommendationOptions
from ..core.models import PlanningError
from ..telemetry.provider import TelemetryProvider


def live_suggestion(lib: Library, provider: TelemetryProvider | None, options: RecommendationOptions | None = None) -> dict:
    try:
        if provider is None or not provider.is_available():
            return {'confirmed': False, 'reason': 'Sin proveedor de telemetría real'}
        event = provider.get_current_state()
    except Exception:
        return {'confirmed': False, 'reason': 'Proveedor de telemetría no disponible'}
    if event is None or event.source == 'simulator' or not event.is_audible() or event.confidence < 0.85:
        return {'confirmed': False, 'reason': 'Pista audible no confirmada'}
    current = lib.tracks.get(event.track_id)
    if current is None or current.bpm is None:
        return {'confirmed': False, 'reason': 'Pista actual sin datos confiables'}
    try:
        result = recommend(current, list(lib.tracks.values()), options or RecommendationOptions())
    except PlanningError as exc:
        return {'confirmed': False, 'reason': str(exc)}
    if not result['recommendations']:
        return {'confirmed': False, 'reason': 'Sin pista compatible confirmada'}
    chosen = lib.tracks[result['recommendations'][0]['id']]
    return {
        'confirmed': True,
        'event_id': f'{lib.revision}:{event.source}:{event.deck_id}:{event.track_id}:{chosen.id}',
        'title': 'Pista compatible',
        'body': f'{chosen.artist} — {chosen.title} · {chosen.bpm:g} BPM · {chosen.key}',
        'track_id': chosen.id,
        'recommendations':result['recommendations'],
    }
