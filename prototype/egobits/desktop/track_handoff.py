"""Resolve a collection ID to an existing local audio file, never a UI path."""
from pathlib import Path
from ..core.models import PlanningError
from ..adapters.m3u8 import local_path
from ..adapters.native_write import digest

def drag_file(lib, track_id, revision):
    if revision!=lib.revision or digest(lib.source)!=lib.revision:
        raise PlanningError('La colección cambió; recargá la recomendación')
    if not isinstance(track_id,str) or track_id not in lib.tracks:
        raise PlanningError('La pista no pertenece a la colección cargada')
    path=local_path(lib.tracks[track_id].location).resolve(strict=True)
    if str(path).startswith('\\\\') or not path.is_file():
        raise PlanningError('Se requiere un archivo de audio local disponible')
    if path.suffix.casefold() not in {'.mp3','.wav','.aiff','.aif','.flac','.m4a','.aac','.ogg','.alac'}:
        raise PlanningError('El archivo no tiene una extensión de audio admitida')
    return {'path':str(path),'track_id':track_id,'source_revision':revision}
