"""Continuous, opt-in local audio pilot. Scores are never probabilities."""
from datetime import datetime, timezone
import threading
import time
from ..core.models import PlanningError
from ..adapters.m3u8 import local_path
from . import audio_match


class AudioWatch:
    def __init__(self, process_state=None):
        self.process_state=process_state
        self.lock=threading.RLock()
        self.stop_event=threading.Event()
        self.thread=None
        self.state={'active':False,'state':'stopped','reason':'Seguimiento de audio desactivado','matched':False}

    def start(self, lib, ids, device, consent, allow_popup=False, candidate_selector=None):
        if consent is not True: raise PlanningError('Confirmá el análisis local de la salida seleccionada')
        if candidate_selector is not None:ids=candidate_selector()
        if type(allow_popup) is not bool: raise PlanningError('Preferencia de popup inválida')
        if not isinstance(ids,list) or not 2<=len(ids)<=20 or len(set(ids))!=len(ids) or any(type(i) is not str or i not in lib.tracks for i in ids):
            raise PlanningError('Seleccioná entre 2 y 20 pistas de la colección para el piloto')
        if type(device) is not int or device not in {d['index'] for d in audio_match.devices()}:
            raise PlanningError('Elegí una salida WASAPI disponible; ASIO puede requerir otra ruta')
        paths={i:local_path(lib.tracks[i].location).resolve(strict=True) for i in ids}
        with self.lock:
            if self.thread and self.thread.is_alive(): raise PlanningError('Detené el seguimiento anterior antes de iniciarlo otra vez')
            self.stop_event=threading.Event()
            self.state={'active':True,'state':'indexing','reason':'Preparando referencias locales de audio',
                        'matched':False,'confirmed':False,'master_confirmed':False,
                        'source_revision':lib.revision,'allow_popup':allow_popup,'indexed':0,'total':len(paths)}
            self.state['automatic']=candidate_selector is not None
            self.thread=threading.Thread(target=self._run,args=(paths,device,self.stop_event,candidate_selector,lib),daemon=True)
            self.thread.start()
            return self.snapshot()

    def _run(self, paths, device, stop, candidate_selector=None, library=None):
        try:
            refs={}
            for tid,path in paths.items():
                if stop.is_set(): return
                refs[tid]=audio_match.features(audio_match.decode(path))
                if sum(r.nbytes for r in refs.values())>256*1024**2: raise PlanningError('Referencias de audio superan 256 MiB; reducí la selección')
                with self.lock:self.state['indexed']=len(refs)
            previous=None
            refreshed=time.monotonic()
            while not stop.is_set():
                if self.process_state and self.process_state()!='open':
                    stop.set()
                    return
                if candidate_selector is not None and time.monotonic()-refreshed>=10:
                    refreshed=time.monotonic()
                    ids=candidate_selector()
                    if set(ids)!=set(refs):
                        with self.lock:self.state.update(matched=False,stable=False,state='indexing',indexed=0,total=len(ids))
                        previous=None
                        refs={tid:refs[tid] for tid in ids if tid in refs}
                        for tid in ids:
                            if stop.is_set():return
                            if tid not in refs:refs[tid]=audio_match.features(audio_match.decode(local_path(library.tracks[tid].location)))
                            if sum(r.nbytes for r in refs.values())>256*1024**2:raise PlanningError('Referencias de audio superan el límite local')
                            with self.lock:self.state['indexed']=len(refs)
                samples=audio_match.capture(device,seconds=3)
                observed=time.time()
                result=audio_match.identify(samples,refs)
                if stop.is_set(): return
                tid=result.get('track_id') if result.get('matched') else None
                stable=bool(tid and previous==tid)
                previous=tid
                with self.lock:
                    self.state.update(result)
                    self.state.update(state='listening',stable=stable,observed_at=observed,
                                      observed_at_utc=datetime.fromtimestamp(observed,timezone.utc).isoformat(),
                                      reason='Coincidencia repetida de audio; master sin certificar' if stable else result['reason'])
                stop.wait(.15)
        except Exception as exc:
            reason=str(exc) if isinstance(exc,PlanningError) else f'{type(exc).__name__}. Revisá salida y archivos locales.'
            with self.lock:self.state.update(active=False,state='error',matched=False,stable=False,reason=f'Seguimiento detenido: {reason}')
        finally:
            if stop.is_set():
                with self.lock:self.state.update(active=False,state='stopped',matched=False,stable=False,reason='Seguimiento detenido')

    def snapshot(self):
        with self.lock:
            result=dict(self.state)
            age=time.time()-result.get('observed_at',0)
            result['fresh']=0<=age<5
            result['popup_eligible']=bool(result.get('active') and result.get('stable') and result.get('matched') and result['fresh'] and result.get('allow_popup'))
            return result

    def stop(self):
        with self.lock:
            self.stop_event.set()
            running=bool(self.thread and self.thread.is_alive())
            self.state.update(active=False,state='stopping' if running else 'stopped',matched=False,stable=False,reason='Deteniendo captura local' if running else 'Captura de audio desactivada')
            return self.snapshot()
