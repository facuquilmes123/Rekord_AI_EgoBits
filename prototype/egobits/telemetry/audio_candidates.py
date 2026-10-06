"""History narrows audio references, but never establishes audible playback."""
from ..adapters.m3u8 import local_path
import os
import unicodedata
from ..adapters.sqlcipher_read import connection
from ..core.models import PlanningError


def path_key(path):
    # Metadata lookup must not stat all 24k files (including offline drives).
    # Selected files are resolved/validated by AudioWatch before decoding.
    return unicodedata.normalize('NFC',os.path.normpath(str(path))).casefold()


class AudioCandidates:
    def __init__(self, library, discover):
        self.library,self.discover=library,discover
        self.index={}
        for track in library.tracks.values():
            try:key=path_key(local_path(track.location))
            except ValueError:continue
            self.index.setdefault(key,[]).append(track.id)

    def __call__(self):
        databases=self.discover()['databases']
        if len(databases)!=1:raise PlanningError('No hay una base única para preparar referencias automáticas')
        with connection(databases[0]) as conn:
            paths=conn.execute('SELECT c.FolderPath FROM djmdSongHistory s JOIN djmdContent c ON c.ID=s.ContentID ORDER BY s.created_at DESC,s.TrackNo DESC LIMIT 50').fetchall()
        ids=[]
        for row in paths:
            matches=self.index.get(path_key(row[0]),[])
            if len(matches)==1 and matches[0] not in ids and local_path(self.library.tracks[matches[0]].location).is_file():ids.append(matches[0])
            if len(ids)==4:break
        if not ids:raise PlanningError('Esperando una pista registrada por Rekordbox que exista en la colección cargada. El audio se comprobará después; el historial solo prepara referencias.')
        anchor=self.library.tracks[ids[0]]
        # Similar tracks are useful negative controls; never accept history alone.
        ordered=sorted(self.library.tracks.values(),key=lambda t:(t.genre!=anchor.genre,abs((t.bpm or 0)-(anchor.bpm or 0)),t.id))
        for track in ordered:
            if track.id in ids:continue
            try:
                path=local_path(track.location)
                if len(self.index.get(path_key(path),[]))==1 and path.is_file():ids.append(track.id)
            except ValueError:continue
            if len(ids)>=8:break
        if len(ids)<2:raise PlanningError('Faltan archivos locales para distinguir la pista de otras referencias')
        return ids
