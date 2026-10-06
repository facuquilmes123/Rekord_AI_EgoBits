from dataclasses import replace
from types import SimpleNamespace
import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from egobits.ai.intents import SimilarTracksIntent, MultiSearchIntent, UnknownIntent
from egobits.ai.parser import parse_natural_language_intent as parse
from egobits.ai.validation import intent_from_payload
from egobits.core.models import Track, PlanningError
from egobits.core.mentions import mention_candidates, resolve_followup
from egobits.desktop.chat import execute_chat


class MentionChatTests(unittest.TestCase):
    def setUp(self):
        ref = Track('1','840','Rodrigo',None,'8A','Tech House',180,'',8,'DJ')
        self.lib = SimpleNamespace(revision='fixture', playlists={}, tracks={
            '1':ref, '2':replace(ref,id='2',title='Vecina',artist='DJ',key='9A'),
            '3':replace(ref,id='3',title='Exacta',artist='DJ',bpm=128),
            '4':replace(ref,id='4',title='Relativa',artist='DJ',key='8B'),
            '5':replace(ref,id='5',title='Otro género',artist='DJ',genre='techno'),
            '6':replace(ref,id='6',title='Otra clave',artist='DJ',key='3A'),
            '7':replace(ref,id='7',title='Sin clave',artist='DJ',key=None)})

    def ask(self, query): return execute_chat(parse(query),self.lib,'closed')

    def test_original_phrase_resolves_artist_title_without_bpm_filter(self):
        answer=self.ask('decime canciones similares en tonalidad y genero a @rodrigo-840')
        self.assertFalse(answer['needs_selection'])
        self.assertEqual(answer['references'][0]['id'],'1')
        self.assertEqual({t['id'] for t in answer['tracks']},{'2','3','4'})
        self.assertIn('compatibilidad Camelot',answer['response'])
        self.assertFalse(answer['applied'])
        self.assertEqual(answer['context_reference']['track_id'],'1')

    def test_exact_tonality_and_quoted_reference(self):
        answer=self.ask('buscame pistas de la misma tonalidad que @"Rodrigo - 840"')
        self.assertEqual({t['id'] for t in answer['tracks']},{'3','5'})
        self.assertEqual(answer['criteria']['key_mode'],'exact')

    def test_bpm_only_does_not_enforce_key_genre_or_artist(self):
        self.lib.tracks={tid:replace(t,bpm=124) for tid,t in self.lib.tracks.items()}
        answer=self.ask('recomendame canciones similares en bpm a @id:1')
        self.assertEqual(answer['total'],6)
        self.assertFalse(answer['criteria']['same_genre'])
        self.assertEqual(answer['criteria']['key_mode'],'none')

    def test_ambiguous_title_requires_explicit_choice_preserving_criteria(self):
        self.lib.tracks['8']=replace(self.lib.tracks['1'],id='8',key='12B')
        answer=self.ask('decime 3 canciones parecidas en bpm a @rodrigo-840')
        self.assertTrue(answer['needs_selection'])
        self.assertEqual({t['id'] for t in answer['candidates']},{'1','8'})
        self.assertIsNone(answer['context_reference'])
        self.assertIn('3 canciones similares en bpm',answer['suggestions'][0]['query'])
        self.assertNotIn('tonalidad',answer['suggestions'][0]['query'])

    def test_partial_name_never_silently_resolves(self):
        answer=self.ask('similares a @rodri')
        self.assertTrue(answer['needs_selection'])
        self.assertEqual(answer['candidates'][0]['id'],'1')
        self.assertNotIn('tracks',answer)

    def test_numeric_name_and_id_collision_requires_explicit_id(self):
        self.lib.tracks['840']=replace(self.lib.tracks['2'],id='840')
        self.assertTrue(self.ask('parecidas a @840')['needs_selection'])
        self.assertEqual(self.ask('parecidas a @id:840')['references'][0]['id'],'840')

    def test_missing_reference_is_explained(self):
        answer=self.ask('similares a @no-existe')
        self.assertTrue(answer['needs_selection'])
        self.assertEqual(answer['candidates'],[])
        self.assertIn('No encontré',answer['response'])

    def test_missing_requested_metadata_is_not_invented(self):
        with self.assertRaises(PlanningError): self.ask('similares en bpm a @id:1')
        self.lib.tracks['1']=replace(self.lib.tracks['1'],energy_source=None)
        with self.assertRaises(PlanningError): self.ask('similares en energia a @id:1')

    def test_multiple_references_are_intersection_and_excluded(self):
        answer=self.ask('similares en genero y tonalidad a @id:1 y @id:2')
        self.assertEqual({t['id'] for t in answer['tracks']},{'3'})
        self.assertEqual(len(answer['references']),2)

    def test_multiple_queries_are_read_only_and_independent(self):
        intent=parse('buscar techno; canciones similares en tonalidad y genero a @rodrigo-840')
        self.assertIsInstance(intent,MultiSearchIntent)
        answer=execute_chat(intent,self.lib,'closed')
        self.assertEqual(len(answer['results']),2)
        self.assertEqual(answer['results'][0]['total'],1)
        self.assertEqual(answer['results'][1]['total'],3)
        self.assertFalse(answer['applied'])
        self.assertIsInstance(parse('buscar techno; crear playlist llamada nueva'),UnknownIntent)
        self.assertIsInstance(parse(';'.join(['buscar house']*6)),UnknownIntent)

    def test_semicolon_in_quoted_song_is_not_batch(self):
        self.assertIsInstance(parse('similares a @"DJ - Uno; Dos"'),SimilarTracksIntent)

    def test_followup_requires_selected_current_reference(self):
        query='otras parecidas a esa pista'
        context={'track_id':'1','source_revision':self.lib.revision}
        rewritten=resolve_followup(query,self.lib,context)
        self.assertIn('@id:1',rewritten)
        self.assertEqual(self.ask(rewritten)['total'],3)
        for value in (None,{'track_id':'1','source_revision':'old'}, {'track_id':'unknown','source_revision':'fixture'}):
            with self.assertRaises(PlanningError): resolve_followup(query,self.lib,value)

    def test_autocomplete_normalizes_names_and_bounds_results(self):
        self.assertEqual(mention_candidates(self.lib,'rodrigo-840')[0]['id'],'1')
        self.assertLessEqual(len(mention_candidates(self.lib,'',2)),2)
        self.assertEqual(mention_candidates(self.lib,'id:3')[0]['id'],'3')
        with self.assertRaises(PlanningError): mention_candidates(self.lib,'a'*161)

    def test_model_cannot_turn_batch_into_write_or_bad_similarity(self):
        payload={'action':'library.similar','params':{'references':['id:1'],'key_mode':'compatible'}}
        self.assertIsInstance(intent_from_payload(payload,[]),SimilarTracksIntent)
        for params in ({'references':[]},{'references':['id:1'],'key_mode':'guess'},
                       {'references':['id:1'],'count':51},{'references':['x']*6}):
            with self.assertRaises(PlanningError): intent_from_payload({'action':'library.similar','params':params},[])
        with self.assertRaises(PlanningError): intent_from_payload({'action':'library.multisearch','params':{'queries':['crear playlist'] }},[])

    def test_every_response_offers_followup_actions(self):
        for intent in (parse('buscar techno'),parse('estado'),UnknownIntent()):
            answer=execute_chat(intent,self.lib,'closed')
            self.assertTrue(answer['suggestions'])
            self.assertTrue(all('query' in a or 'tab' in a for a in answer['suggestions']))

    def test_authenticated_mentions_and_chat_http(self):
        from egobits.desktop import service
        with patch.object(service,'_GLOBAL_LIB',self.lib), patch.object(service,'_SESSION_TOKEN','mentions-test'), patch.object(service,'status',return_value={}), patch.object(service._MONITOR,'check_state',return_value='closed') as process_probe:
            server=ThreadingHTTPServer(('127.0.0.1',0),service.EgoBitsRequestHandler)
            worker=threading.Thread(target=server.serve_forever,daemon=True); worker.start()
            def request(path,body=None,auth=True):
                headers={'Content-Type':'application/json'}
                if auth: headers['X-EgoBits-Token']='mentions-test'
                req=urllib.request.Request(f'http://127.0.0.1:{server.server_port}'+path,data=None if body is None else json.dumps(body).encode(),headers=headers)
                with urllib.request.urlopen(req,timeout=4) as response: return json.load(response)
            try:
                with self.assertRaises(urllib.error.HTTPError) as error: request('/api/mentions?q=rodrigo',auth=False)
                self.assertEqual(error.exception.code,403)
                self.assertEqual(request('/api/mentions?q=rodrigo-840')['tracks'][0]['id'],'1')
                answer=request('/api/chat',{'query':'similares en tonalidad y genero a @rodrigo-840'})
                self.assertEqual(answer['total'],3)
                self.assertTrue(answer['suggestions'])
                self.assertEqual(request('/api/chat',{'query':'otras parecidas a esa pista','context_reference':answer['context_reference']})['total'],3)
                process_probe.assert_not_called()
            finally: server.shutdown(); server.server_close(); worker.join(timeout=2)
