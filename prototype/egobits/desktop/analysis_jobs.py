"""One cancellable offline audio job; results stay in the app's managed directory."""
import copy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import secrets
import tempfile
import threading
from ..core.models import PlanningError
from ..core.acoustic import analyze_file
from ..adapters.m3u8 import local_path


class AnalysisJobs:
    def __init__(self,root,analyzer=analyze_file):
        self.root=Path(root);self.analyzer=analyzer;self.lock=threading.RLock();self.cancelled=threading.Event()
        self.state={'state':'idle'};self.records={};self.scope=None;self.record_stamp=None

    @staticmethod
    def scope_of(lib):return hashlib.sha256(str(getattr(lib,'database_path',lib.source)).encode()).hexdigest()

    def _load(self,scope):
        path=self.root/(scope+'.json')
        try:s=path.stat();stamp=(s.st_mtime_ns,s.st_size)
        except FileNotFoundError:stamp=None
        if self.scope==scope and (stamp==self.record_stamp or self.state['state']=='running'):return
        self.records={}
        if path.is_file():
            try:
                data=json.loads(path.read_text(encoding='utf-8'))
                if isinstance(data,dict):self.records=data
            except (ValueError,OSError):pass
        self.scope=scope;self.record_stamp=stamp

    def _save(self):
        self.root.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=self.root,delete=False,suffix='.tmp') as out:
            path=Path(out.name);json.dump(self.records,out,ensure_ascii=False,allow_nan=False);out.flush();os.fsync(out.fileno())
        os.replace(path,self.root/(self.scope+'.json'))
        s=(self.root/(self.scope+'.json')).stat();self.record_stamp=(s.st_mtime_ns,s.st_size)

    def start(self,lib,track_ids=None,playlist=None):
        with self.lock:
            if self.state['state']=='running':raise PlanningError('Ya hay un análisis acústico activo')
            if track_ids is None:track_ids=[t.id for t in lib.pool([playlist])] if playlist else list(lib.tracks)
            if not isinstance(track_ids,list) or not 1<=len(track_ids)<=500000 or any(not isinstance(t,str) or t not in lib.tracks for t in track_ids):
                raise PlanningError('Selección de audio inválida')
            tracks=[lib.tracks[t] for t in dict.fromkeys(track_ids)]
            self._load(self.scope_of(lib));self.cancelled=threading.Event()
            self.state={'state':'running','job_id':secrets.token_hex(16),'total':len(tracks),'processed':0,'analyzed':0,'failed':0,'errors':[],
                        'source_revision':lib.revision,'energy_kind':'estimated'}
            threading.Thread(target=self._run,args=(tracks,),daemon=True).start();return self.snapshot()

    def _run(self,tracks):
        try:
            for track in tracks:
                if self.cancelled.is_set():break
                try:
                    value=self.analyzer(local_path(track.location),self.cancelled)
                    with self.lock:self.records[track.id]=value;self.state['analyzed']+=1
                except InterruptedError:break
                except Exception as exc:
                    with self.lock:
                        self.state['failed']+=1
                        if len(self.state['errors'])<30:self.state['errors'].append({'id':track.id,'reason':str(exc)[:300]})
                with self.lock:
                    self.state['processed']+=1
                    if self.state['processed']%10==0:self._save()
            with self.lock:
                self._save();self.state['state']='cancelled' if self.cancelled.is_set() else 'complete'
        except Exception as exc:
            with self.lock:self.state.update(state='failed',error=str(exc)[:300])

    def snapshot(self):
        with self.lock:return copy.deepcopy(self.state)

    def cancel(self,job_id):
        with self.lock:
            if self.state.get('job_id')!=job_id:raise PlanningError('Análisis desconocido')
            self.cancelled.set();return self.snapshot()

    def attach(self,lib):
        if not hasattr(lib,'source'):return lib
        with self.lock:
            scope=self.scope_of(lib)
            if self.state['state']=='running' and scope!=self.scope:return lib
            self._load(scope);records=copy.deepcopy(self.records)
        changed={}
        for tid,data in records.items():
            if tid not in lib.tracks or not isinstance(data,dict):continue
            try:
                path=local_path(lib.tracks[tid].location).resolve();stamp=path.stat();ident=data['file_identity']
                if str(path)!=ident['path'] or stamp.st_size!=ident['size'] or stamp.st_mtime_ns!=ident['mtime_ns'] or stamp.st_ino!=ident['inode']:continue
                value=float(data['value'])
                if not 0<=value<=10:continue
                changed[tid]=replace(lib.tracks[tid],energy=value,energy_source=data['source'])
            except (ValueError,KeyError,OSError,TypeError):continue
        if not changed:return lib
        result=copy.copy(lib);result.tracks={**lib.tracks,**changed};result.acoustic_metadata=records;return result

    def measurements(self,lib,track_id):
        with self.lock:
            if self.state['state']=='running' and self.scope_of(lib)!=self.scope:raise PlanningError('Esperá o cancelá el análisis de la colección anterior')
            if self.scope_of(lib)!=self.scope:self._load(self.scope_of(lib))
            data=copy.deepcopy(self.records.get(track_id))
        if data is None:raise PlanningError('La pista todavía no tiene análisis acústico')
        path=local_path(lib.tracks[track_id].location).resolve();stamp=path.stat();ident=data.get('file_identity',{})
        if (str(path),stamp.st_size,stamp.st_mtime_ns,stamp.st_ino)!=(ident.get('path'),ident.get('size'),ident.get('mtime_ns'),ident.get('inode')):
            raise PlanningError('El archivo cambió; volvé a analizar la pista')
        return {'track_id':track_id,**data}
