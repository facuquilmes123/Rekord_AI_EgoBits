"""Evidence-based collection opportunities, with bounded actionable details."""
from collections import Counter
import re
import unicodedata
from ..core.models import PlanningError


def analysis_query(query):
    text=''.join(c for c in unicodedata.normalize('NFD',query.casefold()) if unicodedata.category(c)!='Mn')
    return bool(re.search(r'analiz|analisis',text) and re.search(r'falt|pendient|sin |no .*analiz|no (?:tienen?|tengo|hay)\s+analisis',text))


def metadata_query(query):
    """Recognize missing-field questions without sending whole-library facts to the LLM."""
    text=''.join(c for c in unicodedata.normalize('NFD',query.casefold()) if unicodedata.category(c)!='Mn')
    field=r'(?:genero\w*|etiqueta\w*|bpm|tempo|tonalidad\w*|clave\w*|key)'
    missing=(r'\b(?:falta\w*|pendiente\w*|incomplet\w*|vaci[oa]s?)\b|\ben blanco\b|'
             r'\b(?:sin|no (?:tienen?|tengo|hay))\s+(?:datos? (?:de )?|definir\s+)?'+field+r'\b|'
             r'\b'+field+r'\s+(?:sin (?:definir|asignar|registrar)|no definid[oa]s?)\b')
    if not re.search(missing,text):return None
    fields=[]
    for key,pattern in (('genre',r'\b(genero\w*|etiqueta\w*)\b'),
                        ('bpm',r'\b(bpm|tempo)\b'),
                        ('key',r'\b(tonalidad\w*|clave\w*|key)\b')):
        if re.search(pattern,text):fields.append(key)
    return fields or None


def answer_metadata(lib,fields):
    labels={'genre':'género','bpm':'BPM','key':'tonalidad'}
    groups=catalog(lib)
    counts=[f'{len(groups[key]["track_ids"])} sin {labels[key]}' for key in fields]
    selected=set().union(*(groups[key]['track_ids'] for key in fields))
    rows=[t for t in lib.tracks.values() if t.id in selected][:10]
    response=f'En el XML cargado ({len(lib.tracks)} pistas): '+', '.join(counts)+'.'
    if rows:
        response+='\nPrimeras pistas para corregir:\n'+'\n'.join(f'ID {t.id}: {t.artist or "Sin artista"} — {t.title}' for t in rows)
        if len(selected)>len(rows):response+=f'\nHay {len(selected)-len(rows)} más; abrí el listado completo.'
    response+='\nCompletá esos metadatos en Rekordbox, exportá un XML actualizado y cargalo en Configuración. Esta consulta no modifica la colección.'
    return {'response':response,'applied':False,'answer_mode':'collection_evidence',
            'source_revision':lib.revision,'matched_count':len(selected),
            'suggestions':[{'label':'Ver pistas sin '+labels[key], 'opportunity':key} for key in fields]+
                          [{'label':'Cargar XML actualizado','tab':'tab-config','target':'library-form'}]}


def catalog(lib):
    tracks=list(lib.tracks.values());usage=Counter(i for ids in lib.playlists.values() for i in ids)
    definitions=[
        ('analysis','Revisar análisis', 'Falta BPM o tonalidad en el XML. Es una señal para revisar, no el estado oficial del análisis de Rekordbox.',lambda t:t.bpm is None or not t.key,'Analizá estas pistas en Rekordbox y exportá un XML actualizado. No se inicia un análisis desde esta app.'),
        ('bpm','Completar BPM','Estas pistas no tienen BPM registrado en el XML.',lambda t:t.bpm is None,'Seleccioná las pistas en Rekordbox y ejecutá Analizar pista; después actualizá el XML.'),
        ('key','Completar tonalidades','Estas pistas no tienen tonalidad registrada.',lambda t:not t.key,'Activá el análisis de tonalidad en Rekordbox y actualizá el XML.'),
        ('genre','Etiquetar géneros','Sin género no pueden cumplir el filtro estricto de género.',lambda t:not t.genre,'Completá el género en Rekordbox; después exportá y cargá un XML nuevo.'),
        ('energy','Agregar energía con procedencia','La curva de energía requiere valores verificados, no energía inferida por BPM.',lambda t:t.energy is None,'Configuración → archivo de energías. Usá valores 0..10 asociados al ID y con fuente declarada.'),
        ('artist','Completar artistas','Los artistas vacíos limitan búsquedas y variedad.',lambda t:not t.artist.strip(),'Completá las etiquetas de artista en Rekordbox y actualizá tu XML.'),
        ('duration','Revisar duración','Sin duración no se puede calcular con precisión la duración del set.',lambda t:t.duration is None,'Revisá lectura y análisis del archivo en Rekordbox; luego actualizá el XML.'),
        ('unlisted','Explorar pistas fuera de playlists','Pistas de la colección que no aparecen en ninguna playlist exportada.',lambda t:not usage[t.id],'Podés agregarlas a tu selección y preparar un set. El XML podría omitir playlists que existen en la base real.'),
    ]
    return {key:{'id':key,'title':title,'description':description,'instructions':instructions,
                 'track_ids':[t.id for t in tracks if test(t)]} for key,title,description,test,instructions in definitions}


def native_analysis(lib,discover,offset=0):
    from ..adapters.sqlcipher_read import connection
    paths=discover()['databases']
    if len(paths)!=1:raise PlanningError('No se identificó una base nativa única')
    with connection(paths[0]) as conn:
        total=conn.execute('SELECT count(*) FROM djmdContent WHERE Analysed=0').fetchone()[0]
        rows=conn.execute('SELECT ID,Title,BPM FROM djmdContent WHERE Analysed=0 ORDER BY ID LIMIT 50 OFFSET ?',(offset,)).fetchall()
    return {'id':'analysis','title':'Sin marca nativa de análisis','description':'Lectura de la base real: indicador Analysed=0. Los indicadores no cero pueden representar distintos estados; no se declaran completos sólo por tener una marca.',
            'instructions':'Buscá estas pistas por título en Rekordbox y ejecutá Analizar pista. Después exportá y cargá un XML actualizado.',
            'source_revision':lib.revision,'source':'native_readonly','total':total,'offset':offset,
            'tracks':[{'id':str(tid),'title':title or 'Sin título','artist':lib.tracks[str(tid)].artist if str(tid) in lib.tracks else '',
                       'bpm':bpm/100 if bpm else None,'key':lib.tracks[str(tid)].key if str(tid) in lib.tracks else None,
                       'in_collection':str(tid) in lib.tracks} for tid,title,bpm in rows],
            'next_offset':offset+50 if offset+50<total else None}


def detail(lib,key,offset=0,discover=None):
    if type(offset) is not int or offset<0:raise PlanningError('Página inválida')
    if key=='analysis' and discover:
        try:return native_analysis(lib,discover,offset)
        except (OSError,ValueError,ImportError):pass
    group=catalog(lib).get(key)
    if group is None:raise PlanningError('Oportunidad desconocida')
    ids=group['track_ids'];return {k:v for k,v in group.items() if k!='track_ids'}|{
        'source_revision':lib.revision,'total':len(ids),'offset':offset,
        'tracks':[vars(lib.tracks[i]) for i in ids[offset:offset+50]],'next_offset':offset+50 if offset+50<len(ids) else None}


def answer_analysis(lib,discover=None):
    data=detail(lib,'analysis',discover=discover);bpm=detail(lib,'bpm')['total'];key=detail(lib,'key')['total']
    response=f'En el XML cargado hay {data["total"]} pistas para revisar: {bpm} sin BPM y {key} sin tonalidad (una pista puede faltar en ambos). El XML no certifica cuáles están sin analizar en la base actual de Rekordbox.'
    if data.get('source')=='native_readonly':response=f'En la base real de Rekordbox hay {data["total"]} pistas con el indicador de análisis en cero (Analysed=0). No declaré completos los demás estados. Además, el XML cargado tiene {bpm} pistas sin BPM y {key} sin tonalidad; puede estar desactualizado respecto de la base.'
    if data['tracks']:response+='\n'+ '\n'.join(f'ID {t["id"]}: {t["artist"]} — {t["title"]}' for t in data['tracks'][:10])
    return {'response':response,'applied':False,'answer_mode':'collection_evidence','analysis':data,
            'suggestions':[{'label':'Ver todas las pistas y cómo resolverlo','opportunity':'analysis'},
                           {'label':'Cargar XML actualizado','tab':'tab-config','target':'library-form'}]}
