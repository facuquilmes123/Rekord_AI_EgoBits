"""Collection insights and conservative, explicit duplicate verification."""
from collections import Counter, defaultdict
import hashlib
from pathlib import Path
import time
import xml.etree.ElementTree as ET
from ..adapters.m3u8 import local_path
from ..core.analysis import audit_library, find_duplicates, audit_setlist, explain_transition
from ..core.models import PlanningError

def insights(lib):
    tracks = list(lib.tracks.values())
    audit = audit_library(tracks)
    genres = Counter(t.genre or 'Sin género' for t in tracks)
    keys = Counter(t.key or 'Sin tonalidad' for t in tracks)
    bins = Counter()
    for t in tracks:
        if t.bpm is None: bins['Sin BPM'] += 1
        else:
            start = int(t.bpm // 10) * 10
            bins[f'{start}–{start + 9}'] += 1
    suggestions = []
    from .opportunities import catalog
    for group in catalog(lib).values():
        if group['track_ids']:suggestions.append({'text':f"{len(group['track_ids'])} pistas · {group['title']}", 'action':'opportunity','opportunity':group['id'],'count':len(group['track_ids']),'description':group['description']})
    if genres:
        genre, count = genres.most_common(1)[0]
        if genre != 'Sin género': suggestions.append({'text': f'Prepará un set de {genre}: {count} pistas en tu colección.', 'action': 'genre', 'genre': genre})
    candidates = find_duplicates(tracks)
    if candidates: suggestions.append({'text': f'{len(candidates)} grupos comparten título y artista. Verificá archivos antes de decidir.', 'action': 'duplicates'})
    return {**audit, 'source_revision': lib.revision, 'genres': dict(genres.most_common()), 'keys': dict(keys.most_common()),
            'bpm_distribution': dict(sorted(bins.items())), 'artists_count': len({t.artist.casefold() for t in tracks if t.artist}),
            'playlists_count': len(lib.playlists), 'hours': round(sum(t.duration or 0 for t in tracks) / 3600, 2),
            'missing_genre_count': sum(not t.genre for t in tracks), 'energy_count': sum(t.energy is not None for t in tracks),
            'suggestions': suggestions, 'duplicate_candidates': candidates}

def verify_duplicates(lib, ids):
    if not isinstance(ids, list) or not 2 <= len(ids) <= 100 or len(ids) != len(set(ids)) or any(i not in lib.tracks for i in ids):
        raise PlanningError('Seleccioná de 2 a 100 IDs únicos de esta colección')
    if hashlib.sha256(lib.source.read_bytes()).hexdigest() != lib.revision:
        raise PlanningError('La colección cambió; volvé a cargarla antes de verificar')
    groups, unavailable = defaultdict(list), []
    budget, deadline = 2 * 1024**3, time.monotonic() + 30
    for tid in ids:
        t = lib.tracks[tid]
        try:
            path = local_path(t.location).resolve(strict=True)
            if not path.is_file() or path.suffix.lower() not in ('.mp3', '.wav', '.aiff', '.aif', '.flac', '.m4a', '.ogg', '.aac'):
                raise OSError('Archivo de audio no disponible')
            before = path.stat()
            if before.st_size <= 0: raise OSError('Archivo vacío')
            if before.st_size > budget: raise OSError('Límite de verificación de 2 GiB alcanzado')
            digest = hashlib.sha256()
            with path.open('rb') as file:
                while chunk := file.read(1024 * 1024):
                    if time.monotonic() > deadline: raise OSError('Tiempo de verificación agotado')
                    digest.update(chunk)
            budget -= before.st_size
            after = path.stat()
            if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
                raise OSError('Archivo cambiado durante la verificación')
            cue_data = b''.join(ET.tostring(el) for el in lib.nodes[tid] if el.tag in ('TEMPO', 'POSITION_MARK'))
            groups[digest.hexdigest()].append({'id': tid, 'title': t.title, 'artist': t.artist, 'path': str(path),
                                              'bytes': after.st_size, 'cues_sha256': hashlib.sha256(cue_data).hexdigest()})
        except (OSError, ValueError) as exc: unavailable.append({'id': tid, 'reason': str(exc)})
    confirmed = []
    for digest, rows in groups.items():
        if len(rows) < 2: continue
        same_path = len({r['path'].casefold() for r in rows}) == 1
        confirmed.append({'sha256': digest, 'tracks': rows, 'same_file_reference': same_path,
                          'different_cues': len({r['cues_sha256'] for r in rows}) > 1,
                          'classification': 'Referencias al mismo archivo' if same_path else 'Archivos idénticos byte a byte'})
    return {'confirmed': confirmed, 'unavailable': unavailable, 'source_revision': lib.revision,
            'delete_enabled': False, 'delete_reason': 'El borrado requiere retirar las referencias de la base real y respaldar también la música para poder restaurarla. En Mi colección podés verificar todos los archivos, revisar una regla por porcentaje y confirmar una eliminación recuperable de duplicados idénticos protegida por respaldo.',
            'note': 'Hashes distintos no prueban que sean canciones diferentes: pueden tener distinta codificación o etiquetas. No se eliminan por título/artista.'}

def draft(lib, ids, revision):
    if revision != lib.revision: raise PlanningError('La colección cambió; recargá las pistas')
    if not isinstance(ids, list) or not 1 <= len(ids) <= 100 or len(ids) != len(set(ids)) or any(i not in lib.tracks for i in ids):
        raise PlanningError('Elegí de 1 a 100 pistas distintas de la colección')
    tracks = [lib.tracks[i] for i in ids]
    transitions = []
    for a, b in zip(tracks, tracks[1:]):
        e = explain_transition(a, b)
        transitions.append({'from': a.id, 'to': b.id, 'bpm_delta': e['bpm_delta'], 'harmonic': e['harmonic_score']})
    return {'track_ids': ids, 'tracks': [vars(t) for t in tracks], 'source_revision': lib.revision,
            'duration_sum_seconds': sum(t.duration for t in tracks) if all(t.duration is not None for t in tracks) else None,
            'score': 'Manual', 'mode': 'manual', 'transitions': transitions, 'excluded': {}, 'audit': audit_setlist(tracks),
            'warnings': ['Orden elegido por el DJ. Revisá las transiciones antes de exportar.']}

def answer_help(query, status):
    import unicodedata
    import re
    text = ''.join(c for c in unicodedata.normalize('NFD', query.casefold()) if unicodedata.category(c) != 'Mn')
    if re.search(r'(?:podes|puedes|poder|sabes|saber|estas)\s+(?:escuchar|escuchando|leer|leyendo)|\bescuchas\b|(?:que|cual).*\b(?:sonando|reproduciendo)\b|\bestoy reproduciendo\b|\btu microfono\b',text):
        if status.get('telemetry_available'):
            return 'Hay un proveedor de pista actual conectado. Sólo sugiero cuando confirma reproducción audible y una señal reciente. Eso identifica la pista; no implica escuchar ni grabar audio.'
        return 'Todavía no tengo una lectura certificada del canal master. En Configuración podés activar seguimiento de nuevas pistas del historial para recibir sugerencias: el historial puede tener demora y no confirma qué deck es audible. También hay un ensayo local de identificación de audio WASAPI, comparando pistas seleccionadas; requiere elegir la salida y aún debe validarse con tu equipo. Elegí una pista manualmente para recomendar desde tu biblioteca por BPM, tonalidad, género y energía. El popup optativo de historial o piloto siempre indica que el master no está confirmado. Los Toast de pista audible confirmada requieren un proveedor validado; ningún piloto los habilita por sí solo.'
    if any(w in text for w in ('que podes hacer', 'que puedes hacer', 'tus funciones')) or text.strip(' ?¿!.') in ('ayuda','como funciona'):
        return 'Puedo buscar pistas, listar y comparar playlists, planificar por BPM o energía, explicar transiciones, revisar metadatos y sugerir temas compatibles. En Preparar un set podés usar playlists o toda tu colección, seguir el asistente y armar un orden manual. Exporto XML y M3U8. La creación directa de playlists requiere Rekordbox cerrado, respaldo verificado y confirmación. En Mi colección verifico todos los archivos y ordeno duplicados por evidencia. Las sugerencias por historial usan metadatos de tu colección; no certifican el master audible. El borrado recuperable de duplicados idénticos requiere Rekordbox cerrado, respaldo y confirmación.'
    if any(w in text for w in ('eliminar', 'borrar')) and any(w in text for w in ('duplicad', 'archivo', 'pista')):
        return 'En Mi colección, Verificar toda la colección analiza todos los archivos locales y compara SHA-256 completo, incluso con nombres diferentes. Los resultados se ordenan por puntaje de evidencia. Podés revisar una regla por porcentaje que conserva una pista por grupo; nombres parecidos y cues diferentes quedan protegidos. Podés revisar y confirmar la eliminación recuperable de duplicados idénticos con respaldo automático, consolidación de referencias y restauración. Los candidatos por metadatos no autorizan borrado.'
    if ('m3u8' in text or 'xml' in text) and any(w in text for w in ('export', 'guardar', 'diferencia')):
        return 'XML conserva cues y beatgrids para el Bridge. M3U8 guarda el orden y las rutas de audio para importar la playlist; no transporta cues ni beatgrids. Calculá o armá una propuesta y elegí el formato al exportar.'
    return None
