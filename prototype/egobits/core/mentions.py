"""Resolve @ references locally. Ambiguous names are never chosen silently."""
import re
from .models import PlanningError
from .search import normalized_genre
from .planner import harmonic_score

MENTION = re.compile(r'(?<![\w@])@(?:"([^"\n]{1,160})"|\x27([^\x27\n]{1,160})\x27|([^\s,;?!]{1,160}))')


def extract_mentions(text):
    return [next(x for x in match.groups() if x is not None).rstrip('.') for match in MENTION.finditer(text)]


def resolve_followup(query, lib, context):
    """Reuse only a previously selected reference from the same XML revision."""
    pronoun = re.compile(r'\b(?:esa|esta|la anterior)\s+(?:pista|canci[oó]n|tema)\b|(?<=como )esa\b', re.IGNORECASE)
    if extract_mentions(query) or not pronoun.search(query): return query
    if not isinstance(context, dict) or set(context) != {'track_id','source_revision'}:
        raise PlanningError('Elegí primero una canción con @ para saber a qué pista te referís.')
    if context['source_revision'] != lib.revision or not isinstance(context['track_id'], str) or context['track_id'] not in lib.tracks:
        raise PlanningError('La referencia anterior ya no corresponde a la colección. Volvé a elegirla con @.')
    return pronoun.sub(lambda _: '@id:' + context['track_id'], query)


def mention_candidates(lib, query, limit=10):
    if not isinstance(query, str) or len(query) > 160: raise PlanningError('Referencia demasiado larga.')
    if query.startswith('id:'):
        track = lib.tracks.get(query[3:])
        return [vars(track)] if track else []
    needle = normalized_genre(query)
    if not needle: return [vars(t) for t in list(lib.tracks.values())[:limit]] if not query else []
    ranked = []
    for track in lib.tracks.values():
        title, full = normalized_genre(track.title), normalized_genre(track.artist + ' ' + track.title)
        exact = needle in (title, full) or query == track.id
        if exact or needle in full:
            ranked.append((0 if exact else 1, track.id, track))
    ranked.sort(key=lambda row: row[:2])
    return [vars(row[2]) for row in ranked[:limit]]


def resolve_reference(lib, reference):
    if reference.startswith('id:'):
        track = lib.tracks.get(reference[3:])
        return track, [] if track else mention_candidates(lib, reference)
    needle = normalized_genre(reference)
    exact = [t for t in lib.tracks.values() if needle and
             (needle in (normalized_genre(t.title), normalized_genre(t.artist + ' ' + t.title)) or reference == t.id)]
    if len(exact) == 1: return exact[0], []
    # Partial matches are suggestions only, even if there is just one.
    return None, [vars(t) for t in exact[:10]] if exact else mention_candidates(lib, reference)


def similar_tracks(lib, intent):
    if not isinstance(intent.references, (tuple, list)) or not 1 <= len(intent.references) <= 5 or any(not isinstance(r, str) or not r or len(r) > 160 for r in intent.references):
        raise PlanningError('Elegí de una a cinco referencias @ de la colección.')
    if type(intent.count) is not int or not 1 <= intent.count <= 50 or intent.key_mode not in ('none', 'exact', 'compatible'):
        raise PlanningError('Cantidad o criterio de similitud inválido.')
    if any(type(v) is not bool for v in (intent.same_genre, intent.match_bpm, intent.match_energy)):
        raise PlanningError('Criterios de similitud inválidos.')
    references = []
    for reference in intent.references:
        track, candidates = resolve_reference(lib, reference)
        if track is None:
            return {'needs_selection': True, 'reference': reference, 'candidates': candidates,
                    'response': (f'La referencia @{reference} necesita una selección explícita. Elegí una pista:\n' +
                                 '\n'.join(f'@id:{t["id"]} · {t["artist"]} — {t["title"]} · {t["bpm"]} BPM · {t["key"] or "sin tonalidad"}' for t in candidates))
                                if candidates else f'No encontré @{reference} en tu colección. Escribí @ para buscar y seleccionar una pista.'}
        references.append(track)
    references = list({t.id: t for t in references}.values())
    for t in references:
        if intent.same_genre and not t.genre: raise PlanningError(f'@id:{t.id} no tiene género registrado.')
        if intent.key_mode != 'none' and not t.key: raise PlanningError(f'@id:{t.id} no tiene tonalidad registrada.')
        if intent.match_bpm and t.bpm is None: raise PlanningError(f'@id:{t.id} no tiene BPM registrado.')
        if intent.match_energy and (t.energy is None or not t.energy_source): raise PlanningError(f'@id:{t.id} no tiene energía con fuente registrada.')
    found = []
    reference_ids = {r.id for r in references}
    for t in lib.tracks.values():
        if t.id in reference_ids: continue
        if intent.same_genre and any(normalized_genre(t.genre) != normalized_genre(r.genre) for r in references): continue
        if intent.key_mode == 'exact' and any(t.key != r.key for r in references): continue
        scores = [harmonic_score(r.key, t.key) for r in references]
        if intent.key_mode == 'compatible' and any(s is None or s < .85 for s in scores): continue
        bpm = [abs(t.bpm-r.bpm) for r in references] if t.bpm is not None and all(r.bpm is not None for r in references) else []
        if intent.match_bpm and (not bpm or max(bpm) > 4): continue
        energy = [abs(t.energy-r.energy) for r in references] if t.energy is not None and t.energy_source and all(r.energy is not None and r.energy_source for r in references) else []
        if intent.match_energy and (not energy or max(energy) > 1): continue
        found.append((-(min(scores) if all(s is not None for s in scores) else 0) if intent.key_mode != 'none' else 0,
                      max(bpm) if intent.match_bpm else 0, max(energy) if intent.match_energy else 0, t.id, t))
    found.sort(key=lambda row: row[:4])
    return {'needs_selection': False, 'references': [vars(t) for t in references],
            'tracks': [vars(row[-1]) for row in found[:intent.count]], 'total': len(found),
            'criteria': {'same_genre': intent.same_genre, 'key_mode': intent.key_mode,
                         'bpm_margin': 4 if intent.match_bpm else None, 'energy_margin': 1 if intent.match_energy else None},
            'source_revision': lib.revision}
