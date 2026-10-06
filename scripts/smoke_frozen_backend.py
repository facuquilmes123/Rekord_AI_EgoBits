"""Prueba del EXE real con PATH sin Python/Node y perfil temporal aislado."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import time
import urllib.request
from windows_metrics import ProcessMetrics

ROOT=Path(__file__).resolve().parents[1]


def main():
    executable=ROOT/'build/backend/egobits-backend.exe'
    report={'artifact':str(executable),'sha256':hashlib.sha256(executable.read_bytes()).hexdigest(),
            'network_disabled':False,'environment':'Windows actual; PATH sin Python/Node; perfil temporal', 'checks':{}}
    token=secrets.token_urlsafe(32)
    with tempfile.TemporaryDirectory(prefix='egobits-smoke-') as temporary:
        # Exercise chat against an isolated XML selected as a collection, never demo mode.
        fixture_xml=Path(temporary)/'collection.xml'
        shutil.copy2(ROOT/'prototype/examples/library.xml',fixture_xml)
        env={**os.environ,'LOCALAPPDATA':temporary,'EGB_SESSION_TOKEN':token,'EGB_RESOURCE_ROOT':str(ROOT),
             'EGB_LIBRARY_XML':str(fixture_xml),'PATH':os.path.join(os.environ['SystemRoot'],'System32')}
        for key in ('PYTHONPATH','PYTHONHOME','EGB_ENERGIES_JSON'): env.pop(key,None)
        started=time.monotonic()
        process=subprocess.Popen([str(executable),'--serve','--port','0'],env=env,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        metrics=ProcessMetrics(process.pid)
        try:
            with concurrent.futures.ThreadPoolExecutor() as pool:
                def ready():
                    for line in process.stdout:
                        if line.startswith('EGB_READY:'): return int(line.split(':')[1])
                    raise RuntimeError('Backend no inició')
                try:
                    port=pool.submit(ready).result(timeout=45)
                except concurrent.futures.TimeoutError:
                    # Release the reader before ThreadPoolExecutor waits for it.
                    subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],
                        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW)
                    raise
            report['startup_seconds']=round(time.monotonic()-started,2)
            def request(path,body=None):
                data=json.dumps(body).encode() if body is not None else None
                req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,data=data,
                    headers={'X-EgoBits-Token':token,'Content-Type':'application/json'})
                with urllib.request.urlopen(req,timeout=300) as response: return json.load(response)
            report['checks']['real_xml_selected']=not request('/api/status')['demo']
            plan=request('/api/plan',{'playlists':['ROOT/X','ROOT/Y'],'count':4})
            exported=request('/api/export',{'result':plan,'name':'Prueba ñ 東京','target_path':str(Path(temporary)/'salida.xml')})
            report['checks']['xml_export']=Path(exported['exported_file']).is_file()
            started=time.monotonic()
            chat=request('/api/chat',{'query':'¿Hay canciones en común entre ROOT/X y ROOT/Y?'})
            report['inference_seconds']=round(time.monotonic()-started,2)
            report['llm_status']=request('/api/status')['llm']
            report['checks']['comparison']=chat['intent']['action']=='playlist.compare' and chat['comparison']['common_count']==1
            summary=request('/api/chat',{'query':'resumí mi colección'})
            inspected=request('/api/chat',{'query':'revisá la playlist ROOT/X'})
            audited=request('/api/chat',{'query':'auditá set con IDs 1,2,3'})
            collection_plan=request('/api/chat',{'query':'armá un set de 4 pistas desde toda mi colección'})
            report['checks']['collection_summary']=summary['summary']['tracks']==6 and not summary['applied']
            report['checks']['playlist_inspection']=inspected['playlist']['track_ids']==['1','2','3']
            report['checks']['chat_set_audit']=audited['setlist_audit']['track_count']==3 and not audited['applied']
            report['checks']['chat_collection_plan']=len(collection_plan['plan_result']['track_ids'])==4 and not collection_plan['applied']
            started=time.monotonic()
            conversation=request('/api/chat',{'query':'Como organizo un set para pasar de una apertura tranquila a un cierre intenso?'})
            report['conversation_seconds']=round(time.monotonic()-started,2)
            report['conversation']=conversation
            report['llm_status']=request('/api/status')['llm']
            report['checks']['real_llm']=report['llm_status']['state']=='ready'
            report['checks']['real_conversation']=conversation['answer_mode']=='local_assistant' and not conversation['applied']
            report['checks']['live_blocked']=not request('/api/live-suggestion')['confirmed']
            request('/api/shutdown',{})
            process.wait(timeout=15)
            report['exit_code']=process.returncode
            report['checks']['clean_exit']=process.returncode==0
        finally:
            if process.poll() is None:
                subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
                process.wait(timeout=10)
            for stream in (process.stdout,process.stderr): stream.close()
            report['metrics']=metrics.finish()
            report['checks']['no_orphan_process']=not report['metrics']['still_alive_pids']
            (ROOT/'output/closure/frozen-smoke.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    if not all(report['checks'].values()): raise SystemExit(1)


if __name__=='__main__': main()
