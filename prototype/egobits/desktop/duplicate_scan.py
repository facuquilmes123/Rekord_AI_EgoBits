"""One cancellable, local full-library scan. Scores are evidence, not probability.

Every available audio file is hashed in full, including differently named tracks.
No metadata score authorizes deletion. The rule returns a reviewable proposal only.
"""
from collections import Counter, defaultdict
import copy
import hashlib
import math
import os
from pathlib import Path
import secrets
import threading
import xml.etree.ElementTree as ET
from ..adapters.m3u8 import local_path
from ..adapters.native_write import digest
from ..core.models import PlanningError

AUDIO_SUFFIXES = {'.mp3', '.wav', '.aiff', '.aif', '.flac', '.m4a', '.ogg', '.aac'}


def fingerprint(stat):
    # Windows stat/fstat can disagree on cached creation time (ctime is not a
    # content-change timestamp there). Identity, size and last-write time agree.
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns,
            stat.st_ctime_ns if os.name != 'nt' else None)


def cue_hash(lib, tid):
    return hashlib.sha256(b''.join(ET.tostring(el) for el in lib.nodes[tid]
                                 if el.tag in ('TEMPO', 'POSITION_MARK'))).hexdigest()


class DuplicateScan:
    def __init__(self):
        self.lock = threading.RLock()
        self.cancelled = threading.Event()
        self.result = None

    def start(self, lib):
        with self.lock:
            if self.result and self.result['state'] == 'running':
                raise PlanningError('Ya hay una verificación en curso. Cancelala o esperá a que termine.')
            if digest(lib.source) != lib.revision:
                raise PlanningError('El XML cambió; recargá la colección.')
            self.cancelled = threading.Event()
            self.result = {'scan_id': secrets.token_hex(16), 'source_revision': lib.revision,
                           'state': 'running', 'phase': 'Archivos', 'total': len(lib.tracks),
                           'processed': 0, 'hashed_files': 0, 'bytes_read': 0,
                           'unavailable': [], 'groups': [], 'entries': {}}
            threading.Thread(target=self._run, args=(lib,), daemon=True).start()
            return self.snapshot()

    def snapshot(self):
        with self.lock:
            if self.result is None: return {'state': 'idle'}
            # File identities are internal; the browser cannot supply trusted hashes.
            return copy.deepcopy({k: v for k, v in self.result.items() if k != 'entries'})

    def cancel(self, scan_id):
        with self.lock:
            if not self.result or self.result['scan_id'] != scan_id:
                raise PlanningError('Verificación desconocida.')
            self.cancelled.set()
            return self.snapshot()

    def _run(self, lib):
        entries, content, names, cache = {}, defaultdict(list), defaultdict(list), {}
        try:
            for tid, track in lib.tracks.items():
                if self.cancelled.is_set(): break
                entry = {'id': tid, 'title': track.title, 'artist': track.artist,
                         'cues_sha256': cue_hash(lib, tid)}
                try:
                    path = local_path(track.location).resolve(strict=True)
                    if not path.is_file() or path.suffix.lower() not in AUDIO_SUFFIXES:
                        raise OSError('No es un archivo de audio local compatible.')
                    before = path.stat()
                    if before.st_size == 0: raise OSError('Archivo vacío.')
                    stamp = fingerprint(before)
                    key = (str(path).casefold(), stamp)
                    sha = cache.get(key)
                    if sha is None:
                        checksum = hashlib.sha256()
                        with path.open('rb') as stream:
                            if fingerprint(os.fstat(stream.fileno())) != stamp:
                                raise OSError('El archivo cambió antes de leerlo.')
                            while chunk := stream.read(1024 * 1024):
                                if self.cancelled.is_set(): raise InterruptedError('Cancelado.')
                                checksum.update(chunk)
                                with self.lock: self.result['bytes_read'] += len(chunk)
                            if fingerprint(os.fstat(stream.fileno())) != stamp:
                                raise OSError('El archivo cambió durante la lectura.')
                        if fingerprint(path.stat()) != stamp:
                            raise OSError('El archivo cambió durante la lectura.')
                        sha = checksum.hexdigest()
                        cache[key] = sha
                        with self.lock: self.result['hashed_files'] += 1
                    entry.update(path=str(path), bytes=before.st_size, sha256=sha, stamp=stamp)
                    content[sha].append(tid)
                except InterruptedError:
                    break
                except (OSError, ValueError) as error:
                    entry['error'] = str(error)
                    with self.lock: self.result['unavailable'].append({'id': tid, 'reason': str(error)})
                entries[tid] = entry
                # Empty metadata must never turn an entire library into one candidate group.
                name = (track.artist.strip().casefold(), track.title.strip().casefold())
                if all(name): names[name].append(tid)
                with self.lock: self.result['processed'] += 1
            groups = []
            confirmed_ids = set()
            for sha, ids in content.items():
                if len(ids) < 2: continue
                confirmed_ids.update(ids)
                rows = [entries[i] for i in ids]
                same_file = len({(r['stamp'][0], r['stamp'][1]) for r in rows}) == 1
                different_cues = len({r['cues_sha256'] for r in rows}) != 1
                groups.append({'group_id': sha, 'score': 100, 'confirmed': True,
                               'same_file_reference': same_file, 'different_cues': different_cues,
                               'classification': 'Referencias al mismo archivo' if same_file else 'Contenido idéntico (SHA-256 completo)',
                               'reason': 'Cues o beatgrids diferentes: revisión manual obligatoria.' if different_cues else 'Coincidencia exacta de todos los bytes.',
                               'tracks': [{k: v for k, v in r.items() if k != 'stamp'} for r in rows]})
            for name, ids in names.items():
                # Retain unresolved members even if others have a confirmed content group.
                if len(ids) < 2 or all(i in confirmed_ids for i in ids) and len({entries[i].get('sha256') for i in ids}) == 1:
                    continue
                tracks = [lib.tracks[i] for i in ids]
                durations = [t.duration for t in tracks]
                bpms = [t.bpm for t in tracks]
                score = 50
                evidence = ['Título y artista iguales']
                if all(x is not None for x in durations) and max(durations) - min(durations) <= 1:
                    score += 20; evidence.append('Duración dentro de 1 segundo')
                if all(x is not None for x in bpms) and max(bpms) - min(bpms) <= .1:
                    score += 10; evidence.append('BPM dentro de 0,1')
                if all(t.key for t in tracks) and len({t.key for t in tracks}) == 1:
                    score += 5; evidence.append('Tonalidad igual')
                groups.append({'group_id': hashlib.sha256(repr(name).encode()).hexdigest(),
                               'score': score, 'confirmed': False, 'different_cues': False,
                               'classification': 'Candidatos por metadatos',
                               'reason': '. '.join(evidence) + '. No autoriza eliminación.',
                               'tracks': [{k: v for k, v in entries[i].items() if k != 'stamp'} for i in ids]})
            with self.lock:
                self.result.update(entries=entries, groups=sorted(groups, key=lambda g: (-g['score'], g['group_id'])),
                                   state='cancelled' if self.cancelled.is_set() else 'complete', phase='Finalizado')
                if not self.cancelled.is_set() and digest(lib.source) != lib.revision:
                    self.result.update(state='stale', error='El XML cambió durante el análisis. Recargá y repetí.')
        except Exception as error:
            with self.lock: self.result.update(state='failed', error=str(error))

    def rule(self, lib, scan_id, threshold):
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 <= threshold <= 100:
            raise PlanningError('El umbral debe ser un número entre 0 y 100.')
        with self.lock:
            result = self.result
            if not result or result['scan_id'] != scan_id or result['state'] != 'complete':
                raise PlanningError('Terminá la verificación completa antes de aplicar una regla.')
            if result['source_revision'] != lib.revision or digest(lib.source) != lib.revision:
                raise PlanningError('La colección cambió; repetí la verificación.')
            selected, protected = [], []
            usage = Counter(tid for ids in lib.playlists.values() for tid in ids)
            for group in result['groups']:
                if group['score'] < threshold: continue
                if not group['confirmed'] or group['different_cues']:
                    protected.append({'group_id': group['group_id'], 'score': group['score'],
                                      'track_ids': [t['id'] for t in group['tracks']], 'reason': group['reason']})
                    continue
                rows = group['tracks']
                for row in rows:
                    try:
                        if fingerprint(Path(row['path']).stat()) != result['entries'][row['id']]['stamp']:
                            raise PlanningError('Un archivo cambió después del análisis. Repetí la verificación.')
                    except OSError:
                        raise PlanningError('Un archivo ya no está disponible. Repetí la verificación.') from None
                # Preserve the most referenced track. Deterministic tie break.
                keeper = min(rows, key=lambda r: (-usage[r['id']], r['id']))
                for row in rows:
                    if row['id'] == keeper['id']: continue
                    selected.append({'id': row['id'], 'keeper_id': keeper['id'], 'score': 100,
                                     'path': row['path'], 'keeper_path': keeper['path'], 'sha256': group['group_id'],
                                     'remove_file': row['path'].casefold() != keeper['path'].casefold() and not group['same_file_reference']})
            return {'scan_id': scan_id, 'source_revision': lib.revision, 'threshold': threshold,
                    'comparison': 'mayor o igual', 'selected': selected, 'protected': protected,
                    'references': len(selected), 'files': len({r['path'].casefold() for r in selected if r['remove_file']}),
                    'delete_enabled': False,
                    'delete_reason': 'Prepará el respaldo para consolidar las referencias verificadas y retirar archivos a recuperación local. Rekordbox y sus agentes deben estar cerrados. Los metadatos o vínculos nativos diferentes se protegen durante la preparación.'}
