"""Read-only live history observation; history is never an audible-master claim."""
from datetime import datetime, timezone
from pathlib import Path
import threading
import copy
import time
from ..adapters.sqlcipher_read import connection
from .audio_candidates import path_key
from ..adapters.m3u8 import local_path
from ..core.models import PlanningError
from ..core.recommender import recommend, RecommendationOptions


class HistoryObserver:
    def __init__(self, discover, process_state):
        self.discover, self.process_state = discover, process_state
        self.lock = threading.Lock()
        self.last_poll = 0
        self.path = None
        self.seen = None
        self.current = None
        self.changed_at = 0
        self.reason = 'Esperando conexión a la base local'
        self.revision = None
        self.metadata_mode=False
        self.ranking_cache=None;self.ranking_key=None;self.ranking_at=0
        self.path_index={}

    def reset(self):
        with self.lock:
            self.last_poll = 0
            self.path = self.seen = self.current = self.revision = None
            self.changed_at = 0
            self.reason = 'Colección cambiada. Esperando una entrada nueva del historial'

    def poll(self, lib, options=None, use_last_registered=False):
        with self.lock:
            if use_last_registered!=self.metadata_mode:self.last_poll=0
            self.metadata_mode=use_last_registered
            revision = lib.revision if lib else None
            if revision != self.revision:
                self.revision = revision
                self.last_poll = 0
                self.path = self.seen = self.current = None
                self.path_index={}
                if lib:
                    for track in lib.tracks.values():
                        try:key=path_key(local_path(track.location))
                        except ValueError:continue
                        self.path_index.setdefault(key,[]).append(track)
            if time.monotonic() - self.last_poll < 5: return self._result(lib, options)
            self.last_poll = time.monotonic()
            if self.process_state() != 'open':
                self.seen=None; self.current=None; self.reason='Requiere Rekordbox abierto'
                return self._result(lib,options)
            try:
                dbs=self.discover()['databases']
                if len(dbs)!=1: raise PlanningError('Elegí una base: la detección no es única')
                if dbs[0]!=self.path: self.path=dbs[0]; self.seen=None; self.current=None
                with connection(self.path) as conn:
                    rows=conn.execute('''SELECT s.ID,s.ContentID,s.updated_at,c.FolderPath
                        FROM djmdSongHistory s JOIN djmdContent c ON c.ID=s.ContentID
                        ORDER BY s.created_at DESC,s.TrackNo DESC LIMIT 50''').fetchall()
                signature=tuple((str(r[0]),str(r[1]),str(r[2])) for r in rows)
                if self.seen is None:
                    self.seen=signature; self.reason='Conectado. Esperando una entrada nueva; no se reutiliza historial anterior'
                    if use_last_registered and rows:
                        self.current=rows[0];self.changed_at=time.monotonic()
                        self.reason='Referencia: última pista registrada en Rekordbox. No confirma la pista audible actual'
                elif signature != self.seen:
                    previous=set(self.seen); added=[r for r in rows if (str(r[0]),str(r[1]),str(r[2])) not in previous]
                    self.seen=signature
                    if len(added)==1:
                        self.current=added[0]; self.changed_at=time.monotonic()
                        self.reason='Nueva pista registrada en el historial; master audible sin confirmar'
                    else:
                        self.current=None; self.reason='Cambios múltiples de historial; referencia ambigua'
                elif use_last_registered and self.current is None and rows:
                    self.current=rows[0];self.changed_at=time.monotonic()
                    self.reason='Referencia: última pista registrada en Rekordbox. No confirma la pista audible actual'
            except (OSError,ValueError,ImportError):
                self.seen=None; self.current=None; self.reason='Historial local no disponible'
            return self._result(lib,options)

    def _result(self,lib,options):
        base={'connected': self.seen is not None,'source':'rekordbox_history','confirmed':False,
              'master_confirmed':False,'reason':self.reason,'recommendations':[]}
        base['reference_mode']='last_registered' if self.metadata_mode else 'new_entries'
        if not self.current or (not self.metadata_mode and time.monotonic()-self.changed_at>120) or not lib: return base
        matches=self.path_index.get(path_key(self.current[3]),[])
        if len(matches)!=1: return {**base,'reason':'La pista registrada no tiene correspondencia única en el XML'}
        try:
            from ..core.recommender import compact_recommendation
            selected_options=options or RecommendationOptions()
            key=(lib.revision,tuple(str(value) for value in self.current),tuple(sorted(vars(selected_options).items())))
            if key!=self.ranking_key or time.monotonic()-self.ranking_at>=5:
                self.ranking_cache=compact_recommendation(recommend(matches[0],list(lib.tracks.values()),selected_options))
                self.ranking_key=key;self.ranking_at=time.monotonic()
            result=copy.deepcopy(self.ranking_cache)
            return {**base,**result,'history_event_id':str(self.current[0]),'age_seconds':round(time.monotonic()-self.changed_at,1)}
        except PlanningError as exc: return {**base,'reason':str(exc)}
