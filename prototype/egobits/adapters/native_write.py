"""Create a new playlist on an encrypted staging copy with a verified backup.

No track deletion, audio mutation, key persistence or writes while Rekordbox is open.
Publication holds exclusive Windows handles and records crash recovery state.
"""
from pathlib import Path
import hashlib
import json
import secrets
import shutil
import threading
import time
import unicodedata
import os
import re
from .windows_exclusive import WindowsExclusiveFiles
from .sqlcipher_read import connection, inspect
from .m3u8 import local_path
from ..core.models import PlanningError


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(1024 * 1024): result.update(chunk)
    return result.hexdigest()


def normalized(path):
    return unicodedata.normalize('NFC', str(Path(path).resolve())).casefold()


def save_journal(work, manifest):
    pending = work / 'journal.pending'
    with pending.open('w', encoding='utf-8') as stream:
        json.dump(manifest, stream, indent=2)
        stream.flush(); os.fsync(stream.fileno())
    os.replace(pending, work / 'journal.json')


def durable_copy(source, target):
    shutil.copy2(source, target)
    with target.open('r+b') as stream: os.fsync(stream.fileno())


def unchanged_tables(path):
    result = {}
    with connection(path) as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        for table in tables:
            if table in {'djmdPlaylist', 'djmdSongPlaylist', 'agentRegistry', 'sqlite_sequence'}: continue
            quoted = '"' + table.replace('"', '""') + '"'
            # Sort row digests: logical invariance independent of SQLite row layout.
            rows = sorted(hashlib.sha256(repr(row).encode('utf-8')).digest() for row in conn.execute('SELECT * FROM ' + quoted))
            result[table] = hashlib.sha256(b''.join(rows)).hexdigest()
    return result


def playlist_rows(path):
    """Adding a playlist must preserve every pre-existing playlist/membership."""
    with connection(path) as conn:
        return {table:{repr(row) for row in conn.execute('SELECT * FROM '+table)}
                for table in ('djmdPlaylist','djmdSongPlaylist')}


def schema_signature(path):
    with connection(path) as conn:
        schema=conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name").fetchall()
        version=conn.execute('PRAGMA user_version').fetchone()[0]
    return hashlib.sha256(repr((version,schema)).encode('utf-8')).hexdigest()


class NativePlaylistWriter:
    def __init__(self, root, process_state, discover):
        self.root = Path(root).resolve()
        self.process_state, self.discover = process_state, discover
        self.previews = {}
        self.lock = threading.Lock()
        self.stop_requested = threading.Event()

    def guard(self, db, recovery=False):
        if self.stop_requested.is_set(): raise PlanningError('Rekord AI se está cerrando. Volvé a abrirlo para continuar.')
        if self.process_state() != 'closed':
            raise PlanningError('Cerrá Rekordbox y salí de sus agentes de sincronización desde la bandeja. Luego volvé a intentar. El aviso permite solicitar cierre normal o una finalización con confirmación explícita.')
        discovered = self.discover()
        paths = {Path(p).resolve() for p in discovered['databases']}
        if db not in paths: raise PlanningError('La base ya no coincide con la instalación detectada')
        versions = [row['version'] for row in discovered['installations']]
        if not versions or not all(isinstance(v,str) and re.fullmatch(r'[67]\.\d+(?:\.\d+){0,2}',v.strip()) for v in versions):
            raise PlanningError('Sólo se admite el esquema de Rekordbox 6/7; versión no identificada')
        for journal in (self.root/'transaction-recovery').glob('*/journal.json'):
            try: state=json.loads(journal.read_text(encoding='utf-8'))['state']
            except (OSError, ValueError, KeyError): raise PlanningError('Hay un recibo de recuperación ilegible; revisá los respaldos') from None
            if state in ('checkpointing','restoring','recovery_required'):
                raise PlanningError('Hay una recuperación interrumpida: restaurá su respaldo antes de continuar')
        for suffix in ('-wal', '-shm', '-journal'):
            if Path(str(db) + suffix).exists():
                raise PlanningError('Hay transacciones pendientes; respaldá y recuperalas desde Configuración → Base y procesos')
        if self.root.exists() and not recovery:
            for journal in self.root.glob('*/journal.json'):
                if json.loads(journal.read_text(encoding='utf-8'))['state'] in ('publishing', 'recovery_required'):
                    raise PlanningError('Hay una publicación interrumpida: recuperar el respaldo antes de continuar')

    def ensure_space(self, files):
        total=sum(path.stat().st_size for path in files)
        ancestor=self.root
        while not ancestor.exists():ancestor=ancestor.parent
        reserve=max(64*1024**2,total)
        if shutil.disk_usage(ancestor).free < 2*total+reserve or shutil.disk_usage(files[0].parent).free < reserve:
            raise PlanningError('Espacio insuficiente para respaldo, propuesta y margen de recuperación; liberá espacio antes de continuar')

    def approval_preview(self, token):
        if not isinstance(token,str) or not re.fullmatch('[0-9a-f]{32}',token):raise PlanningError('Propuesta inválida')
        with self.lock:
            item=self.previews.get(token)
            if not item or item[0]<time.monotonic():raise PlanningError('La propuesta venció')
            manifest=json.loads((item[1]/'journal.json').read_text(encoding='utf-8'))
            operation='restore' if manifest['state']=='prepared_restore' else manifest.get('operation','create_playlist')
            if manifest['state'] not in ('prepared','prepared_restore'):raise PlanningError('Propuesta no aplicable')
            fingerprint=hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            summary=f"{manifest['name']}\nBase: {manifest['database']}\nRespaldo: {item[1]/'backup'}\n"
            summary+=f"Pistas: {len(manifest.get('track_ids',[]))}" if operation=='create_playlist' else 'Se restaurará la colección completa y se desharán cambios posteriores.'
            if operation=='consolidate_duplicates':
                summary=f"Consolidar {len(manifest['mapping'])} referencias duplicadas.\nRetirar {len(manifest['audio_moves'])} archivos de sus rutas originales hacia recuperación local.\nLas playlists apuntarán a la pista conservada.\nBase: {manifest['database']}\nRespaldo: {item[1]/'backup'}\nEl XML original se conserva."
            return {'token':token,'operation':operation,'digest':fingerprint,'summary':summary}

    def prepare(self, lib, ids, name, db_path):
        with self.lock:
            db = Path(db_path).resolve(strict=True)
            self.guard(db)
            if not isinstance(name, str) or not name.strip() or len(name) > 200 or any(ord(c)<32 for c in name):
                raise PlanningError('Nombre de playlist inválido')
            if not isinstance(ids, list) or not 1 <= len(ids) <= 100 or any(type(i) is not str for i in ids) or len(set(ids)) != len(ids) or any(i not in lib.tracks for i in ids):
                raise PlanningError('Elegí de 1 a 100 pistas conocidas y únicas')
            if digest(lib.source) != lib.revision: raise PlanningError('El XML cambió; recargá la colección')
            aux = db.parent / 'masterPlaylists6.xml'
            if not aux.is_file(): raise PlanningError('Falta masterPlaylists6.xml: no se publica una playlist incompleta')
            self.ensure_space([db,aux])
            hashes = {db.name: digest(db), aux.name: digest(aux)}
            token = secrets.token_hex(16)
            work = self.root / token
            backup, stage = work / 'backup', work / 'stage'
            backup.mkdir(parents=True); stage.mkdir()
            save_journal(work,{'state':'preparing','created_at':time.time(),'database':str(db),'files':hashes,'name':name.strip()})
            for file in (db, aux):
                durable_copy(file, backup / file.name)
                durable_copy(file, stage / file.name)
                if digest(backup/file.name) != hashes[file.name]: raise PlanningError('Respaldo no coincide')
            self.guard(db)
            if any(digest(db.parent / n) != h for n,h in hashes.items()): raise PlanningError('La colección cambió durante el respaldo')
            before = unchanged_tables(stage / db.name)
            playlists_before = playlist_rows(stage / db.name)
            with connection(stage / db.name) as conn:
                rows = conn.execute('SELECT ID, FolderPath FROM djmdContent').fetchall()
                if conn.execute('SELECT count(*) FROM djmdPlaylist WHERE Name=? AND ParentID=?',(name.strip(),'root')).fetchone()[0]:
                    raise PlanningError('Ya existe una playlist con ese nombre en la raíz')
            paths = {}
            for native_id, path in rows:
                if path: paths.setdefault(normalized(path), []).append(str(native_id))
            mapped = []
            for tid in ids:
                matches = paths.get(normalized(local_path(lib.tracks[tid].location)), [])
                if len(matches) != 1: raise PlanningError('Una ruta no tiene correspondencia única en la colección real')
                mapped.append(matches[0])
            if len(set(mapped)) != len(mapped): raise PlanningError('Varias pistas apuntan al mismo registro nativo')
            from pyrekordbox import Rekordbox6Database
            native = Rekordbox6Database(path=stage / db.name, db_dir=stage)
            try:
                playlist = native.create_playlist(name.strip())
                pid = str(playlist.ID)
                for native_id in mapped: native.add_to_playlist(playlist, native_id)
                native.commit()
            except Exception:
                native.rollback()
                raise PlanningError('La propuesta nativa falló en copia; la base original está intacta') from None
            finally:
                native.close(); native.engine.dispose()
            if unchanged_tables(stage/db.name) != before:
                raise PlanningError('La operación alteraría datos fuera de playlists; publicación bloqueada')
            playlists_after = playlist_rows(stage/db.name)
            if any(not rows.issubset(playlists_after[table]) for table,rows in playlists_before.items()):
                raise PlanningError('La propuesta alteraría playlists existentes; publicación bloqueada')
            if len(playlists_after['djmdPlaylist']-playlists_before['djmdPlaylist'])!=1 or len(playlists_after['djmdSongPlaylist']-playlists_before['djmdSongPlaylist'])!=len(mapped):
                raise PlanningError('La propuesta incluye playlists o membresías adicionales; publicación bloqueada')
            if inspect(stage/db.name)['integrity'] != 'ok': raise PlanningError('La copia modificada no supera integridad')
            with connection(stage/db.name) as conn:
                order = [str(r[0]) for r in conn.execute('SELECT ContentID FROM djmdSongPlaylist WHERE PlaylistID=? ORDER BY TrackNo',(pid,))]
            if order != mapped: raise PlanningError('El orden nativo no coincide con la propuesta')
            self.guard(db)
            if inspect(backup/db.name)['integrity'] != 'ok': raise PlanningError('El respaldo no supera integridad')
            for n in hashes:
                with (stage/n).open('r+b') as stream: os.fsync(stream.fileno())
            manifest = {'state':'prepared','created_at':time.time(),'database':str(db),'files':hashes,'staged':{n:digest(stage/n) for n in hashes},'playlist_id':pid,'name':name.strip(),'track_ids':mapped,'xml_revision':lib.revision,'schema_sha256':schema_signature(backup/db.name)}
            save_journal(work, manifest)
            self.previews[token] = (time.monotonic()+600, work, lib.revision)
            return {'token':token,'playlist_name':name.strip(),'tracks':len(mapped),'backup_directory':str(backup),'integrity':'ok','expires_seconds':600,'operation':'create_playlist','requires_confirmation':True}

    def apply(self, token, revision):
        if not isinstance(token,str) or not re.fullmatch('[0-9a-f]{32}',token): raise PlanningError('Propuesta inválida')
        with self.lock:
            item = self.previews.pop(token, None)
            if not item or item[0] < time.monotonic() or item[2] != revision:
                raise PlanningError('La revisión venció o cambió. Creá una nueva propuesta con respaldo.')
            work = item[1]
            manifest = json.loads((work/'journal.json').read_text(encoding='utf-8'))
            if manifest['state'] != 'prepared': raise PlanningError('Propuesta ya utilizada')
            return self._publish(work, manifest)

    def _publish(self, work, manifest, recovery=False):
        db = Path(manifest['database']).resolve(strict=True)
        self.guard(db, recovery=recovery)
        if set(manifest['files']) != {'master.db', 'masterPlaylists6.xml'}:
            raise PlanningError('Recibo de respaldo inválido')
        for name, value in manifest['files'].items():
            if digest(work/'backup'/name) != value: raise PlanningError('El respaldo fue alterado')
            if digest(work/'stage'/name) != manifest['staged'][name]: raise PlanningError('La propuesta fue alterada')
        if inspect(work/'stage'/db.name)['integrity'] != 'ok': raise PlanningError('La propuesta no supera integridad')
        if manifest.get('repaired_xml') and digest(manifest['repaired_xml'])!=manifest['repaired_xml_sha256']:
            raise PlanningError('La copia XML reparada fue alterada')
        staged_schema=schema_signature(work/'stage'/db.name)
        try: current_schema=schema_signature(db)
        except PlanningError:
            if not recovery or not manifest.get('recovery_schema_unknown'):raise
            origin=json.loads((self.root/manifest['restores']/'journal.json').read_text(encoding='utf-8'))
            if origin['state'] not in ('publishing','recovery_required') or origin.get('schema_sha256')!=staged_schema:
                raise PlanningError('La recuperación no tiene un recibo válido de operación interrumpida')
            current_schema=staged_schema
        if current_schema!=staged_schema:raise PlanningError('El esquema de la colección cambió; publicación bloqueada')
        with WindowsExclusiveFiles([db.parent/name for name in manifest['files']]) as held:
            self.guard(db, recovery=recovery)
            if any(held.digest(n) != h for n,h in manifest['files'].items()):
                raise PlanningError('La base cambió desde el respaldo. Revisá nuevamente.')
            from .audio_recovery import AudioRecovery
            with AudioRecovery(manifest) as audio:
                return self._publish_locked(work,manifest,held,audio)

    def _publish_locked(self,work,manifest,held,audio):
        db=Path(manifest['database'])
        manifest['state'] = 'publishing'; save_journal(work, manifest)
        try:
            audio.move()
            for name in manifest['files']:
                self.guard(db, recovery=True)
                held.write_from(name, work/'stage'/name)
            if any(held.digest(n) != h for n,h in manifest['staged'].items()):
                raise PlanningError('La verificación posterior falló')
            manifest['state'] = 'applied'; save_journal(work, manifest)
        except Exception:
            try:
                # Rollback holds both handles even if a process started meanwhile.
                for name in manifest['files']: held.write_from(name, work/'backup'/name)
                if any(held.digest(n) != h for n,h in manifest['files'].items()): raise OSError('Rollback verification failed')
                audio.rollback()
                manifest['state'] = 'rolled_back'; save_journal(work, manifest)
            except Exception:
                manifest['state'] = 'recovery_required'; save_journal(work, manifest)
                raise PlanningError('La operación quedó pendiente de recuperación. Cerrá Rekordbox y restaurá este respaldo desde la app.') from None
            raise PlanningError('La operación se canceló y se restauró el respaldo verificado.') from None
        if manifest['state']=='applied':
            for name in manifest['files']:
                try:(work/'stage'/name).unlink()
                except OSError:pass
        return {'operation_id':work.name,'state':manifest['state'],'backup_directory':str(work/'backup'),
                'playlist_name':manifest['name'],'repaired_xml':manifest.get('repaired_xml'),
                'source_xml':manifest.get('source_xml')}

    def backups(self):
        result = []
        for journal in self.root.glob('*/journal.json'):
            try:
                m = json.loads(journal.read_text(encoding='utf-8'))
                if set(m['files']) != {'master.db','masterPlaylists6.xml'}: raise ValueError('Recibo inválido')
                valid = all(digest(journal.parent/'backup'/n)==h for n,h in m['files'].items())
                if m.get('audio_moves') and m['state'] in ('applied','publishing','recovery_required'):
                    from .audio_recovery import restore_plan
                    restore_plan(m)
                result.append({'id':journal.parent.name,'name':m['name'],'created_at':m.get('created_at',0),'state':m['state'],'verified':valid})
            except (OSError, KeyError, ValueError):
                result.append({'id':journal.parent.name,'name':'Respaldo ilegible','created_at':0,'state':'invalid','verified':False})
        return sorted(result,key=lambda x:x['created_at'],reverse=True)

    def prepare_restore(self, operation_id):
        with self.lock:
            if not isinstance(operation_id,str) or not re.fullmatch('[0-9a-f]{32}',operation_id): raise PlanningError('Respaldo inválido')
            origin = self.root/operation_id
            m = json.loads((origin/'journal.json').read_text(encoding='utf-8'))
            db = Path(m['database']).resolve(strict=True); self.guard(db, recovery=True)
            if set(m['files']) != {'master.db','masterPlaylists6.xml'}: raise PlanningError('Recibo inválido')
            for n,h in m['files'].items():
                if digest(origin/'backup'/n)!=h: raise PlanningError('El respaldo fue alterado')
            if inspect(origin/'backup'/db.name)['integrity']!='ok': raise PlanningError('El respaldo no supera integridad')
            backup_schema=schema_signature(origin/'backup'/db.name)
            recovery_schema_unknown=False
            try:current_schema=schema_signature(db)
            except PlanningError:
                if m['state'] not in ('publishing','recovery_required') or m.get('schema_sha256')!=backup_schema:raise
                current_schema=backup_schema;recovery_schema_unknown=True
            if m.get('schema_sha256',backup_schema)!=backup_schema or current_schema!=backup_schema:
                raise PlanningError('El respaldo pertenece a otro esquema de colección; restauración bloqueada')
            self.ensure_space([db,db.parent/'masterPlaylists6.xml'])
            token = secrets.token_hex(16); work = self.root/token
            (work/'backup').mkdir(parents=True); (work/'stage').mkdir()
            current = {n:digest(db.parent/n) for n in m['files']}
            save_journal(work,{'state':'preparing_restore','created_at':time.time(),'database':str(db),'files':current,'name':'Restauración de '+m['name']})
            for n in m['files']:
                durable_copy(db.parent/n,work/'backup'/n)
                durable_copy(origin/'backup'/n,work/'stage'/n)
                if digest(work/'backup'/n)!=current[n] or digest(work/'stage'/n)!=m['files'][n]: raise PlanningError('La colección cambió durante el respaldo')
            manifest={'state':'prepared_restore','created_at':time.time(),'database':str(db),'files':current,'staged':m['files'],'name':'Restauración de '+m['name'],'restores':operation_id,'schema_sha256':backup_schema}
            if recovery_schema_unknown:manifest['recovery_schema_unknown']=True
            if m.get('audio_moves'):
                from .audio_recovery import restore_plan
                checks,moves=restore_plan(m)
                manifest.update(audio_checks=checks,audio_moves=moves)
            if m.get('source_xml'):manifest['source_xml']=m['source_xml']
            save_journal(work,manifest)
            self.previews[token]=(time.monotonic()+600,work,'restore')
            return {'token':token,'backup_directory':str(work/'backup'),'name':manifest['name'],'warning':'Se recuperará la colección completa de ese respaldo. Los cambios posteriores se desharán; el estado actual queda respaldado automáticamente.'}

    def restore(self, token):
        if not isinstance(token,str) or not re.fullmatch('[0-9a-f]{32}',token): raise PlanningError('Revisión inválida')
        with self.lock:
            item=self.previews.pop(token,None)
            if not item or item[0]<time.monotonic() or item[2]!='restore': raise PlanningError('Revisión de restauración vencida')
            work=item[1];manifest=json.loads((work/'journal.json').read_text(encoding='utf-8'))
            result=self._publish(work,manifest,recovery=True)
            origin=self.root/manifest['restores'];previous=json.loads((origin/'journal.json').read_text(encoding='utf-8'))
            previous['state']='restored';save_journal(origin,previous)
            return result

