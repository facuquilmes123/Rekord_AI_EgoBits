"""Conservative duplicate consolidation on an encrypted staging copy.

Only identical files with equivalent native metadata and supported relationships
can be consolidated. Unknown dependencies, cues, tags and device/cloud state are
protected rather than guessed. Audio moves are reversible under Windows handles.
"""
from collections import Counter
from pathlib import Path
import copy
import json
import secrets
import time
import xml.etree.ElementTree as ET
from .native_write import digest, normalized, durable_copy, save_journal, schema_signature
from .sqlcipher_read import connection, inspect
from ..core.models import PlanningError

RELATIONS={'djmdSongPlaylist','djmdSongHistory'}
STATS={'usn','rb_local_usn','rb_data_status','rb_local_data_status','rb_local_deleted','rb_local_synced',
       'updated_at','created_at'}
IDENTITY={'ID','UUID','FolderPath','FileNameL','FileNameS',
          'DateAdded','DateCreated','StockDate'}


def quote(name): return '"'+name.replace('"','""')+'"'


def snapshot(path):
    with connection(path) as conn:
        result={}
        for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            cols=[r[1] for r in conn.execute('PRAGMA table_info('+quote(table)+')')]
            result[table]=(cols,list(conn.execute('SELECT * FROM '+quote(table))))
        return result


def native_mapping(before, selected, dependencies=None):
    cols,rows=before['djmdContent']; index={str(r[cols.index('ID')]):dict(zip(cols,r)) for r in rows}
    mapping={}; protected=[]
    for proposal in selected:
        removed=str(proposal['id']);keeper=str(proposal['keeper_id'])
        a=index.get(removed);b=index.get(keeper)
        reason=None
        if not a or not b: reason='Los IDs XML no coinciden con la colección nativa actual.'
        elif normalized(a['FolderPath'])!=normalized(proposal['path']) or normalized(b['FolderPath'])!=normalized(proposal['keeper_path']):
            reason='La ruta nativa cambió o no coincide con el XML.'
        elif a.get('AnalysisDataPath')!=b.get('AnalysisDataPath'):
            reason='Análisis nativos diferentes: es necesario verificar beatgrids y datos ANLZ antes de consolidar.'
        elif any(a[c]!=b[c] for c in cols if c not in STATS|IDENTITY):
            reason='Metadatos nativos diferentes: se preservan ambas versiones.'
        elif any(row.get(c) for row in (a,b) for c in ('rb_local_deleted','rb_local_synced','ContentLink')):
            reason='La pista tiene estado de sincronización o vinculación que requiere revisión.'
        else:
            for table,(names,items) in before.items():
                if table=='djmdContent':continue
                # Check both declared content links and UUID links; unexpected
                # relationships are not silently deleted by the ORM.
                links=[c for c in names if c in ('ContentID','ContentUUID','MasterSongID') or 'content' in c.casefold() and c.casefold().endswith(('id','uuid'))]
                links=list(set(links)|set((dependencies or {}).get(table,{})))
                for c in links:
                    target=(dependencies or {}).get(table,{}).get(c,'UUID' if c.casefold().endswith('uuid') else 'ID')
                    value=a.get(target)
                    if value and any(str(row[names.index(c)])==str(value) for row in items) and (table not in RELATIONS or c!='ContentID'):
                        reason=f'Dependencia protegida en {table}: cues, tags o vínculo no consolidable automáticamente.'
                        break
                if reason:break
        if reason:protected.append({'id':removed,'keeper_id':keeper,'reason':reason})
        else:mapping[removed]=keeper
    if set(mapping)&set(mapping.values()):raise PlanningError('La propuesta contiene ciclos o pistas conservadas que se retirarían')
    return mapping,protected


def verify_changes(before, after, mapping):
    if set(before)!=set(after):raise PlanningError('La consolidación alteró el esquema')
    for table,(cols,rows) in before.items():
        newcols,newrows=after[table]
        if cols!=newcols:raise PlanningError('El esquema cambió durante la propuesta')
        if table=='agentRegistry':continue
        if table=='djmdContent':
            expected=[r for r in rows if str(r[cols.index('ID')]) not in mapping]
        elif table in RELATIONS:
            expected=[]
            for row in rows:
                values=list(row);i=cols.index('ContentID');values[i]=mapping.get(str(values[i]),values[i]);expected.append(tuple(values))
        else:expected=rows
        # Only remapped memberships may change sync counters/timestamps.
        if table in RELATIONS:
            keep=[i for i,c in enumerate(cols) if c not in STATS]
            expected=[tuple(r[i] for i in keep) for r in expected]
            newrows=[tuple(r[i] for i in keep) for r in newrows]
        if Counter(map(repr,expected))!=Counter(map(repr,newrows)):
            raise PlanningError(f'La operación cambiaría datos no autorizados en {table}; original intacto')


def prepare(writer,lib,rule,db_path):
    with writer.lock:
        db=Path(db_path).resolve(strict=True);writer.guard(db)
        if digest(lib.source)!=lib.revision:raise PlanningError('El XML cambió; recargá y verificá otra vez')
        if not rule['selected']:raise PlanningError('No hay duplicados verificados y seguros en esta regla')
        aux=db.parent/'masterPlaylists6.xml'
        if not aux.is_file():raise PlanningError('Falta el archivo de playlists nativo')
        writer.ensure_space([db,aux])
        hashes={p.name:digest(p) for p in (db,aux)}
        token=secrets.token_hex(16);work=writer.root/token
        (work/'backup').mkdir(parents=True);(work/'stage').mkdir()
        save_journal(work,{'state':'preparing','created_at':time.time(),'database':str(db),'files':hashes,'name':'Consolidación de duplicados'})
        for p in (db,aux):
            durable_copy(p,work/'backup'/p.name);durable_copy(p,work/'stage'/p.name)
            if digest(work/'backup'/p.name)!=hashes[p.name]:raise PlanningError('El respaldo no coincide')
        before=snapshot(work/'stage'/db.name)
        with connection(work/'stage'/db.name) as conn:
            dependencies={t:{r[3]:r[4] for r in conn.execute('PRAGMA foreign_key_list('+quote(t)+')') if r[2]=='djmdContent'} for t in before}
            triggers=conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()
        if triggers:raise PlanningError('La base tiene triggers no certificados para consolidación; revisión manual requerida')
        mapping,protected=native_mapping(before,rule['selected'],dependencies)
        if not mapping:raise PlanningError('Todos los grupos requieren revisión manual: '+ '; '.join(p['reason'] for p in protected[:3]))
        chosen=[r for r in rule['selected'] if r['id'] in mapping]
        checks={};moves={}
        contents=before['djmdContent'];native_paths={normalized(r[contents[0].index('FolderPath')]):[] for r in contents[1] if r[contents[0].index('FolderPath')]}
        for row in contents[1]:
            if row[contents[0].index('FolderPath')]:native_paths[normalized(row[contents[0].index('FolderPath')])].append(str(row[contents[0].index('ID')]))
        for r in chosen:
            for name in ('path','keeper_path'):
                p=Path(r[name]).resolve(strict=True)
                if p.is_symlink() or p.stat().st_nlink!=1:raise PlanningError('Enlaces de archivos protegidos: revisar manualmente')
                if digest(p)!=r['sha256']:raise PlanningError('Un archivo cambió después de verificarlo')
                checks[str(p)]=r['sha256']
            if r['remove_file']:
                p=Path(r['path']).resolve(strict=True)
                # Never remove a path still needed by an unselected native row.
                if any(i not in mapping for i in native_paths[normalized(p)]):
                    raise PlanningError('Otra referencia nativa necesita un archivo seleccionado; se conserva')
                destination=p.parent/'.rekord-ai-recovery'/token/p.name
                destination.parent.mkdir(parents=True,exist_ok=True)
                if destination.exists() or destination.parent.resolve()!=p.parent/'.rekord-ai-recovery'/token:
                    raise PlanningError('El destino de recuperación no es seguro')
                moves[str(p)]={'source':str(p),'target':str(destination),'sha256':r['sha256']}
        from pyrekordbox import Rekordbox6Database
        from pyrekordbox.db6 import tables
        native=Rekordbox6Database(path=work/'stage'/db.name,db_dir=work/'stage')
        try:
            for removed,keeper in mapping.items():
                for table in (tables.DjmdSongPlaylist,tables.DjmdSongHistory):
                    for row in native.query(table).filter(table.ContentID==removed).all():row.ContentID=keeper
                native.session.flush()
                native.delete(native.query(tables.DjmdContent).filter(tables.DjmdContent.ID==removed).one())
            native.commit()
        except Exception:
            native.rollback();raise PlanningError('La consolidación falló en copia; base y música originales intactas') from None
        finally:native.close();native.engine.dispose()
        verify_changes(before,snapshot(work/'stage'/db.name),mapping)
        if digest(work/'stage'/aux.name)!=hashes[aux.name]:raise PlanningError('La consolidación alteraría el índice de playlists; original intacto')
        if inspect(work/'stage'/db.name)['integrity']!='ok':raise PlanningError('La copia no supera integridad')
        tree=ET.ElementTree(copy.deepcopy(lib.root))
        collection=tree.getroot().find('COLLECTION')
        for track in list(collection):
            if track.get('TrackID') in mapping:collection.remove(track)
        collection.set('Entries',str(len(collection)))
        for node in tree.getroot().iter('TRACK'):
            if node.get('Key') in mapping:node.set('Key',mapping[node.get('Key')])
        repaired=work/'collection-consolidated.xml'
        tree.write(repaired,encoding='utf-8',xml_declaration=True)
        # XML source remains immutable; publish a new working collection instead.
        writer.guard(db)
        if any(digest(db.parent/n)!=h for n,h in hashes.items()):raise PlanningError('La base cambió durante la preparación')
        manifest={'state':'prepared','operation':'consolidate_duplicates','created_at':time.time(),'database':str(db),
                  'files':hashes,'staged':{n:digest(work/'stage'/n) for n in hashes},'name':'Consolidación de duplicados',
                  'track_ids':list(mapping),'mapping':mapping,'xml_revision':lib.revision,'source_xml':str(lib.source),
                  'repaired_xml':str(repaired),'repaired_xml_sha256':digest(repaired),'audio_checks':checks,
                  'audio_moves':list(moves.values()),'schema_sha256':schema_signature(work/'backup'/db.name)}
        save_journal(work,manifest);writer.previews[token]=(time.monotonic()+600,work,lib.revision)
        return {'token':token,'references':len(mapping),'files':len(moves),'protected':protected,
                'backup_directory':str(work/'backup'),'repaired_xml':str(repaired),'requires_confirmation':True}
