import json
import threading
import urllib.request
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from egobits.adapters.xml_adapter import Library
from egobits.ai.parser import parse_natural_language_intent as parse
from egobits.ai.intents import SearchTracksIntent
from egobits.desktop import service
from egobits.desktop.opportunities import metadata_query,analysis_query


class PerformanceWorkflowTests(unittest.TestCase):
    def test_metadata_negations_and_blanks(self):
        for query in ('qué pistas no tienen género?', 'canciones con género vacío', 'género en blanco', 'género sin definir'):
            self.assertEqual(metadata_query(query),['genre'])
        self.assertTrue(analysis_query('qué temas no tienen análisis?'))
        self.assertFalse(metadata_query('cómo mezclar sin cambiar BPM?'))
        self.assertFalse(metadata_query('no tienen el mismo género estas dos pistas'))

    def test_informational_genre_questions_skip_model(self):
        for query,genre in [('qué temas de house tengo?','house'),('cuáles canciones de tech house hay?','tech house')]:
            intent=parse(query)
            self.assertIsInstance(intent,SearchTracksIntent)
            self.assertEqual(intent.genre,genre);self.assertEqual(intent.query,'')
        self.assertNotIsInstance(parse('qué significa house?'),SearchTracksIntent)

    def test_http_direct_aliases_and_compact_recommendations(self):
        lib=Library(Path(__file__).resolve().parents[1]/'examples/library.xml')
        with patch.object(service,'_GLOBAL_LIB',lib),patch.object(service,'EXAMPLES_DIR',Path('unmatched-demo-source')),patch.object(service,'_SESSION_TOKEN',None),patch.object(service,'assistant_answer',side_effect=AssertionError('Model must not be called')):
            server=ThreadingHTTPServer(('127.0.0.1',0),service.EgoBitsRequestHandler)
            worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            def request(path,body):
                req=urllib.request.Request(f'http://127.0.0.1:{server.server_port}'+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(req,timeout=4) as response:return json.load(response)
            try:
                for query in ('qué pistas no tienen género?','qué temas de house tengo?'):
                    self.assertFalse(request('/api/chat',{'query':query})['applied'])
                result=request('/api/recommend',{'current_track_id':'1'})
                self.assertNotIn('excluded',result)
                self.assertEqual(result['excluded_count'],sum(result['excluded_reasons'].values()))
            finally:server.shutdown();server.server_close();worker.join()
