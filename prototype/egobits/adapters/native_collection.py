"""Coherent, read-only Rekordbox snapshots. Never uses immutable on a live DB."""
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from urllib.parse import quote
from .sqlcipher_read import connection
from .xml_adapter import Library
from ..core.models import PlanningError


def integer(value, default=None):
    try: return int(value) if value is not None and value != '' else default
    except (ValueError, TypeError): return default


def rating(value):
    value=integer(value)
    if value in (0,1,2,3,4,5):return value
    # DeviceSQL uses 0..5; master.db versions may use the 0/51/102/... scale.
    if value in (51,102,153,204,255):return value//51
    return None


class NativeCollection:
    def __init__(self, database, cache_directory, connector=connection):
        self.database=Path(database).resolve(strict=True)
        self.cache=Path(cache_directory)
        self.connector=connector
        self.lock=threading.RLock()
        self.library=None
        self.checked_at=0
        self.stamp=None

    def _stamp(self):
        result=[]
        for path in (self.database,Path(str(self.database)+'-wal')):
            try:
                s=path.stat();result.append((s.st_ino,s.st_size,s.st_mtime_ns))
            except FileNotFoundError:result.append(None)
        return tuple(result)

    def load(self, force=False):
        with self.lock:
            if not force and self.library and time.monotonic()-self.checked_at<3:return self.library
            stamp=self._stamp()
            if not force and self.library and stamp==self.stamp:
                self.checked_at=time.monotonic();return self.library
            with self.connector(self.database) as conn:
                conn.execute('BEGIN')
                tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                def rows(table):
                    if table not in tables:return []
                    cursor=conn.execute('SELECT * FROM "'+table+'" LIMIT 500001')
                    names=[c[0] for c in cursor.description];items=cursor.fetchall()
                    if len(items)>500000:raise PlanningError('La tabla supera el límite seguro de 500.000 registros')
                    result=[dict(zip(names,row)) for row in items]
                    return [r for r in result if not integer(r.get('rb_local_deleted'),0)]
                content=rows('djmdContent')
                if 'djmdContent' not in tables:raise PlanningError('Base sin colección compatible')
                artists={str(r['ID']):r.get('Name','') for r in rows('djmdArtist')}
                genres={str(r['ID']):r.get('Name','') for r in rows('djmdGenre')}
                keys={str(r['ID']):r.get('ScaleName','') for r in rows('djmdKey')}
                tags=rows('djmdMyTag');links=rows('djmdSongMyTag');cues=rows('djmdCue')
                phrases=rows('djmdSongPhrase');playlists=rows('djmdPlaylist');members=rows('djmdSongPlaylist')
            root=ET.Element('DJ_PLAYLISTS',Version='1.0.0')
            collection=ET.SubElement(root,'COLLECTION',Entries=str(len(content)))
            extras={};tagmap={str(r['ID']):r for r in tags};tags_by_track=defaultdict(list)
            for link in links:
                tag=tagmap.get(str(link.get('MyTagID')))
                if tag:
                    parent=tagmap.get(str(tag.get('ParentID')), {})
                    tags_by_track[str(link.get('ContentID'))].append({'id':str(tag['ID']),'name':tag.get('Name') or '', 'category':parent.get('Name') or '', 'category_id':str(parent.get('ID') or '')})
            cues_by_track=defaultdict(list);phrases_by_track=defaultdict(list)
            for cue in cues:cues_by_track[str(cue.get('ContentID'))].append(cue)
            for phrase in phrases:phrases_by_track[str(phrase.get('ContentID'))].append({k:v for k,v in phrase.items() if isinstance(v,(str,int,float,bool,type(None)))})
            for row in content:
                tid=str(row['ID']);path=str(row.get('FolderPath') or '')
                bpm=integer(row.get('BPM'));length=integer(row.get('Length'))
                attributes={'TrackID':tid,'Name':str(row.get('Title') or ''),'Artist':artists.get(str(row.get('ArtistID')),'') or '',
                            'Genre':genres.get(str(row.get('GenreID')),'') or '', 'Tonality':keys.get(str(row.get('KeyID')),'') or '',
                            'Location':'file://localhost/'+quote(path.replace('\\','/').lstrip('/'),safe='/:') if path else ''}
                if bpm:attributes['AverageBpm']=str(bpm/100)
                if length is not None:attributes['TotalTime']=str(length)
                node=ET.SubElement(collection,'TRACK',attributes)
                normalized=[]
                for cue in cues_by_track[tid]:
                    start=integer(cue.get('InMsec'));end=integer(cue.get('OutMsec'));kind=integer(cue.get('Kind'),0)
                    if start is None or start<0:continue
                    loop=bool(end is not None and end>start)
                    item={'start':start/1000,'end':end/1000 if loop else None,'hot_cue':kind if 1<=kind<=8 else None,
                          'name':str(cue.get('Comment') or ''),'color':cue.get('Color'),'active_loop':bool(cue.get('ActiveLoop')),'loop':loop,'source':'djmdCue'}
                    normalized.append(item)
                    attr={'Name':item['name'],'Type':'4' if loop else '0','Start':str(item['start']),'Num':str(kind-1 if item['hot_cue'] else -1)}
                    if loop:attr['End']=str(item['end'])
                    ET.SubElement(node,'POSITION_MARK',attr)
                extras[tid]={'rating':rating(row.get('Rating')),'play_count':integer(row.get('DJPlayCount')),
                    'date_added':str(row.get('StockDate') or row.get('created_at') or ''),'tags':tags_by_track[tid],
                    'cues':normalized,'phrase_records':phrases_by_track[tid],
                    'analysis_path':str(row.get('AnalysisDataPath') or ''),
                    'beatgrid_locked':None if row.get('BeatGridLock') is None else bool(integer(row.get('BeatGridLock'),0)),
                    'source':'master.db'}
            playlist_root=ET.SubElement(ET.SubElement(root,'PLAYLISTS'),'NODE',Name='ROOT',Type='0')
            by_id={str(r['ID']):r for r in playlists};membership=defaultdict(list)
            for member in sorted(members,key=lambda r:integer(r.get('TrackNo'),0)):
                tid=str(member.get('ContentID'))
                if tid in extras:membership[str(member.get('PlaylistID'))].append(tid)
            nodes={};visiting=set()
            def playlist_node(pid):
                if pid in nodes:return nodes[pid]
                if pid in visiting:raise PlanningError('Árbol de playlists cíclico')
                visiting.add(pid);row=by_id[pid];parent=str(row.get('ParentID'))
                container=playlist_node(parent) if parent in by_id else playlist_root
                # Attribute 1 is a folder; smart playlists are materialized from available membership.
                folder=integer(row.get('Attribute'),0)==1
                name=str(row.get('Name') or pid)
                if any(n.get('Name')==name for n in container):name+=' ['+pid+']'
                node=ET.SubElement(container,'NODE',Name=name,Type='0' if folder else '1',KeyType='0')
                if not folder:
                    for tid in membership[pid]:ET.SubElement(node,'TRACK',Key=tid)
                nodes[pid]=node;visiting.remove(pid);return node
            for pid in by_id:playlist_node(pid)
            # Real libraries may contain control characters illegal in XML 1.0.
            # Sanitize only the disposable snapshot, never the original DB.
            sanitized=0
            for element in root.iter():
                for key,value in list(element.attrib.items()):
                    clean=''.join(c if c in '\t\n\r' or 0x20<=ord(c)<=0xd7ff or 0xe000<=ord(c)<=0xfffd or 0x10000<=ord(c)<=0x10ffff else '\ufffd' for c in value)
                    if clean!=value:sanitized+=1;element.set(key,clean)
            # Include metadata in snapshot identity even if base XML fields did not change.
            metadata_hash=hashlib.sha256(json.dumps(extras,sort_keys=True,ensure_ascii=True).encode()).hexdigest()
            root.set('EgoBitsMetadataRevision',metadata_hash)
            payload=ET.tostring(root,encoding='utf-8',xml_declaration=True)
            digest=hashlib.sha256(payload).hexdigest();self.cache.mkdir(parents=True,exist_ok=True)
            target=self.cache/(hashlib.sha256(str(self.database).encode()).hexdigest()+'.xml')
            if not self.library or self.library.revision!=digest or not target.exists():
                with tempfile.NamedTemporaryFile(dir=self.cache,delete=False,suffix='.tmp') as out:
                    temp=Path(out.name);out.write(payload);out.flush();os.fsync(out.fileno())
                os.replace(temp,target)
            lib=Library(target);lib.native_metadata=extras;lib.source_kind='native_snapshot';lib.database_path=self.database
            lib.sanitized_snapshot_fields=sanitized
            lib.snapshot_at=datetime.now(timezone.utc).isoformat();lib.native_tags=[{'id':str(t['ID']),'name':t.get('Name') or '', 'parent_id':str(t.get('ParentID') or ''),'category':tagmap.get(str(t.get('ParentID')),{}).get('Name') or ''} for t in tags]
            self.library=lib;self.checked_at=time.monotonic();self.stamp=stamp
            return lib
