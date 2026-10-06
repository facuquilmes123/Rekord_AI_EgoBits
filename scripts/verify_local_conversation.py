"""Real offline conversation verification; fixture collection, no writes."""
import json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'prototype'))
os.environ['EGB_RESOURCE_ROOT']=str(ROOT)
from egobits.desktop import service
from egobits.adapters.xml_adapter import Library
lib=Library(ROOT/'prototype/examples/library.xml')
report={'checks':{},'cases':[]}
try:
 for query in ['Como organizo un set para pasar de una apertura tranquila a un cierre intenso?','Que informacion de mi coleccion podes usar y que te falta para evaluar la energia?']:
  start=time.monotonic();result=service.assistant_answer(query,lib)
  report['cases'].append({'query':query,'seconds':round(time.monotonic()-start,2),'result':result})
  print(json.dumps(report['cases'][-1],ensure_ascii=False),flush=True)
 report['checks']['real_conversation']=any(c['result']['answer_mode']=='local_assistant' for c in report['cases'])
 report['checks']['all_responses_useful']=all(c['result']['answer_mode'] in ('local_assistant','guided_fallback') and c['result']['verified_facts']['missing_bpm']==0 and not c['result']['applied'] for c in report['cases'])
finally:
 if service._LLAMA_RUNTIME:service._LLAMA_RUNTIME.stop()
 (ROOT/'output/closure/release-039/conversation-source.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if not all(report['checks'].values()):raise SystemExit(1)
