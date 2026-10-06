"""Single validated, read-only tool boundary for HTTP, MCP and local model."""
import inspect
import json
import re
import time
import unicodedata
from datetime import date as calendar_date
from . import intelligence as queries
from .models import PlanningError, PlanOptions
from .planner import plan
from .analysis import audit_library
from .recommender import recommend, RecommendationOptions


def plan_selection(lib, track_ids, count=10, mode='bpm'):
    if not isinstance(track_ids,list) or not 1<=len(track_ids)<=1000 or any(not isinstance(i,str) or i not in lib.tracks for i in track_ids):
        raise PlanningError('Seleccioná IDs existentes de la colección (1..1000)')
    return {**plan([lib.tracks[i] for i in dict.fromkeys(track_ids)],PlanOptions(count=count,mode=mode)),
            'source_revision':lib.revision,'applied':False}


def recommendation(lib, track_id, max_key_shift=0, count=5):
    if not isinstance(track_id,str) or track_id not in lib.tracks:raise PlanningError('Pista inexistente')
    result=recommend(lib.tracks[track_id],list(lib.tracks.values()),RecommendationOptions(count=count,max_key_shift=max_key_shift))
    result.pop('excluded',None)
    return {**result,'source_revision':lib.revision}


def audio_measurement(lib,track_id):
    from ..desktop.service import _ANALYSIS
    if not isinstance(track_id,str) or track_id not in lib.tracks:raise PlanningError('Pista inexistente')
    return _ANALYSIS.measurements(lib,track_id)


def device_list(lib):
    from ..desktop.service import _USB
    return _USB.discover()


def device_audit(lib,device_id,limit=100,offset=0):
    from ..desktop.service import _USB
    return _USB.device(device_id).inspect(limit,offset)


def link_state(lib):
    from ..desktop.service import _LINK
    return _LINK.snapshot()


FUNCTIONS={'collection.query':queries.query_tracks,'collection.tags':queries.get_tags,
           'collection.missing_files':queries.missing_files,'track.structure':queries.structure,
           'set.preshow':queries.preshow,'transition.phrase':queries.phrase_transition,
           'set.plan_selection':plan_selection,'recommend.key_shift':recommendation,
           'audio.measurement':audio_measurement,'device.list':device_list,'device.audit':device_audit,'link.state':link_state}
DESCRIPTIONS={
    'collection.query':'Filtrar toda la colección por título/artista, género, estrellas, sin reproducir, fecha AAAA-MM-DD y MyTags. Resultados paginados.',
    'collection.tags':'Listar MyTags con categoría e ID de la colección viva.',
    'collection.missing_files':'Comprobar archivos por página; next_offset indica la página siguiente.',
    'track.structure':'Consultar hot cues, memory cues, loops, beatgrid y frases ANLZ existentes de un ID.',
    'set.preshow':'Auditar una playlist o toda la colección por páginas antes del show.',
    'transition.phrase':'Proponer mezcla 4/4 basada en Outro analizado y Hot Cue A, para dos IDs.',
    'set.plan_selection':'Ordenar IDs obtenidos de filtros en modo bpm o energy; sólo propuesta.',
    'recommend.key_shift':'Compatibilidad armónica con Key Shift optativo de 0, 1 o 2 semitonos.',
    'audio.measurement':'Leer LUFS y energía estimada ya calculados offline para un ID.',
    'device.list':'Detectar USB DeviceSQL presentes, sin modificar archivos.',
    'device.audit':'Auditar un device_id obtenido de device.list: archivos, análisis y referencias huérfanas.',
    'link.state':'Consultar receptor o simulación Pro DJ Link; On-Air no certifica audio audible.'}


def catalog():
    return [{'name':name,'description':DESCRIPTIONS[name],
             'parameters':{p.name:('required' if p.default is inspect.Parameter.empty else p.default)
                           for p in inspect.signature(fn).parameters.values() if p.name!='lib'},'read_only':True}
            for name,fn in FUNCTIONS.items()]


def execute(lib,name,arguments):
    if not isinstance(name,str) or name not in FUNCTIONS:raise PlanningError('Herramienta no permitida')
    if not isinstance(arguments,dict) or len(json.dumps(arguments))>16000:raise PlanningError('Argumentos inválidos')
    try:inspect.signature(FUNCTIONS[name]).bind(lib,**arguments)
    except TypeError:raise PlanningError('Parámetros desconocidos o incompletos para '+name) from None
    try:return FUNCTIONS[name](lib,**arguments)
    except (TypeError,KeyError,AttributeError):raise PlanningError('Tipos de parámetros inválidos') from None


def response(lib,result,trace=None):
    tracks=result.get('tracks',[])
    if tracks and not isinstance(tracks[0],dict):tracks=[]
    if 'total' in result:message=f"Encontré {result['total']} pistas en la selección consultada. Muestro {len(tracks)}."
    elif 'tags' in result:message='MyTags: '+', '.join(t['category']+'/'+t['name'] for t in result['tags'][:40])
    elif 'missing_in_page' in result:message=f"Comprobé {result['checked']} archivos de {result['total_tracks']}: {result['missing_in_page']} ausentes o inaccesibles en esta página."
    elif 'hot_cues' in result:message=f"{result['title']}: {result['hot_cues']} hot cues, {result['memory_cues']} memory cues, {result['loops']} loops y {len(result['phrases'])} frases. Beatgrid {'presente, sin certificar su precisión' if result['beatgrid_present'] else 'no disponible'}."
    elif result.get('available') is True:message=f"Propuesta de ensayo: iniciar la entrante en {result['start_incoming_seconds']} s cuando la saliente llegue a {result['start_outgoing_seconds']} s. Mezcla de {result['bars']} compases, aproximadamente {result['mix_duration_seconds']} s, asumiendo 4/4. No garantiza drops sincronizados."
    elif 'recommendations' in result:message='Sugerencias: '+('; '.join(f"{t['artist']} — {t['title']}: "+', '.join(t.get('match_reasons',[])) for t in result['recommendations']) or 'sin coincidencias con estos criterios')
    elif result.get('reason'):message=result['reason']
    else:message='Consulta completada con datos de la colección conectada.'
    return {'response':message,'tracks':tracks,'result':result,'tool_trace':trace or [],'source_revision':lib.revision,'applied':False}


def direct(lib,query):
    text=''.join(c for c in unicodedata.normalize('NFD',query.casefold()) if not unicodedata.combining(c))
    if re.search(r'\b(?:mytags|mis etiquetas|listar etiquetas)\b',text) and not re.search(r'\b(?:con|filtra|busca)\b',text):
        return response(lib,execute(lib,'collection.tags',{}))
    args={}
    if re.search(r'sin (?:reproducir|reproducciones)|nunca (?:reproduc|toc)|joyas olvidadas|crate digg',text):args['unplayed']=True
    rating=re.search(r'(?:al menos|minimo|desde)?\s*([0-5]) estrellas',text)
    if rating:args['min_rating']=int(rating[1])
    date=re.search(r'(?:desde|despues de)\s+(\d{4}-\d{2}-\d{2})',text)
    if date:args['added_after']=date[1]
    elif 'este ano' in text:args['added_after']=f'{calendar_date.today().year}-01-01'
    tag=re.search(r'(?:mytag|etiqueta)\s+["“]([^"”]+)["”]',query,re.I)
    if tag:args['tags']=[tag[1]]
    available_genres=sorted({t.genre for t in lib.tracks.values() if t.genre},key=len,reverse=True)
    for genre in available_genres:
        if genre.casefold() in query.casefold():args['genre']=genre;break
    inferred=[t['id'] for t in getattr(lib,'native_tags',[]) if len(t['name'])>2 and re.search(r'(?<!\w)'+re.escape(t['name'].casefold())+r'(?!\w)',query.casefold())]
    if inferred and re.search(r'mostr|busc|selecci|tema|pista|track|tague|filtr',text):args['tags']=inferred[:20]
    # Compound planning is left to the bounded agent, never silently discarded.
    if args and set(args)!={'genre'}:
        if re.search(r'\b(?:arma|armame|planifica|ordena|prepara)\b',text):
            count_match=re.search(r'(\d+)\s*(?:pistas|temas|tracks|canciones)',text)
            count=int(count_match[1]) if count_match else 10
            if not 1<=count<=100:raise PlanningError('Elegí entre 1 y 100 pistas para el set')
            found=execute(lib,'collection.query',{**args,'limit':200})
            if not found['tracks']:return response(lib,found)
            planned=plan_selection(lib,[t['id'] for t in found['tracks']],min(count,len(found['tracks'])),'energy' if 'energia' in text else 'bpm')
            answer=response(lib,planned,[{'tool':'collection.query','state':'complete'},{'tool':'set.plan_selection','state':'complete'}])
            answer['plan_result']=planned;answer['response']=f"Preparé una propuesta de {len(planned['track_ids'])} pistas con los filtros pedidos."
            if found['total']>200:answer['response']+=f" La búsqueda encontró {found['total']}; planifiqué sobre las primeras 200 coincidencias."
            return answer
        return response(lib,execute(lib,'collection.query',args))
    return None


def needs_agent(lib,query):
    if re.search(r'mytag|etiqueta|estrellas|sin reproducir|nunca toc|crate digg|hot cue|memory cue|frase|pre.?show|key shift|\busb\b|pendrive|pro dj link|\blufs\b',query,re.I):return True
    return any(len(t['name'])>2 and re.search(r'(?<!\w)'+re.escape(t['name'])+r'(?!\w)',query,re.I) for t in getattr(lib,'native_tags',[]))


def run_agent(lib,query,client,cancelled=None,max_steps=3):
    started=time.monotonic();trace=[];seen=set();last=None
    names={'collection.query','set.plan_selection'}
    text=query.casefold()
    if re.search(r'tag|etiqueta|afterparty|peak|vocal',text):names.add('collection.tags')
    if re.search(r'cue|frase|estructura|pre.?show',text):names.update(('track.structure','set.preshow','transition.phrase'))
    if re.search(r'key shift|semitono|armoni',text):names.add('recommend.key_shift')
    if re.search(r'usb|pendrive|dispositivo',text):names.update(('device.list','device.audit'))
    if 'link' in text:names.add('link.state')
    if re.search(r'lufs|sonoridad|acustic',text):names.add('audio.measurement')
    if re.search(r'archivo|faltan|ausente',text):names.add('collection.missing_files')
    context={'source_revision':lib.revision,'source_kind':getattr(lib,'source_kind','xml'),
             'tracks_count':len(lib.tracks),'playlists':list(lib.playlists)[:30],'tools':[t for t in catalog() if t['name'] in names],'results':[]}
    for _ in range(max_steps):
        if (cancelled and cancelled.is_set()) or time.monotonic()-started>65:break
        call=client.generate_tool_step(query,context)
        if not isinstance(call,dict) or set(call)!={'tool','arguments'}:raise PlanningError('Respuesta de herramientas inválida')
        if call['tool']=='finish':break
        args=call['arguments']
        if isinstance(args,str):
            try:args=json.loads(args)
            except ValueError:raise PlanningError('Argumentos JSON inválidos') from None
        fingerprint=json.dumps([call['tool'],args],sort_keys=True)
        if fingerprint in seen:break
        seen.add(fingerprint)
        try:
            last=execute(lib,call['tool'],args)
            trace.append({'tool':call['tool'],'state':'complete'})
            # Bounded context, intact JSON, no file locations sent to the model.
            compact={k:v for k,v in last.items() if k not in ('source','source_path')}
            if isinstance(compact.get('tracks'),list):compact['tracks']=[{k:v for k,v in t.items() if k in ('id','title','bpm','key','rating','tags')} for t in compact['tracks'][:20]]
            encoded=json.dumps(compact,ensure_ascii=False)
            context['results'].append({'tool':call['tool'],'result':compact if len(encoded)<14000 else {'note':'Resultado extenso; consultar una página menor.'}})
            if call['tool']=='set.plan_selection':break
        except PlanningError as exc:
            trace.append({'tool':call['tool'],'state':'rejected','reason':str(exc)})
            context['results'].append({'tool':call['tool'],'error':str(exc)})
    if last is None:return {'response':'No pude completar la consulta. Revisá la conexión de la colección y probá con filtros concretos.','tool_trace':trace,'applied':False}
    result=response(lib,last,trace)
    if trace and trace[-1]['state']=='rejected':result['response']+=' El último paso no se completó: '+trace[-1]['reason']
    if last.get('track_ids'):result['plan_result']=last
    result['bounded_steps']=max_steps
    return result
