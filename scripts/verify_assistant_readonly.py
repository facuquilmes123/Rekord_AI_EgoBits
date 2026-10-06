"""Verify assistant workflows on a selected XML; exports only to a temporary folder.

No database/audio writes, process closure or inference. Report omits personal names.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'prototype'))
from egobits.adapters.xml_adapter import Library,export_xml
from egobits.adapters.m3u8 import export_m3u8
from egobits.ai.intents import SearchTracksIntent,ComparePlaylistsIntent,ExplainTransitionIntent,RecommendManualIntent
from egobits.ai.parser import parse_natural_language_intent
from egobits.desktop.chat import execute_chat
from egobits.desktop.collection_tools import draft
from egobits.core.planner import harmonic_score


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xml',type=Path)
    args=parser.parse_args()
    settings={}
    if args.xml is None:
        settings=json.loads((Path(os.environ['LOCALAPPDATA'])/'Rekord AI EgoBits/settings.json').read_text(encoding='utf-8'))
    source=args.xml or Path(settings['library_xml'])
    energies=json.loads(Path(settings['energies_json']).read_text(encoding='utf-8')) if settings.get('energies_json') else None
    lib=Library(source,energies);before=lib.revision
    checks={};timings={}
    def ask(query):
        start=time.monotonic()
        result=execute_chat(parse_natural_language_intent(query,list(lib.playlists)),lib,'open')
        timings[result['intent']['action']]=round(time.monotonic()-start,3)
        assert not result['applied']
        return result
    summary=ask('resumí mi colección')
    checks['complete_summary']=summary['summary']['tracks']==len(lib.tracks)
    result=ask('armá un set de 10 pistas desde toda mi colección')['plan_result']
    checks['collection_plan']=len(result['track_ids'])==10 and all(0<=t['bpm_delta']<=3 and t['harmonic']>0 for t in result['transitions'])
    paths=list(lib.playlists)
    if paths:
        inspection=ask('revisá la playlist '+paths[0])['playlist']
        checks['original_playlist_order']=inspection['track_ids']==lib.playlists[paths[0]]
    if len(paths)>1:
        compared=execute_chat(ComparePlaylistsIntent(playlist_a=paths[0],playlist_b=paths[1]),lib,'open')['comparison']
        checks['playlist_comparison']=compared['common_count']==len(set(lib.playlists[paths[0]])&set(lib.playlists[paths[1]]))
    searched=execute_chat(SearchTracksIntent(query='',bpm_min=120,bpm_max=126,limit=5),lib,'open')
    checks['complete_filtered_search']=searched['total']==sum(t.bpm is not None and 120<=t.bpm<=126 for t in lib.tracks.values())
    ids=result['track_ids']
    audit=ask('auditá set con IDs '+','.join(ids))['setlist_audit']
    checks['set_order_audit']=audit['track_count']==10 and audit['approved']
    transition=execute_chat(ExplainTransitionIntent(track_a_id=ids[0],track_b_id=ids[1]),lib,'open')['transition']
    checks['transition']=transition['bpm_delta']==result['transitions'][0]['bpm_delta']
    reference=next(t for t in lib.tracks.values() if t.genre and t.key and t.bpm is not None and 120<=t.bpm<=126)
    recommendations=execute_chat(RecommendManualIntent(current_track_id=reference.id),lib,'open')['recommendations']
    checks['recommendations_grounded']=bool(recommendations) and all(t['id'] in lib.tracks and t['id']!=reference.id and
        abs(t['bpm']-reference.bpm)<=4 and t['genre']==reference.genre and harmonic_score(t['key'],reference.key)>0 for t in recommendations)
    manual=draft(lib,list(reversed(ids)),lib.revision)
    checks['manual_order']=manual['track_ids']==list(reversed(ids))
    with tempfile.TemporaryDirectory(prefix='rekord-ai-readonly-') as folder:
        xml=Path(folder)/'set.xml';m3u8=Path(folder)/'set.m3u8'
        export_xml(lib,result,'Read-only verification',xml)
        export_m3u8(lib,result,'Read-only verification',m3u8)
        out=Library(xml)
        checks['xml_export_order']=out.playlists['ROOT/Read-only verification']==ids
        checks['xml_preserves_cues_beatgrid']=all(
            [ET.tostring(el) for el in lib.nodes[tid] if el.tag in ('TEMPO','POSITION_MARK')]==
            [ET.tostring(el) for el in out.nodes[tid] if el.tag in ('TEMPO','POSITION_MARK')] for tid in ids)
        checks['m3u8_export']=m3u8.read_text(encoding='utf-8').startswith('#EXTM3U\n')
    checks['source_unchanged']=hashlib.sha256(source.read_bytes()).hexdigest()==before
    report={'tracks':len(lib.tracks),'playlists':len(paths),'verified_energy':summary['summary']['verified_energy'],
            'candidate_total':result['candidate_total'],'candidate_count':result['candidate_count'],
            'timings_seconds':timings,'recommendations_returned':len(recommendations),'checks':checks}
    print(json.dumps(report,ensure_ascii=True,indent=2))
    if not all(checks.values()):raise SystemExit(1)


if __name__=='__main__':main()
