"""DeviceSQL read/export with staged additions, verified backup and native approval."""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import shutil
import string
import struct
import re
import threading
import time
from ..core.models import PlanningError
from ..vendor.rekordbox_pdb import Database
from ..vendor.rekordbox_pdb.edit import PdbEditor
from .native_write import digest
from .windows_exclusive import WindowsExclusiveFiles
from .m3u8 import local_path
from .analysis_structure import analysis_path

PDB=Path('PIONEER/rekordbox/export.pdb')


def contained(root,relative):
    if not isinstance(relative,str) or '\x00' in relative or ':' in relative:raise PlanningError('Ruta USB inválida')
    parts=PurePosixPath(relative.replace('\\','/').lstrip('/'))
    if '..' in parts.parts:raise PlanningError('La ruta sale del dispositivo')
    result=(Path(root)/str(parts)).resolve()
    if not result.is_relative_to(Path(root).resolve()):raise PlanningError('La ruta sale del dispositivo')
    return result


def parse_pdb(path):
    path=Path(path)
    if path.stat().st_size>256*1024*1024:raise PlanningError('DeviceSQL supera 256 MiB')
    try:return Database(path.read_bytes())
    except (ValueError,IndexError,KeyError,OverflowError,TypeError,struct.error) as exc:raise PlanningError('DeviceSQL no válido: '+type(exc).__name__) from None


class DeviceLibrary:
    def __init__(self,root):
        self.root=Path(root).resolve(strict=True);self.path=contained(self.root,str(PDB));self.db=parse_pdb(self.path)
        self.revision=digest(self.path)

    def inspect(self,limit=100,offset=0):
        from ..core.intelligence import pagination
        pagination(limit,offset)
        tracks={t.id:t for t in self.db.tracks};nodes={p.id:p for p in self.db.playlist_tree}
        orphans=[asdict(e) for e in self.db.playlist_entries if e.track_id not in tracks or e.playlist_id not in nodes]
        rows=[]
        for track in self.db.tracks[offset:offset+limit]:
            try:
                audio=contained(self.root,track.file_path);analysis=contained(self.root,track.analyze_path) if track.analyze_path else None
                exists=audio.is_file() and audio.stat().st_size>0;analyzed=bool(analysis and analysis.is_file())
            except (ValueError,OSError):exists=analyzed=False
            rows.append({'id':str(track.id),'title':track.title,'bpm':track.tempo/100,'file_available':exists,'analysis_available':analyzed,'rating':track.rating})
        return {'source':'DeviceSQL','source_revision':self.revision,'total_tracks':len(tracks),
                'playlists':[{'id':str(p.id),'name':p.name,'folder':bool(p.is_folder),'parent_id':str(p.parent_id)} for p in nodes.values()],
                'orphan_count':len(orphans),'orphans':orphans[:100],'tracks':rows,'offset':offset,
                'next_offset':offset+len(rows) if offset+len(rows)<len(tracks) else None,
                'device_library_plus_present':(self.root/'PIONEER/rekordbox/exportLibrary.db').exists(),
                'note':'Archivos comprobados por página. Device Library Plus es independiente; los cambios DeviceSQL no se replican a esa base.'}


class UsbExports:
    def __init__(self,backup_root,process_state,locker=WindowsExclusiveFiles):
        self.root=Path(backup_root);self.process_state=process_state;self.locker=locker;self.lock=threading.Lock()
        self.devices={};self.proposals={}

    def register(self,root):
        device=DeviceLibrary(root);key=hashlib.sha256(str(device.root).encode()).hexdigest()[:20]
        self.devices[key]=device.root
        return {'device_id':key,'root':str(device.root),'source_revision':device.revision}

    def discover(self):
        found=[]
        if os.name=='nt':
            for letter in string.ascii_uppercase:
                root=Path(letter+':/')
                try:
                    if (root/PDB).is_file():found.append(self.register(root))
                except (OSError,ValueError):continue
        return {'devices':found,'note':'Seleccioná un dispositivo exportado por Rekordbox. La detección no modifica archivos.'}

    def device(self,device_id):
        if not isinstance(device_id,str) or device_id not in self.devices:raise PlanningError('Elegí un USB detectado o seleccionado por vos')
        return DeviceLibrary(self.devices[device_id])

    def backups(self):
        result=[]
        if self.root.exists():
            for folder in self.root.iterdir():
                try:
                    if not folder.is_dir() or not (folder/'manifest.json').is_file():continue
                    m=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
                    if (folder/'original.pdb').is_file():result.append({'operation_id':folder.name,'device_root':m['device_root'],'name':m['name']})
                except (OSError,ValueError,KeyError):continue
        return {'backups':result}

    def prepare_restore(self,operation_id):
        if self.process_state()!='closed':raise PlanningError('Cerrá Rekordbox y sus agentes antes de restaurar')
        if not isinstance(operation_id,str) or len(operation_id)!=32 or any(c not in string.hexdigits for c in operation_id):raise PlanningError('Respaldo desconocido')
        with self.lock:
            previous=contained(self.root,operation_id);m=json.loads((previous/'manifest.json').read_text(encoding='utf-8'))
            saved=previous/'original.pdb'
            if digest(saved)!=m['original_sha256']:raise PlanningError('Respaldo alterado')
            parse_pdb(saved)
            root=Path(m['device_root']).resolve(strict=True);target=contained(root,str(PDB))
            if root.stat().st_dev!=m['volume_id']:raise PlanningError('El volumen no coincide con el respaldo')
            token=secrets.token_hex(16);folder=self.root/token;folder.mkdir(parents=True)
            current_hash=digest(target);shutil.copy2(target,folder/'original.pdb');shutil.copy2(saved,folder/'proposed.pdb')
            if digest(folder/'original.pdb')!=current_hash:raise PlanningError('El dispositivo cambió durante el respaldo')
            proposal={'token':token,'operation':'usb_restore','device_root':str(root),'volume_id':m['volume_id'],
                'original_sha256':current_hash,'proposed_sha256':digest(saved),'playlist_id':None,'track_ids':[],
                'additions':[],'expires_at':time.time()+600,'name':'Restaurar respaldo '+operation_id}
            proposal['digest']=hashlib.sha256(json.dumps(proposal,sort_keys=True).encode()).hexdigest()
            (folder/'manifest.json').write_text(json.dumps(proposal,indent=2),encoding='utf-8');self.proposals[token]=proposal
            return self.approval_preview(token)

    def prepare(self,device_id,name,device_track_ids=None,lib=None,track_ids=None):
        if self.process_state()!='closed':raise PlanningError('Cerrá Rekordbox y sus agentes antes de preparar una escritura USB')
        if not isinstance(name,str) or not name.strip() or len(name)>120 or any(ord(c)<32 for c in name):raise PlanningError('Nombre de playlist inválido')
        with self.lock:
            device=self.device(device_id)
            if device.inspect(limit=1)['orphan_count']:raise PlanningError('El USB tiene referencias huérfanas: exportalo nuevamente desde Rekordbox antes de escribir')
            if (device.root/'PIONEER/rekordbox/exportLibrary.db').exists():
                raise PlanningError('USB con Device Library Plus: usá exportación desde Rekordbox para mantener ambas bases sincronizadas')
            ids=device_track_ids or [];new_ids=track_ids or []
            if not isinstance(ids,list) or not isinstance(new_ids,list) or not 1<=len(ids)+len(new_ids)<=100:raise PlanningError('Elegí entre 1 y 100 pistas')
            if len(set(ids))!=len(ids) or len(set(new_ids))!=len(new_ids):raise PlanningError('La selección contiene IDs repetidos')
            existing={str(t.id):t for t in device.db.tracks}
            if any(not isinstance(i,str) or i not in existing for i in ids):raise PlanningError('ID de dispositivo inexistente')
            if new_ids and (lib is None or any(not isinstance(i,str) or i not in lib.tracks for i in new_ids)):raise PlanningError('ID de colección inexistente')
            token=secrets.token_hex(16);folder=self.root/token;folder.mkdir(parents=True)
            backup=folder/'original.pdb';shutil.copy2(device.path,backup)
            if digest(backup)!=device.revision:raise PlanningError('El USB cambió durante el respaldo')
            editor=PdbEditor(backup.read_bytes());selected=[int(i) for i in ids];additions=[]
            for tid in ids:
                track=existing[tid]
                if not contained(device.root,track.file_path).is_file() or not track.analyze_path or not contained(device.root,track.analyze_path).is_file():
                    raise PlanningError('Una pista del USB no tiene audio/análisis accesible')
            for tid in new_ids:
                track=lib.tracks[tid];source=local_path(track.location).resolve(strict=True);anlz=analysis_path(lib,tid)
                if anlz is None:raise PlanningError('La exportación nueva necesita el análisis original de Rekordbox; conectá la colección viva y analizá esa pista')
                if source.suffix.lower() not in ('.mp3','.wav','.aiff','.aif','.m4a'):raise PlanningError('Formato no verificado para nueva exportación DeviceSQL')
                import av
                with av.open(str(source)) as media:
                    if not media.streams.audio:raise PlanningError('Archivo sin audio')
                    audio=media.streams.audio[0];sample_rate=audio.codec_context.sample_rate;bitrate=round((audio.bit_rate or 0)/1000)
                    if sample_rate not in (44100,48000,88200,96000):raise PlanningError('Frecuencia no verificada para reproductores DeviceSQL')
                    codec=audio.codec_context.name;pcm=re.fullmatch(r'pcm_s(16|24)(?:le|be)',codec)
                    if source.suffix.lower() in ('.wav','.aif','.aiff') and not pcm:raise PlanningError('Exportación PCM verificada sólo para 16/24 bits enteros')
                    if source.suffix.lower()=='.m4a' and codec!='aac':raise PlanningError('Exportación M4A verificada sólo con codec AAC')
                    sample_depth=int(pcm[1]) if pcm else 16
                basename=hashlib.sha256((tid+str(source)).encode()).hexdigest()[:24]
                relative=f'Contents/RekordAI-{token}/{basename}{source.suffix.lower()}'
                staged=contained(folder,relative);staged.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,staged)
                file_hash=digest(source)
                if digest(staged)!=file_hash:raise PlanningError('El audio cambió durante la copia')
                additions.append({'relative':relative,'sha256':file_hash,'bytes':staged.stat().st_size})
                analysis_relative=f'PIONEER/USBANLZ/RekordAI-{token}/{basename}/ANLZ0000.DAT'
                from .anlz_relocate import relocate,tags
                for extension in ('.DAT','.EXT','.2EX'):
                    original=anlz.with_suffix(extension)
                    if not original.is_file():continue
                    if original.stat().st_size>32*1024*1024:raise PlanningError('Archivo ANLZ demasiado grande')
                    data=relocate(original.read_bytes(),'/'+relative)
                    rel=str(Path(analysis_relative).with_suffix(extension)).replace('\\','/')
                    target=contained(folder,rel);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
                    tags(target.read_bytes())
                    additions.append({'relative':rel,'sha256':digest(target),'bytes':target.stat().st_size})
                selected.append(editor.add_track(title=track.title,artist=track.artist,genre=track.genre,key=track.key,
                    file_path='/'+relative,analyze_path='/'+analysis_relative,tempo=round((track.bpm or 0)*100),duration=round(track.duration or 0),file_size=source.stat().st_size,sample_rate=sample_rate,bitrate=bitrate,sample_depth=sample_depth))
            pid=editor.create_playlist(name.strip())
            for tid in selected:editor.add_to_playlist(pid,tid)
            staged_pdb=folder/'proposed.pdb';staged_pdb.write_bytes(editor.to_bytes());parsed=parse_pdb(staged_pdb)
            actual=[e.track_id for e in sorted(parsed.playlist_entries,key=lambda r:r.entry_index) if e.playlist_id==pid]
            if actual!=selected:raise PlanningError('La playlist preparada no coincide con la selección')
            manifest={'token':token,'operation':'usb_export','device_id':device_id,'device_root':str(device.root),'volume_id':device.root.stat().st_dev,
                'original_sha256':device.revision,'proposed_sha256':digest(staged_pdb),'playlist_id':pid,'track_ids':selected,'additions':additions,
                'expires_at':time.time()+600,'name':name.strip()}
            manifest['digest']=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
            (folder/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');self.proposals[token]=manifest
            return self.approval_preview(token)

    def approval_preview(self,token):
        if not isinstance(token,str) or token not in self.proposals:raise PlanningError('Propuesta USB desconocida')
        m=self.proposals[token]
        if time.time()>m['expires_at']:raise PlanningError('La propuesta USB venció')
        summary=(f"Restaurar DeviceSQL en {m['device_root']}. Se conserva un respaldo del estado actual y todos los archivos de música." if m['operation']=='usb_restore' else f"Crear «{m['name']}» con {len(m['track_ids'])} pistas en {m['device_root']}. Se copiarán {len(m['additions'])} archivos nuevos. Respaldo verificado disponible.")
        return {'token':token,'digest':m['digest'],'operation':m['operation'],
                'summary':summary+' No retirar el USB durante la operación.',
                'tracks':len(m['track_ids']),'new_files':len(m['additions']),'backup_directory':str(self.root/token),'hardware_verified':False}

    def apply(self,token):
        with self.lock:
            self.approval_preview(token);m=self.proposals[token];folder=self.root/token
            if self.process_state()!='closed':raise PlanningError('Rekordbox o sus agentes están abiertos')
            root=Path(m['device_root']).resolve(strict=True);target=contained(root,str(PDB))
            if root.stat().st_dev!=m['volume_id']:raise PlanningError('El dispositivo fue reemplazado')
            if digest(folder/'original.pdb')!=m['original_sha256'] or digest(folder/'proposed.pdb')!=m['proposed_sha256']:raise PlanningError('El respaldo o propuesta fue alterado')
            required=sum(a['bytes'] for a in m['additions'])+(folder/'proposed.pdb').stat().st_size
            if shutil.disk_usage(root).free<required+16*1024*1024:raise PlanningError('No hay espacio suficiente en el USB')
            copied=[]
            # Exclusive handle blocks concurrent writers; backups also recover power loss.
            with self.locker([target]) as locked:
                if locked.digest(target.name)!=m['original_sha256']:raise PlanningError('El USB cambió después de preparar la propuesta')
                try:
                    for item in m['additions']:
                        src=contained(folder,item['relative']);dst=contained(root,item['relative'])
                        if digest(src)!=item['sha256'] or dst.exists():raise PlanningError('Archivo preparado alterado o destino ocupado')
                        dst.parent.mkdir(parents=True,exist_ok=True)
                        with src.open('rb') as incoming,dst.open('xb') as outgoing:
                            shutil.copyfileobj(incoming,outgoing);outgoing.flush();os.fsync(outgoing.fileno())
                        copied.append(dst)
                        if digest(dst)!=item['sha256']:raise PlanningError('La copia USB no coincide')
                    locked.write_from(target.name,folder/'proposed.pdb')
                    if locked.digest(target.name)!=m['proposed_sha256']:raise PlanningError('La publicación USB no coincide')
                except Exception:
                    locked.write_from(target.name,folder/'original.pdb')
                    if locked.digest(target.name)!=m['original_sha256']:raise PlanningError('Restauración USB incompleta; usá el respaldo indicado')
                    raise
            self.proposals.pop(token,None)
            (folder/'applied.json').write_text(json.dumps({'state':'applied','copied_files':len(copied)}),encoding='utf-8')
            return {'state':'applied','playlist_id':m['playlist_id'],'tracks':len(m['track_ids']),'backup_directory':str(folder),
                    'warning':'Validado estructuralmente; ensayá el USB en el reproductor antes del show. Rekordbox puede reemplazar estos cambios al sincronizar.'}
