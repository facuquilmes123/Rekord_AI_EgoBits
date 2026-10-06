"""Collection queries shared by chat, HTTP and MCP; no database writes."""
from datetime import date
import math
from pathlib import Path
from .models import PlanningError
from .planner import normalize_key, harmonic_score
from ..adapters.m3u8 import local_path


def pagination(limit,offset):
    if type(limit) is not int or not 1<=limit<=200 or type(offset) is not int or not 0<=offset<=500000:
        raise PlanningError('Paginación: límite 1..200 y desplazamiento 0..500000')


def query_tracks(lib, query='', genre='', min_rating=None, max_rating=None, unplayed=False,
                 added_after='', tags=None, tag_mode='all', sort_by_date=False, limit=50, offset=0):
    pagination(limit,offset)
    if any(not isinstance(v,str) or len(v)>500 for v in (query,genre,added_after)):raise PlanningError('Filtro de texto inválido')
    if type(unplayed) is not bool or type(sort_by_date) is not bool:raise PlanningError('Filtros booleanos inválidos')
    if any(v is not None and (type(v) is not int or not 0<=v<=5) for v in (min_rating,max_rating)):raise PlanningError('Rating: 0..5 estrellas')
    if min_rating is not None and max_rating is not None and min_rating>max_rating:raise PlanningError('Rango de estrellas invertido')
    if added_after:
        try:date.fromisoformat(added_after)
        except ValueError:raise PlanningError('Fecha: AAAA-MM-DD') from None
    tags=tags or []
    if not isinstance(tags,list) or len(tags)>20 or any(not isinstance(t,str) or not t or len(t)>200 for t in tags) or tag_mode not in ('all','any'):
        raise PlanningError('Indicá hasta 20 etiquetas y modo all/any')
    metadata=getattr(lib,'native_metadata',{})
    if (unplayed or added_after or tags or min_rating is not None or max_rating is not None) and not hasattr(lib,'native_metadata'):
        raise PlanningError('Conectá la colección viva para consultar estrellas, reproducciones, fechas y MyTags')
    result=[]
    for track in lib.tracks.values():
        extra=metadata.get(track.id,{})
        if query.casefold() not in (track.title+' '+track.artist).casefold():continue
        if genre and genre.casefold() not in track.genre.casefold():continue
        if min_rating is not None and (extra.get('rating') is None or extra['rating']<min_rating):continue
        if max_rating is not None and (extra.get('rating') is None or extra['rating']>max_rating):continue
        if unplayed and extra.get('play_count')!=0:continue
        if added_after and (not extra.get('date_added') or extra['date_added'][:10]<added_after):continue
        available={v.casefold() for t in extra.get('tags',[]) for v in (t['id'],t['name'],t['category']+'/'+t['name'],t['category'],t.get('category_id',''))}
        checks=[t.casefold() in available for t in tags]
        if checks and not (all(checks) if tag_mode=='all' else any(checks)):continue
        result.append({**vars(track),**{k:extra.get(k) for k in ('rating','play_count','date_added','tags')}})
    if sort_by_date:result.sort(key=lambda t:(t.get('date_added') or '',t['id']),reverse=True)
    return {'tracks':result[offset:offset+limit],'total':len(result),'offset':offset,'limit':limit,'source_revision':lib.revision,
            'source_kind':getattr(lib,'source_kind','xml'),'scope':'colección conectada completa; resultados paginados',
            'play_count_note':'El contador de Rekordbox no demuestra que nunca se reprodujo fuera de esta colección.'}


def get_tags(lib):
    if not hasattr(lib,'native_tags'):raise PlanningError('Conectá la colección viva para leer MyTags')
    return {'tags':lib.native_tags,'source_revision':lib.revision}


def missing_files(lib, limit=100, offset=0):
    pagination(limit,offset);tracks=list(lib.tracks.values());rows=[]
    for track in tracks[offset:offset+limit]:
        try:
            path=local_path(track.location)
            state='available' if path.is_file() and path.stat().st_size>0 else 'missing_or_empty'
        except (ValueError,OSError):state='unavailable'
        rows.append({'id':track.id,'title':track.title,'artist':track.artist,'state':state})
    return {'checked':len(rows),'total_tracks':len(tracks),'offset':offset,'next_offset':offset+len(rows) if offset+len(rows)<len(tracks) else None,
            'files':rows,'missing_in_page':sum(r['state']!='available' for r in rows),'source_revision':lib.revision,
            'note':'Unidad desconectada, permisos y rutas movidas también pueden impedir el acceso. No se borró nada.'}


def shifted_key(key,semitones):
    key=normalize_key(key)
    if key is None:return None
    if type(semitones) is not int or not -12<=semitones<=12:raise PlanningError('Desplazamiento tonal inválido')
    return str((int(key[:-1])-1+7*semitones)%12+1)+key[-1]


def key_shift_options(from_key,to_key,max_semitones=2):
    if type(max_semitones) is not int or not 0<=max_semitones<=2:raise PlanningError('Key Shift admite 0, 1 o 2 semitonos')
    if not normalize_key(from_key) or not normalize_key(to_key):return []
    choices=[]
    for shift in range(-max_semitones,max_semitones+1):
        result=shifted_key(to_key,shift);score=harmonic_score(from_key,result)
        if score>=.85:choices.append({'semitones':shift,'resulting_key':result,'harmonic_score':score,
                                     'manual_action':f'Key Shift {shift:+d} en la pista entrante' if shift else 'Sin Key Shift'})
    return sorted(choices,key=lambda r:(abs(r['semitones']),-r['harmonic_score'],r['semitones']))


def structure(lib,track_id):
    if track_id not in lib.tracks:raise PlanningError('Pista no encontrada en esta colección')
    from ..adapters.analysis_structure import analysis_structure
    extra=getattr(lib,'native_metadata',{}).get(track_id,{})
    node=lib.nodes[track_id];cues=extra.get('cues')
    if cues is None:
        cues=[]
        for mark in node.findall('POSITION_MARK'):
            try:
                start=float(mark.get('Start',''));end=float(mark.get('End')) if mark.get('End') else None;num=int(mark.get('Num',-1))
                if not math.isfinite(start) or start<0 or (end is not None and not math.isfinite(end)):continue
                cues.append({'start':start,'end':end,'loop':mark.get('Type')=='4','hot_cue':num+1 if 0<=num<=7 else None,'name':mark.get('Name',''),'source':'XML'})
            except (ValueError,TypeError):continue
    analysis=analysis_structure(lib,track_id)
    return {'track_id':track_id,'title':lib.tracks[track_id].title,'cues':cues,'hot_cues':sum(bool(c['hot_cue']) for c in cues),
            'memory_cues':sum(not c['hot_cue'] for c in cues),'loops':sum(c['loop'] for c in cues),
            'beatgrid_present':bool(node.findall('TEMPO')) or analysis['beatgrid_present'],
            'beatgrid_locked':extra.get('beatgrid_locked'),'beatgrid_verified':False,
            'phrases':analysis['phrases'],'analysis_note':analysis['note'],'source_revision':lib.revision,
            'note':'La presencia de beatgrid no certifica alineación musical; la revisión auditiva sigue siendo necesaria.'}


def preshow(lib,playlist=None,limit=100,offset=0):
    pagination(limit,offset)
    ids=list(lib.tracks) if not playlist else [t.id for t in lib.pool([playlist])]
    rows=[]
    for tid in ids[offset:offset+limit]:
        data=structure(lib,tid);track=lib.tracks[tid]
        try:available=local_path(track.location).is_file()
        except (ValueError,OSError):available=False
        rows.append({**data,'file_available':available,'missing_bpm':track.bpm is None,'missing_key':track.key is None})
    return {'tracks':rows,'total':len(ids),'offset':offset,'next_offset':offset+len(rows) if offset+len(rows)<len(ids) else None,
            'source_revision':lib.revision,'scope':'Auditoría paginada de la selección completa'}


def phrase_transition(lib,from_id,to_id,bars=16):
    if type(bars) is not int or not 1<=bars<=64:raise PlanningError('Longitud: 1..64 compases')
    a=structure(lib,from_id);b=structure(lib,to_id);ta=lib.tracks[from_id];tb=lib.tracks[to_id]
    if not ta.bpm or not tb.bpm:raise PlanningError('Ambas pistas necesitan BPM')
    outgoing=next((p for p in reversed(a['phrases']) if p.get('label')=='outro'),None)
    incoming=next((c for c in b['cues'] if c['hot_cue']==1),None)
    if outgoing is None or incoming is None:
        return {'available':False,'reason':'Se necesita una frase Outro con tiempo conocido y Hot Cue A en la pista entrante.',
                'from':a,'to':b,'source_revision':lib.revision}
    duration=bars*4*60/ta.bpm
    return {'available':True,'from_id':from_id,'to_id':to_id,'start_outgoing_seconds':outgoing['start_seconds'],
            'start_incoming_seconds':incoming['start'],'mix_duration_seconds':round(duration,3),'bars':bars,'assumed_beats_per_bar':4,
            'incoming_tempo_ratio':round(ta.bpm/tb.bpm,6),'harmonic_options':key_shift_options(ta.key,tb.key),
            'evidence':{'outgoing_phrase':outgoing,'incoming_cue':incoming},'source_revision':lib.revision,
            'note':'Propuesta para ensayo con tempo ajustado y compás 4/4. No garantiza drops sincronizados ni ausencia de choque melódico.'}
