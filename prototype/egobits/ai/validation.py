"""Frontera de confianza: ninguna respuesta del modelo es una orden ejecutable."""
from dataclasses import fields
import math
from .intents import (
    PlanPlaylistIntent, SearchTracksIntent, ComparePlaylistsIntent, AuditLibraryIntent,
    ExplainTransitionIntent, RecommendManualIntent, RecommendLiveIntent, SystemStatusIntent,
    UnknownIntent, ListPlaylistsIntent, DuplicatesIntent, DescribeTrackIntent,
    SimilarTracksIntent, MultiSearchIntent,
)
from ..core.models import PlanningError, PlanOptions

TYPES = {kind().action: kind for kind in (
    PlanPlaylistIntent, SearchTracksIntent, ComparePlaylistsIntent, AuditLibraryIntent,
    ExplainTransitionIntent, RecommendManualIntent, RecommendLiveIntent, SystemStatusIntent,
    UnknownIntent, ListPlaylistsIntent, DuplicatesIntent, DescribeTrackIntent,
    SimilarTracksIntent, MultiSearchIntent,
)}
PARAMETERS = {
    'playlists': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 20},
    'references': {'type': 'array', 'items': {'type': 'string', 'maxLength':160}, 'minItems':1, 'maxItems':5},
    'queries': {'type': 'array', 'items': {'type': 'string', 'maxLength':500}, 'minItems':1, 'maxItems':5},
    'key_mode': {'type': 'string', 'enum': ['none', 'exact', 'compatible']},
    'count': {'type': 'integer', 'minimum': 1, 'maximum': 100},
    'mode': {'type': 'string', 'enum': ['bpm', 'energy']},
    'max_bpm_step': {'type': 'number', 'exclusiveMinimum': 0, 'maximum': 30},
    **{key: {'type': 'boolean'} for key in ('same_genre', 'harmonic', 'avoid_adjacent_artist', 'match_bpm', 'match_energy')},
    **{key: {'type': 'string', 'maxLength': 500} for key in (
        'out_name', 'query', 'playlist_a', 'playlist_b', 'track_a_id', 'track_b_id',
        'current_track_id', 'track_id', 'reason', 'genre', 'key')},
    **{key: {'type': 'number', 'minimum': 0, 'maximum': 400} for key in ('bpm_min', 'bpm_max')},
    **{key: {'type': 'number', 'minimum': 0, 'maximum': 10} for key in ('energy_min', 'energy_max')},
    'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100},
    'offset': {'type': 'integer', 'minimum': 0, 'maximum': 1000000},
}
REQUIRED_PARAMS = {'playlist.plan': ['playlists'], 'playlist.compare': ['playlist_a','playlist_b'],
                   'library.search': ['query'], 'track.describe': ['track_id'],
                   'transition.explain': ['track_a_id','track_b_id'],
                   'recommend.manual': ['current_track_id'], 'library.similar':['references'],
                   'library.multisearch':['queries'], 'help': ['reason']}
INTENT_SCHEMA = {'oneOf': [
    {'type': 'object', 'additionalProperties': False, 'required': ['action','params'],
     'properties': {'action': {'const': action}, 'params': {
         'type': 'object', 'additionalProperties': False,
         'properties': {field.name: PARAMETERS[field.name] for field in fields(kind) if field.name != 'action'},
         'required': REQUIRED_PARAMS.get(action, [])}}}
    for action, kind in TYPES.items()
]}
ACTION_HELP = '; '.join(action + '(' + ','.join(field.name for field in fields(kind) if field.name != 'action') + ')'
                        for action, kind in TYPES.items())


def intent_from_payload(payload, available_playlists):
    if not isinstance(payload, dict) or set(payload) != {'action', 'params'}:
        raise PlanningError('Respuesta de IA con estructura inválida')
    kind = TYPES.get(payload['action']) if isinstance(payload['action'], str) else None
    params = payload['params']
    if kind is None or not isinstance(params, dict):
        raise PlanningError('Acción de IA no permitida')
    allowed = {field.name for field in fields(kind)} - {'action'}
    if set(params) - allowed:
        raise PlanningError('Parámetros no admitidos para la acción')
    for key, value in params.items():
        spec = PARAMETERS[key]
        expected = spec['type']
        if expected == 'string' and (not isinstance(value, str) or len(value) > 500):
            raise PlanningError('Texto de IA inválido')
        if 'enum' in spec and value not in spec['enum']: raise PlanningError('Opción de IA inválida')
        if expected == 'integer' and (type(value) is not int or not spec['minimum'] <= value <= spec['maximum']):
            raise PlanningError('Entero de IA inválido')
        if expected == 'boolean' and type(value) is not bool:
            raise PlanningError('Booleano de IA inválido')
        if expected == 'array' and (not isinstance(value, list) or not all(isinstance(v, str) and len(v) <= spec['items'].get('maxLength',500) for v in value) or not spec.get('minItems',0) <= len(value) <= spec['maxItems']):
            raise PlanningError('Lista de IA inválida')
        if expected == 'number' and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                                    or value < spec.get('minimum', 0) or value <= spec.get('exclusiveMinimum', -1)
                                    or value > spec.get('maximum', float('inf'))):
            raise PlanningError('Número de IA inválido')
    params = dict(params)
    for key in ('playlists', 'references', 'queries'):
        if key in params: params[key] = tuple(params[key])
    intent = kind(**params)
    if isinstance(intent, SearchTracksIntent):
        from ..core.search import validate_search
        validate_search(intent)
    if isinstance(intent, SimilarTracksIntent) and (not intent.references or not 1 <= intent.count <= 50 or any(not r for r in intent.references)):
        raise PlanningError('Referencias o cantidad de similitud inválidas')
    if isinstance(intent, MultiSearchIntent):
        from .parser import parse_natural_language_intent
        if not intent.queries or any(not isinstance(parse_natural_language_intent(q, available_playlists), (SearchTracksIntent, SimilarTracksIntent)) for q in intent.queries):
            raise PlanningError('El lote sólo admite búsquedas y similitudes sin escrituras')
    if isinstance(intent, PlanPlaylistIntent):
        if not intent.playlists or any(p not in available_playlists for p in intent.playlists):
            raise PlanningError('La IA propuso playlists inexistentes o no eligió origen')
        PlanOptions(count=intent.count, mode=intent.mode, max_bpm_step=intent.max_bpm_step,
                    same_genre=intent.same_genre, harmonic=intent.harmonic,
                    avoid_adjacent_artist=intent.avoid_adjacent_artist)
    if isinstance(intent, ComparePlaylistsIntent):
        if intent.playlist_a not in available_playlists or intent.playlist_b not in available_playlists:
            raise PlanningError('La IA propuso playlists inexistentes')
    if isinstance(intent, RecommendManualIntent) and not 1 <= intent.count <= 50:
        raise PlanningError('Demasiadas recomendaciones')
    return intent
