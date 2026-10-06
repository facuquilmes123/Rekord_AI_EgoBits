"""UTF-8 local playlist export. M3U8 stores paths, not Rekordbox cues/grids."""
import hashlib
import os
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit
from ..core.models import PlanningError

def local_path(location):
    parsed = urlsplit(location)
    if parsed.scheme.lower() != 'file' or parsed.netloc.lower() != 'localhost' or parsed.query or parsed.fragment:
        raise PlanningError('Se requiere una ubicación local file://localhost/')
    if re.search(r'%(?![0-9a-fA-F]{2})', parsed.path):
        raise PlanningError('Escape URI inválido')
    path = unquote(parsed.path, encoding='utf-8', errors='strict')
    if any(c in path for c in ('\r', '\n', '\x00')) or not path.startswith('/') or path.startswith('//'):
        raise PlanningError('Ruta local inválida')
    if re.match(r'^/[A-Za-z]:/', path): path = path[1:]
    if os.name == 'nt': path = path.replace('/', '\\')
    return Path(path)

def export_m3u8(lib, result, name, target):
    if target.suffix.lower() != '.m3u8' or target.resolve() == lib.source:
        raise PlanningError('Elegí un archivo M3U8 nuevo')
    if result.get('source_revision') != lib.revision or hashlib.sha256(lib.source.read_bytes()).hexdigest() != lib.revision:
        raise PlanningError('La colección cambió; recargá y recalculá')
    ids = result.get('track_ids', [])
    if not ids or len(ids) != len(set(ids)) or any(i not in lib.tracks for i in ids):
        raise PlanningError('IDs exportados inválidos')
    lines = ['#EXTM3U']
    for tid in ids:
        t = lib.tracks[tid]
        path = local_path(t.location)
        label = f'{t.artist} - {t.title}'.replace('\r', ' ').replace('\n', ' ').replace('\x00', '')
        seconds = round(t.duration) if t.duration is not None else -1
        lines.extend([f'#EXTINF:{seconds},{label}', str(path)])
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x', encoding='utf-8', newline='\n') as file: file.write('\n'.join(lines) + '\n')
    return target
