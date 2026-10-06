"""Ejecución de consultas admitidas. Nunca exporta ni muta por decisión del LLM."""
from ..ai.intents import (
    PlanPlaylistIntent, SearchTracksIntent, ComparePlaylistsIntent, AuditLibraryIntent,
    ExplainTransitionIntent, RecommendManualIntent, RecommendLiveIntent, SystemStatusIntent,
    UnknownIntent, ListPlaylistsIntent, DuplicatesIntent, DescribeTrackIntent,
    SimilarTracksIntent, MultiSearchIntent, CollectionSummaryIntent, InspectPlaylistIntent, AuditSetlistIntent,
)
from ..core.models import PlanOptions, PlanningError
from ..core.planner import plan
from ..core.analysis import audit_library, audit_setlist, compare_playlists, explain_transition, find_duplicates
from ..core.recommender import recommend, RecommendationOptions
from ..core.search import search_library
from ..core.mentions import similar_tracks


def enrich_chat(result, lib=None):
    """Offer concrete, safe next steps after every answer; never execute them."""
    suggestions = list(result.get('suggestions', []))[:3]
    if result.get('needs_selection'):
        params = result.get('intent', {})
        criteria = []
        if params.get('same_genre'): criteria.append('genero')
        if params.get('key_mode') == 'exact': criteria.append('misma tonalidad')
        elif params.get('key_mode') == 'compatible': criteria.append('tonalidad')
        if params.get('match_bpm'): criteria.append('bpm')
        if params.get('match_energy'): criteria.append('energia')
        for t in result.get('candidates', [])[:5]:
            refs = [f'@id:{t["id"]}' if r == result['reference'] else '@"'+r+'"'
                    for r in params.get('references', [result['reference']])]
            suggestions.append({'label': f'Elegir {t["artist"]} — {t["title"]} · ID {t["id"]}',
                'query': f'decime {params.get("count",10)} canciones similares en {" y ".join(criteria)} a ' + ' y '.join(refs)})
    else:
        references = result.get('references') or result.get('tracks') or result.get('alternatives') or []
        track = references[0] if references else result.get('track')
        if track and lib and track['id'] in lib.tracks:
            tid = track['id']
            suggestions.extend([{'label':'Ver detalles de la pista', 'query':f'describí pista {tid}'},
                                {'label':'Similares por género y tonalidad', 'query':f'decime canciones similares en genero y tonalidad a @id:{tid}'},
                                {'label':'También ajustar BPM', 'query':f'decime canciones similares en genero tonalidad y bpm a @id:{tid}'}])
    suggestions.extend([{'label':'Revisar mi colección', 'query':'auditar colección'},
                        {'label':'Preparar un set', 'tab':'tab-planner'},
                        {'label':'Conexión y permisos', 'tab':'tab-config'}])
    references = result.get('references') or ([result['track']] if result.get('track') else [])
    context = {'track_id':references[0]['id'], 'source_revision':lib.revision} if len(references)==1 and lib else None
    return {**result, 'suggestions': suggestions[:6], 'context_reference':context}


def execute_chat(intent, lib, state, recommendation=None, live=None):
    return enrich_chat(_execute_chat(intent, lib, state, recommendation, live), lib)


def _execute_chat(intent, lib, state, recommendation=None, live=None):
    result = {'intent': vars(intent), 'applied': False}
    if isinstance(intent, UnknownIntent):
        return {**result, 'response': intent.reason}
    if isinstance(intent, SystemStatusIntent):
        return {**result, 'response': f'Rekordbox: {state}. Biblioteca: {len(lib.tracks) if lib else 0} pistas. Puedo buscar, comparar, recomendar, auditar playlists y preparar propuestas offline. La exportación XML/M3U8 se confirma en el planificador. Crear playlists nativas y consolidar duplicados idénticos requiere Rekordbox y sus agentes cerrados, respaldo y confirmación en la app. El master audible todavía no está certificado.'}
    if lib is None:
        raise PlanningError('Cargá un XML de colección para realizar esta consulta')
    if isinstance(intent,CollectionSummaryIntent):
        from .collection_tools import collection_summary
        return {**result,**collection_summary(lib)}
    if isinstance(intent,InspectPlaylistIntent):
        from .collection_tools import inspect_playlist
        return {**result,**inspect_playlist(lib,intent.playlist)}
    if isinstance(intent,AuditSetlistIntent):
        if not intent.track_ids or len(intent.track_ids)>1000 or any(tid not in lib.tracks for tid in intent.track_ids):
            raise PlanningError('Indicá de 1 a 1000 IDs existentes en el orden que querés revisar')
        PlanOptions(max_bpm_step=intent.max_bpm_step)
        audit=audit_setlist([lib.tracks[tid] for tid in intent.track_ids],intent.max_bpm_step)
        response=f"Revisé {audit['track_count']} pistas en el orden indicado: {audit['issues_found']} observaciones. La revisión usa metadatos del XML."
        response+='\n'+'\n'.join(issue['detail'] for issue in audit['issues'][:10])
        return {**result,'response':response,'setlist_audit':{**audit,'issues':audit['issues'][:100]},'source_revision':lib.revision}
    if isinstance(intent, MultiSearchIntent):
        from ..ai.parser import parse_natural_language_intent
        if not isinstance(intent.queries, (tuple,list)) or not 1 <= len(intent.queries) <= 5:
            raise PlanningError('El lote admite de una a cinco búsquedas.')
        queries = [parse_natural_language_intent(q, list(lib.playlists)) for q in intent.queries]
        if any(not isinstance(item, (SearchTracksIntent, SimilarTracksIntent)) for item in queries):
            raise PlanningError('El lote sólo admite búsquedas y similitudes.')
        answers = []
        for query, item in zip(intent.queries, queries):
            try: answer = _execute_chat(item,lib,state,recommendation,live)
            except PlanningError as error: answer = {'response':str(error), 'applied':False}
            answers.append({'query':query, **answer})
        return {**result, 'results':answers, 'response':'\n\n'.join(f'{n}. {r["query"]}\n{r["response"]}' for n,r in enumerate(answers,1))}
    if isinstance(intent, SimilarTracksIntent):
        matches = similar_tracks(lib, intent)
        if matches['needs_selection']: return {**result, **matches}
        criteria = []
        if intent.same_genre: criteria.append('mismo género')
        if intent.key_mode != 'none': criteria.append('misma tonalidad' if intent.key_mode == 'exact' else 'compatibilidad Camelot (misma, vecinas y relativa)')
        if intent.match_bpm: criteria.append('BPM ±4')
        if intent.match_energy: criteria.append('energía ±1/10 con fuente registrada')
        reference = ', '.join(f'{t["artist"]} — {t["title"]} (@id:{t["id"]})' for t in matches['references'])
        response = f'Referencia: {reference}.\nCriterios: {", ".join(criteria) or "sin filtros"}.\n{matches["total"]} canciones de tu colección cumplen todos los criterios; excluí las referencias.\n'
        response += '\n'.join(f'@id:{t["id"]}: {t["artist"]} — {t["title"]} · {t["bpm"]} BPM · {t["key"] or "sin tonalidad"} · {t["genre"] or "sin género"}' for t in matches['tracks'])
        response += '\nCompatibilidad por metadatos; no confirma similitud sonora ni escucha del master.'
        return {**result, **matches, 'response':response}
    if isinstance(intent, PlanPlaylistIntent):
        if intent.source not in ('playlists','collection') or (intent.source=='collection' and intent.playlists):
            raise PlanningError('Origen de planificación inválido')
        if intent.source=='playlists' and not intent.playlists:
            raise PlanningError('Indicá las playlists de origen')
        options = PlanOptions(count=intent.count, mode=intent.mode, max_bpm_step=intent.max_bpm_step,
                              harmonic=intent.harmonic, same_genre=intent.same_genre,
                              avoid_adjacent_artist=intent.avoid_adjacent_artist)
        proposal = plan(list(lib.tracks.values()) if intent.source=='collection' else lib.pool(list(intent.playlists)), options)
        proposal['source_revision'] = lib.revision
        return {**result, 'response': f'Propuesta de {len(proposal["track_ids"])} pistas por {intent.mode}. Revisala en Preparar un set y confirmá su exportación.'+ ('\n'+proposal['warnings'][0] if proposal['candidate_total']>1000 else ''),
                'plan_result': proposal}
    if isinstance(intent, ListPlaylistsIntent):
        rows = [{'path': path, 'count': len(ids)} for path, ids in lib.playlists.items()]
        return {**result, 'response': '\n'.join(f'{r["path"]}: {r["count"]} pistas' for r in rows), 'playlists': rows}
    if isinstance(intent, SearchTracksIntent):
        matches = search_library(lib, intent)
        filters = []
        if intent.genre: filters.append('género ' + intent.genre)
        if intent.bpm_min is not None or intent.bpm_max is not None: filters.append(f'BPM {intent.bpm_min if intent.bpm_min is not None else 0:g}–{intent.bpm_max if intent.bpm_max is not None else 400:g}')
        if intent.key: filters.append('Camelot ' + intent.key.upper())
        if intent.energy_min is not None or intent.energy_max is not None: filters.append(f'energía {intent.energy_min if intent.energy_min is not None else 0:g}–{intent.energy_max if intent.energy_max is not None else 10:g}/10 con fuente registrada')
        response = f'{matches["total"]} coincidencias' + (' · ' + ', '.join(filters) if filters else '') + '.\n'
        def lines(rows):
            return '\n'.join(f'ID {t["id"]}: {t["artist"]} — {t["title"]} · {t["bpm"]} BPM · {t["key"] or "sin tonalidad"} · energía ' +
                             (f'{t["energy"]}/10 ({t["energy_source"]})' if t['energy'] is not None and t['energy_source'] else 'sin dato') for t in rows)
        response += lines(matches['tracks'])
        if matches['missing_energy_count']:
            response += f'\n{matches["missing_energy_count"]} pistas cumplen los demás filtros pero no tienen energía con fuente registrada. No puedo confirmar ese criterio.'
        if matches['alternatives']:
            response += '\nAlternativas por género/BPM/tonalidad, sin confirmar energía:\n' + lines(matches['alternatives'])
        elif not matches['total'] and not matches['missing_energy_count']:
            response += 'No hay coincidencias exactas. Probá ampliar el rango BPM o cambiar la tonalidad; no relajé tus filtros automáticamente.'
        return {**result, **matches, 'response': response}
    if isinstance(intent, ComparePlaylistsIntent):
        comparison = compare_playlists(lib.pool([intent.playlist_a]), lib.pool([intent.playlist_b]))
        return {**result, 'response': f'{comparison["common_count"]} pistas comunes; {comparison["only_a_count"]} exclusivas de la primera y {comparison["only_b_count"]} de la segunda.', 'comparison': comparison}
    if isinstance(intent, AuditLibraryIntent):
        audit = audit_library(list(lib.tracks.values()))
        missing_genre=sum(not track.genre for track in lib.tracks.values())
        return {**result, 'response': f'{audit["total_tracks"]} pistas en el XML cargado: {missing_genre} sin género, {audit["missing_bpm_count"]} sin BPM y {audit["missing_key_count"]} sin tonalidad. Salud de metadatos: {audit["health_score"]}%. Abrí cada listado para ver todas las pistas y corregilas en Rekordbox; luego exportá y cargá un XML actualizado.',
                'audit':{**audit,'missing_genre_count':missing_genre},
                'suggestions':[{'label':'Ver pistas sin género','opportunity':'genre'},
                               {'label':'Ver pistas sin BPM','opportunity':'bpm'},
                               {'label':'Ver pistas sin tonalidad','opportunity':'key'}]}
    if isinstance(intent, DuplicatesIntent):
        duplicates = find_duplicates(list(lib.tracks.values()))
        return {**result, 'response': f'{len(duplicates)} grupos posiblemente duplicados por título/artista. No se eliminó ningún archivo.', 'duplicates': duplicates}
    if isinstance(intent, DescribeTrackIntent):
        track = lib.tracks.get(intent.track_id)
        if track is None:
            raise PlanningError('ID de pista inexistente')
        return {**result, 'response': f'{track.artist} — {track.title}. BPM: {track.bpm}; tonalidad: {track.key}; género: {track.genre or "sin dato"}; energía: {track.energy}.', 'track': vars(track)}
    if isinstance(intent, ExplainTransitionIntent):
        if intent.track_a_id not in lib.tracks or intent.track_b_id not in lib.tracks:
            raise PlanningError('ID de pista inexistente')
        transition = explain_transition(lib.tracks[intent.track_a_id], lib.tracks[intent.track_b_id])
        return {**result, 'response': f'Delta BPM: {transition["bpm_delta"]}. {transition["harmonic_explanation"]} {transition["energy_explanation"]}', 'transition': transition}
    if isinstance(intent, RecommendManualIntent):
        current = lib.tracks.get(intent.current_track_id)
        if current is None:
            raise PlanningError('ID de pista inexistente')
        options = dict(recommendation or {})
        options['count'] = intent.count
        suggestions = recommend(current, list(lib.tracks.values()), RecommendationOptions(**options))
        return {**result, 'response': f'{len(suggestions["recommendations"])} candidatas compatibles.\n' + '\n'.join(f'ID {t["id"]}: {t["artist"]} — {t["title"]}' for t in suggestions['recommendations']), **suggestions}
    if isinstance(intent, RecommendLiveIntent):
        suggestion = live or {'confirmed': False, 'reason': 'Sin telemetría real validada'}
        if suggestion.get('source')=='rekordbox_history':
            reference=suggestion.get('reference_track')
            response=suggestion.get('reason','Referencia del historial; no escucha del master')
            if reference:response=f'Referencia del historial: {reference["artist"]} — {reference["title"]}. No confirma la pista audible actual.\n'+response
            rows=suggestion.get('recommendations',[])
            response+='\n'+'\n'.join(f'{t["artist"]} — {t["title"]} · {t.get("bpm")} BPM · {t.get("key") or "Sin tonalidad"} · {t.get("genre") or "Sin género"}' for t in rows)
            return {**result,'response':response,'live':suggestion,'recommendations':rows,'references':[reference] if reference else []}
        return {**result, 'response': suggestion.get('body') if suggestion.get('confirmed') else suggestion.get('reason'), 'live': suggestion}
    raise PlanningError('Consulta no implementada')
