"""Opt-in live Windows QA: read-only library/history, audio in RAM only."""
import argparse,json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'prototype'))
from egobits.adapters.xml_adapter import Library
from egobits.adapters.m3u8 import local_path
from egobits.telemetry.audio_match import devices,decode,features,capture,identify
from egobits.telemetry.audio_candidates import AudioCandidates
from egobits.desktop.discovery import discover
from egobits.desktop.settings import SettingsStore
from egobits.core.recommender import recommend,RecommendationOptions

parser=argparse.ArgumentParser();parser.add_argument('--device',type=int,required=True);parser.add_argument('--consent-local-audio',action='store_true');args=parser.parse_args()
if not args.consent_local_audio:raise SystemExit('Local audio consent required')
settings=SettingsStore().snapshot();lib=Library(Path(settings['library_xml']))
ids=AudioCandidates(lib,discover)();print('Preparing automatic references:',len(ids),flush=True)
refs={i:features(decode(local_path(lib.tracks[i].location))) for i in ids}
results=[]
for _ in range(2):
 samples=capture(args.device,seconds=3);started=time.monotonic();result=identify(samples,refs);result['processing_seconds']=round(time.monotonic()-started,3);results.append(result);print(result,flush=True)
stable=all(r.get('matched') for r in results) and results[0].get('track_id')==results[1].get('track_id') and all(r['processing_seconds']<5 for r in results)
report={'library_count':len(lib.tracks),'candidate_count':len(ids),'audio_saved':False,'master_certified':False,'stable_match':stable,'results':results}
if stable:
 track=lib.tracks[results[-1]['track_id']];report['identified_title']=track.title
 report['recommendations']=recommend(track,list(lib.tracks.values()),RecommendationOptions(**settings['recommendation']))['recommendations'][:3]
(ROOT/'output/closure/live-automatic-audio-20261002.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('Stable audio match:',stable,flush=True)
