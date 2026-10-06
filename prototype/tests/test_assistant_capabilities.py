from dataclasses import replace
from pathlib import Path
import unittest
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from egobits.adapters.xml_adapter import Library
from egobits.ai.parser import parse_natural_language_intent as parse
from egobits.ai.validation import intent_from_payload
from egobits.core.models import PlanningError, PlanOptions
from egobits.core.planner import plan
from egobits.desktop.chat import execute_chat
from egobits.desktop import service
from egobits.desktop.collection_tools import answer_help


class AssistantCapabilitiesTests(unittest.TestCase):
    def setUp(self):
        self.lib=Library(Path(__file__).resolve().parents[1]/'examples/library.xml')

    def ask(self,query):return execute_chat(parse(query,list(self.lib.playlists)),self.lib,'open')

    def test_summary_counts_entire_collection(self):
        answer=self.ask('resumí mi colección')
        self.assertEqual(answer['summary']['tracks'],len(self.lib.tracks))
        self.assertEqual(answer['summary']['playlists'],len(self.lib.playlists))
        self.assertFalse(answer['applied'])
        self.assertEqual(self.ask('¿Cuántas pistas tengo?')['summary']['tracks'],len(self.lib.tracks))

    def test_capability_help_states_real_conditions(self):
        response=answer_help('qué puede hacer por mí?',{})
        for condition in ('fuente registrada','preselección','archivos accesibles','agentes cerrados','confirmación','última exportación'):
            self.assertIn(condition,response)

    def test_http_new_capabilities_never_wait_for_model(self):
        with patch.object(service,'_GLOBAL_LIB',self.lib),patch.object(service,'EXAMPLES_DIR',Path('unmatched-demo-source')),patch.object(service,'_SESSION_TOKEN',None),patch.object(service,'assistant_answer',side_effect=AssertionError('Must not invoke model')):
            server=ThreadingHTTPServer(('127.0.0.1',0),service.EgoBitsRequestHandler)
            worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            try:
                queries=[('resumí mi colección','library.summary'),('revisá la playlist ROOT/X','playlist.inspect'),
                         ('auditá set con IDs 1,2,3','setlist.audit'),('armá un set de 4 pistas desde toda mi colección','playlist.plan')]
                for query,action in queries:
                    request=urllib.request.Request(f'http://127.0.0.1:{server.server_port}/api/chat',data=json.dumps({'query':query}).encode(),headers={'Content-Type':'application/json'})
                    with urllib.request.urlopen(request,timeout=4) as response:data=json.load(response)
                    self.assertEqual(data['intent']['action'],action);self.assertFalse(data['applied'])
            finally:server.shutdown();server.server_close();worker.join()

    def test_playlist_inspection_retains_duplicate_references(self):
        self.lib.playlists['ROOT/X']=['1','2','1']
        answer=self.ask('revisá la playlist ROOT/X')
        self.assertEqual(answer['playlist']['track_ids'],['1','2','1'])
        self.assertEqual(answer['playlist']['duplicate_references'],1)

    def test_playlist_inspection_preserves_order_and_audits_transitions(self):
        answer=self.ask('revisá la playlist ROOT/X')
        self.assertEqual(answer['playlist']['track_ids'],self.lib.playlists['ROOT/X'])
        self.assertEqual(answer['playlist']['audit']['track_count'],len(self.lib.playlists['ROOT/X']))
        self.assertIn('duración',answer['response'])

    def test_chat_audits_explicit_setlist_and_rejects_unknown_ids(self):
        answer=self.ask('auditá set con IDs 1, 2, 3')
        self.assertEqual(answer['setlist_audit']['track_count'],3)
        with self.assertRaises(PlanningError):self.ask('auditá set con IDs 1, 999999')

    def test_collection_plan_produces_exportable_proposal(self):
        answer=self.ask('armá un set de 4 pistas desde toda mi colección')
        self.assertEqual(len(answer['plan_result']['track_ids']),4)
        self.assertEqual(answer['plan_result']['source_revision'],self.lib.revision)
        self.assertFalse(answer['applied'])

    def test_large_collection_is_bounded_and_constraints_preserved(self):
        base=self.lib.tracks['1']
        tracks=[replace(base,id=str(i),artist=f'DJ {i}',bpm=120+i/1000,key='8A') for i in range(2500)]
        result=plan(tracks,PlanOptions(count=8))
        self.assertEqual(result['candidate_total'],2500)
        self.assertEqual(result['candidate_count'],1000)
        self.assertEqual(len(result['track_ids']),8)
        self.assertTrue(any('preselección' in warning for warning in result['warnings']))
        self.assertTrue(all(0<=t['bpm_delta']<=3 for t in result['transitions']))

    def test_unproven_energy_never_drives_plan(self):
        tracks=[replace(t,energy=8,energy_source=None) for t in self.lib.tracks.values()]
        with self.assertRaises(PlanningError):plan(tracks,PlanOptions(count=2,mode='energy'))

    def test_model_new_readonly_actions_validate_sources(self):
        for action,params in [('library.summary',{}),('playlist.inspect',{'playlist':'ROOT/X'}),
                              ('setlist.audit',{'track_ids':['1','2']}),
                              ('playlist.plan',{'source':'collection','count':4})]:
            intent=intent_from_payload({'action':action,'params':params},list(self.lib.playlists))
            self.assertFalse(execute_chat(intent,self.lib,'open')['applied'])
        with self.assertRaises(PlanningError):intent_from_payload({'action':'playlist.inspect','params':{'playlist':'inventada'}},list(self.lib.playlists))
