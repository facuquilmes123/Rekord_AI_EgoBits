"""Read existing ANLZ beat grids and phrases; never generate fake analysis."""
from functools import lru_cache
from pathlib import Path
import math


def analysis_path(lib,track_id):
    raw=getattr(lib,'native_metadata',{}).get(track_id,{}).get('analysis_path','')
    if not raw:return None
    path=Path(raw)
    if path.is_file():return path.resolve()
    database=getattr(lib,'database_path',None)
    if database:
        root=(Path(database).parent/'share').resolve()
        candidate=(root/raw.replace('\\','/').lstrip('/')).resolve()
        if candidate.is_relative_to(root) and candidate.is_file():return candidate
    return None


@lru_cache(maxsize=128)
def _read(paths):
    from pyrekordbox.anlz import AnlzFile
    times=[];phrase_tag=None
    for name,size,mtime in paths:
        if size>32*1024*1024:raise ValueError('ANLZ demasiado grande')
        data=AnlzFile.parse_file(name)
        if data['PQTZ']:times=[float(x) for x in data.get_tag('PQTZ').times]
        if data['PSSI']:phrase_tag=data.get_tag('PSSI').content
    phrases=[]
    if phrase_tag is not None and times:
        high={1:'intro',2:'up',3:'down',5:'chorus',6:'outro'}
        mid={1:'intro',2:'verse_1',3:'verse_2',4:'verse_3',5:'verse_4',6:'verse_5',7:'verse_6',8:'bridge',9:'chorus',10:'outro'}
        low={1:'intro',2:'verse_1',3:'verse_1b',4:'verse_1c',5:'verse_2',6:'verse_2b',7:'verse_2c',8:'bridge',9:'chorus',10:'outro'}
        labels={1:high,2:mid,3:low}.get(int(phrase_tag.mood),{})
        for entry in phrase_tag.entries:
            index=int(entry.beat)-1
            if 0<=index<len(times) and math.isfinite(times[index]):
                phrases.append({'label':labels.get(int(entry.kind),'unknown'),'kind':int(entry.kind),'mood':int(phrase_tag.mood),
                                'beat':index+1,'start_seconds':times[index],'source':'ANLZ/PSSI+PQTZ'})
    return {'beatgrid_present':bool(times),'phrases':phrases,'note':'Frases de Rekordbox con tiempos del beatgrid.' if phrases else 'Sin frases PSSI con tiempos disponibles.'}


def analysis_structure(lib,track_id):
    path=analysis_path(lib,track_id)
    if path is None:return {'beatgrid_present':False,'phrases':[],'note':'No hay archivo de análisis accesible.'}
    try:
        paths=[]
        for candidate in (path.with_suffix('.DAT'),path.with_suffix('.EXT')):
            if candidate.is_file():
                stat=candidate.stat();paths.append((str(candidate),stat.st_size,stat.st_mtime_ns))
        return _read(tuple(paths))
    except Exception as exc:
        return {'beatgrid_present':False,'phrases':[],'note':'Análisis no legible: '+type(exc).__name__}
