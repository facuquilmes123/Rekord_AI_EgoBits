from __future__ import annotations
import copy
import hashlib
import math
import re
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote, urlsplit
from ..core.models import Track, PlanningError
from ..core.planner import normalize_key, number

XML_LIMIT_BYTES=256*1024*1024


class _XmlReader:
    def __init__(self,stream):
        self.stream=stream;self.checksum=hashlib.sha256();self.size=0;self.tail=b''

    def read(self,size=65536):
        chunk=self.stream.read(min(size,65536) if size>=0 else 65536)
        self.size+=len(chunk)
        if self.size>XML_LIMIT_BYTES:raise PlanningError('XML demasiado grande (máximo 256 MiB)')
        if b'\x00' in chunk:raise PlanningError('El XML debe estar codificado en UTF-8')
        inspected=(self.tail+chunk).upper()
        if b'<!DOCTYPE' in inspected or b'<!ENTITY' in inspected:
            raise PlanningError('DTD y entidades externas no admitidas')
        self.tail=inspected[-16:];self.checksum.update(chunk)
        return chunk


class Library:
    """Representación inmutable en memoria de una instantánea XML de Rekordbox."""
    def __init__(self, source: Path, energies: dict[str, dict[str, Any]] | None = None):
        self.source = source.resolve()
        before=self.source.stat()
        if before.st_size>XML_LIMIT_BYTES:raise PlanningError('XML demasiado grande (máximo 256 MiB)')
        try:
            with self.source.open('rb') as stream:
                reader=_XmlReader(stream)
                self.root=ET.parse(reader).getroot()
                self.revision=reader.checksum.hexdigest()
            after=self.source.stat()
            if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
                raise PlanningError('El XML cambió durante la carga; volvé a cargarlo')
        except ET.ParseError as e:
            raise PlanningError(f'XML malformado: {e}')
        if self.root.tag != 'DJ_PLAYLISTS':
            raise PlanningError('Formato XML no reconocido; debe ser DJ_PLAYLISTS')

        self.nodes: dict[str, ET.Element] = {}
        self.tracks: dict[str, Track] = {}
        self.playlists: dict[str, list[str]] = {}
        energies = energies or {}
        if not isinstance(energies, dict) or any(not isinstance(row, dict) for row in energies.values()):
            raise PlanningError('Energías: se requiere un objeto por TrackID')

        for el in self.root.findall('./COLLECTION/TRACK'):
            tid = el.get('TrackID', '')
            if not tid or tid in self.tracks:
                raise PlanningError('TrackID ausente o duplicado')
            en = energies.get(tid, {})
            value = en.get('value')
            if value is not None:
                if (isinstance(value, bool) or
                    not isinstance(value, (float, int)) or
                    not math.isfinite(value) or
                    not 0 <= value <= 10 or
                    not en.get('source')):
                    raise PlanningError('Energía exige valor 0..10 y fuente declarada')
            self.nodes[tid] = el
            self.tracks[tid] = Track(
                id=tid,
                title=el.get('Name', ''),
                artist=el.get('Artist', ''),
                bpm=number(el.get('AverageBpm')),
                key=normalize_key(el.get('Tonality')),
                genre=el.get('Genre', '').strip().casefold(),
                duration=number(el.get('TotalTime')),
                location=el.get('Location', ''),
                energy=float(value) if value is not None else None,
                energy_source=en.get('source')
            )

        locations: dict[str, list[str]] = {}
        for tid, t in self.tracks.items():
            locations.setdefault(t.location, []).append(tid)

        def walk(node: ET.Element, path: list[str]):
            name = node.get('Name', '')
            here = path + [name]
            if node.get('Type') == '1':
                key = '/'.join(here)
                if key in self.playlists:
                    raise PlanningError('Ruta de playlist ambigua')
                ids = []
                for t in node.findall('TRACK'):
                    ref = t.get('Key', '')
                    if node.get('KeyType', '0') == '1':
                        found = locations.get(ref, [])
                        if len(found) != 1:
                            raise PlanningError('Referencia por ubicación ambigua o ausente')
                        ref = found[0]
                    if ref not in self.tracks:
                        raise PlanningError('Playlist referencia un TrackID inexistente')
                    ids.append(ref)
                self.playlists[key] = ids
            else:
                for child in node.findall('NODE'):
                    walk(child, here)

        for node in self.root.findall('./PLAYLISTS/NODE'):
            walk(node, [])

    def pool(self, paths: list[str]) -> list[Track]:
        """Obtiene la unión ordenada y sin duplicados de pistas para las playlists dadas."""
        if not isinstance(paths, (list, tuple)) or not all(isinstance(p, str) for p in paths) or not paths:
            raise PlanningError('Elegí al menos una playlist')
        for p in paths:
            if p not in self.playlists:
                raise PlanningError('Playlist no encontrada: ' + p)
        ids = dict.fromkeys(t for p in paths for t in self.playlists[p])
        return [self.tracks[i] for i in ids]

def export_xml(lib: Library, result: dict[str, Any], name: str, target: Path) -> Path:
    """Exporta un archivo XML nuevo compatible con el Bridge de Rekordbox.
    Conserva todos los nodos hijos originales (cues, loops, beatgrids, etc.).
    Garantiza inmutabilidad absoluta del XML de origen.
    """
    if not isinstance(name, str) or not name.strip():
        raise PlanningError('Nombre vacío')
    if any((ord(ch) < 32 and ch not in '\t\n\r') or 0xD800 <= ord(ch) <= 0xDFFF for ch in name):
        raise PlanningError('Nombre con caracteres inválidos para XML')
    if target.suffix.lower() != '.xml':
        raise PlanningError('Destino debe ser XML')
    if target.resolve() == lib.source:
        raise PlanningError('No se sobrescribe el XML de origen')
    if result.get('source_revision', lib.revision) != lib.revision:
        raise PlanningError('El plan pertenece a otra revisión de biblioteca')
    if hashlib.sha256(lib.source.read_bytes()).hexdigest() != lib.revision:
        raise PlanningError('El XML fuente cambió: recargá la biblioteca y recalculá')

    ids = result.get('track_ids', [])
    if not ids or len(ids) != len(set(ids)) or any(i not in lib.nodes for i in ids):
        raise PlanningError('IDs exportados inválidos')

    for tid in ids:
        try:
            valid_id = 0 <= int(tid) <= 2147483647 and str(int(tid)) == tid
        except (ValueError, TypeError):
            valid_id = False
        if not valid_id:
            raise PlanningError('TrackID no cumple especificación XML: entero de 32 bits')
        location = lib.tracks[tid].location
        parsed = urlsplit(location)
        if parsed.scheme.lower() != 'file' or parsed.netloc.lower() != 'localhost' or not parsed.path.startswith('/'):
            raise PlanningError('Exportación XML requiere ubicación local file://localhost/')
        if parsed.query or parsed.fragment or not parsed.path.strip('/'):
            raise PlanningError('Location debe ser un URI local sin query ni fragmento')
        if re.search(r'%(?![0-9A-Fa-f]{2})', parsed.path):
            raise PlanningError('Location contiene un escape URI inválido')

    root = ET.Element('DJ_PLAYLISTS', Version='1.0.0')
    ET.SubElement(root, 'PRODUCT', Name='Rekord AI', Version='0.4.1', Company='EgoBits')
    collection = ET.SubElement(root, 'COLLECTION', Entries=str(len(ids)))
    for tid in ids:
        track_node = copy.deepcopy(lib.nodes[tid])
        location = track_node.get('Location', '')
        parsed = urlsplit(location)
        # El Bridge espera un URI: preservar escapes válidos y codificar Unicode/espacios.
        track_node.set('Location', f'file://localhost{quote(parsed.path, safe="/:%")}')
        collection.append(track_node)

    pls = ET.SubElement(root, 'PLAYLISTS')
    folder = ET.SubElement(pls, 'NODE', Type='0', Name='ROOT', Count='1')
    node = ET.SubElement(folder, 'NODE', Type='1', Name=name, KeyType='0', Entries=str(len(ids)))
    for tid in ids:
        ET.SubElement(node, 'TRACK', Key=tid)

    ET.indent(root)
    payload = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    # Verificación de integridad del XML recién generado
    ET.fromstring(payload)

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as f:
        f.write(payload)
    return target

def diff_libraries(lib_a: Library, lib_b: Library) -> dict[str, Any]:
    """Compara dos instantáneas de la colección para detectar cambios."""
    ids_a = set(lib_a.tracks.keys())
    ids_b = set(lib_b.tracks.keys())

    added_ids = sorted(ids_b - ids_a)
    removed_ids = sorted(ids_a - ids_b)
    common_ids = sorted(ids_a & ids_b)

    modified = []
    for tid in common_ids:
        ta, tb = lib_a.tracks[tid], lib_b.tracks[tid]
        diffs = {}
        if ta.bpm != tb.bpm:
            diffs['bpm'] = {'before': ta.bpm, 'after': tb.bpm}
        if ta.key != tb.key:
            diffs['key'] = {'before': ta.key, 'after': tb.key}
        if ta.title != tb.title:
            diffs['title'] = {'before': ta.title, 'after': tb.title}
        if diffs:
            modified.append({'id': tid, 'changes': diffs})

    return {
        'revision_a': lib_a.revision,
        'revision_b': lib_b.revision,
        'added_count': len(added_ids),
        'removed_count': len(removed_ids),
        'modified_count': len(modified),
        'added_tracks': [vars(lib_b.tracks[i]) for i in added_ids],
        'removed_tracks': [vars(lib_a.tracks[i]) for i in removed_ids],
        'modified_tracks': modified
    }
