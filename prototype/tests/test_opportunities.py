import json
from pathlib import Path
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch,MagicMock
from egobits.adapters.xml_adapter import Library
from egobits.desktop.opportunities import analysis_query,answer_analysis,detail,catalog,metadata_query,answer_metadata
from egobits.desktop import service


class OpportunityTests(unittest.TestCase):
    def setUp(self):self.lib=Library(Path(__file__).resolve().parents[1]/'examples/library.xml')

    def test_analysis_aliases_and_evidence_fallback(self):
        for query in ['cuales pistas me faltan analizar en rekordbox?','Qué canciones están sin analizar','análisis pendientes']:
            self.assertTrue(analysis_query(query))
        self.assertFalse(analysis_query('analizar una transición'))
        data=answer_analysis(self.lib,lambda:{'databases':[]})
        self.assertIn('XML no certifica',data['response']);self.assertEqual(data['suggestions'][0]['opportunity'],'analysis')

    def test_native_zero_flag_is_not_inferred_from_missing_metadata(self):
        conn=MagicMock();conn.__enter__.return_value=conn
        conn.execute.return_value.fetchone.return_value=(1,)
        conn.execute.return_value.fetchall.return_value=[('outside-xml','Pendiente',0)]
        with patch('egobits.adapters.sqlcipher_read.connection',return_value=conn):
            data=answer_analysis(self.lib,lambda:{'databases':['fixture.db']})
        self.assertEqual(data['analysis']['source'],'native_readonly');self.assertEqual(data['analysis']['total'],1)
        self.assertFalse(data['analysis']['tracks'][0]['in_collection']);self.assertIn('Analysed=0',data['response'])

    def test_every_opportunity_has_specific_instructions_and_valid_ids(self):
        for key,group in catalog(self.lib).items():
            self.assertTrue(group['instructions']);data=detail(self.lib,key)
            self.assertEqual(data['total'],len(group['track_ids']))
            self.assertTrue(all(t['id'] in self.lib.tracks for t in data['tracks']))

    def test_missing_metadata_uses_complete_xml_and_actionable_list(self):
        fields=metadata_query('¿Cuáles pistas están sin género, BPM y tonalidad?')
        self.assertEqual(fields,['genre','bpm','key'])
        answer=answer_metadata(self.lib,fields)
        self.assertEqual(answer['answer_mode'],'collection_evidence')
        self.assertEqual(answer['matched_count'],len(set().union(*(catalog(self.lib)[key]['track_ids'] for key in fields))))
        self.assertIn('Primeras pistas para corregir',answer['response'])
        self.assertEqual([item['opportunity'] for item in answer['suggestions'][:3]],fields)
        self.assertIsNone(metadata_query('¿Cómo mezclo sin perder energía?'))

    def test_missing_genre_chat_skips_model(self):
        with patch.object(service,'_GLOBAL_LIB',self.lib),patch.object(service,'EXAMPLES_DIR',Path('unmatched-demo-source')),patch.object(service,'_SESSION_TOKEN',None),patch.object(service,'assistant_answer',side_effect=AssertionError('Must not invoke model')):
            server=ThreadingHTTPServer(('127.0.0.1',0),service.EgoBitsRequestHandler);worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            try:
                request=urllib.request.Request(f'http://127.0.0.1:{server.server_port}/api/chat',data=json.dumps({'query':'¿Qué pistas están sin género?'}).encode(),headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(request,timeout=4) as response:data=json.load(response)
                self.assertEqual(data['answer_mode'],'collection_evidence')
                self.assertEqual(data['suggestions'][0]['opportunity'],'genre')
            finally:server.shutdown();server.server_close();worker.join()

    def test_chat_analysis_bypasses_model_and_returns_actionable_detail(self):
        with patch.object(service,'_GLOBAL_LIB',self.lib),patch.object(service,'EXAMPLES_DIR',Path('unmatched-demo-source')),patch.object(service,'_SESSION_TOKEN',None),patch.object(service,'discover',return_value={'databases':[]}),patch.object(service,'assistant_answer',side_effect=AssertionError('Must not invoke model')):
            server=ThreadingHTTPServer(('127.0.0.1',0),service.EgoBitsRequestHandler);worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            try:
                request=urllib.request.Request(f'http://127.0.0.1:{server.server_port}/api/chat',data=json.dumps({'query':'cuales pistas me faltan analizar en rekordbox?'}).encode(),headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(request,timeout=4) as response:data=json.load(response)
                self.assertEqual(data['answer_mode'],'collection_evidence');self.assertFalse(data['applied'])
                with urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/api/opportunity?id=analysis&revision={self.lib.revision}',timeout=4) as response:result=json.load(response)
                self.assertEqual(data['analysis']['total'],result['total'])
                with urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/settings-tabs.js',timeout=4) as response:
                    self.assertIn(b'data-settings',response.read())

            finally:server.shutdown();server.server_close();worker.join()

    def test_busy_model_rejects_queue_instead_of_waiting_indefinitely(self):
        lock=threading.Lock();lock.acquire()
        with patch.object(service,'_AI_LOCK',lock):
            with self.assertRaisesRegex(ValueError,'otra consulta'):
                with service.ai_slot():self.fail('Slot incorrectly granted')
        lock.release()


class ConversationRecoveryTests(unittest.TestCase):
    def test_model_invoked_automatically_for_open_question(self):
        lib=Library(Path(__file__).resolve().parents[1]/'examples/library.xml')
        client=MagicMock();client.generate_answer.return_value={'answer':'Organizá apertura, desarrollo y cierre.','suggested_questions':['auditar colección'],'track_ids':[]}
        with patch.object(service,'local_llama_client',return_value=client),patch.object(service._SETTINGS,'snapshot',return_value={'llm_enabled':True}):
            result=service.assistant_answer('Como preparo una noche musical?',lib)
        self.assertEqual(result['answer_mode'],'local_assistant');client.generate_answer.assert_called_once()

    def test_invalid_model_answer_retried_without_relaxing_validation(self):
        lib=Library(Path(__file__).resolve().parents[1]/'examples/library.xml')
        client=MagicMock();client.generate_answer.side_effect=[{'answer':'Ya he borrado las pistas','suggested_questions':[],'track_ids':['invented']},{'answer':'Revisá las transiciones antes del show.','suggested_questions':[],'track_ids':[]}]
        with patch.object(service,'local_llama_client',return_value=client),patch.object(service._SETTINGS,'snapshot',return_value={'llm_enabled':True}):
            result=service.assistant_answer('Como preparo mi show?',lib)
        self.assertEqual(result['answer_mode'],'local_assistant');self.assertEqual(client.generate_answer.call_count,2);self.assertFalse(result['applied'])

    def test_model_failure_returns_grounded_facts_and_recovery_actions(self):
        lib=Library(Path(__file__).resolve().parents[1]/'examples/library.xml')
        with patch.object(service,'local_llama_client',side_effect=OSError('fixture unavailable')),patch.object(service._SETTINGS,'snapshot',return_value={'llm_enabled':True}):
            result=service.assistant_answer('Como preparo mi show?',lib)
        self.assertEqual(result['answer_mode'],'guided_fallback');self.assertEqual(result['verified_facts']['tracks'],len(lib.tracks));self.assertFalse(result['applied']);self.assertTrue(result['suggestions'])

    def test_timeout_cancels_owned_inference_before_automatic_restart(self):
        lib=Library(Path(__file__).resolve().parents[1]/'examples/library.xml');runtime=MagicMock()
        client=MagicMock();client.generate_answer.side_effect=TimeoutError('fixture timeout')
        with patch.object(service,'_LLAMA_RUNTIME',runtime),patch.object(service,'local_llama_client',return_value=client),patch.object(service._SETTINGS,'snapshot',return_value={'llm_enabled':True}):
            result=service.assistant_answer('Como preparo mi show?',lib)
        runtime.stop.assert_called_once();self.assertEqual(result['answer_mode'],'guided_fallback')

    def test_observed_false_bpm_and_energy_claims_are_rejected(self):
        from egobits.desktop.assistant_context import collection_context,validate_answer
        lib=Library(Path(__file__).resolve().parents[1]/'examples/library.xml');ctx=collection_context(lib,'energía')
        for answer in ['Faltan BPM y tonalidad en 1 pista para calcular energía precisa.','Para energía real necesitas valores verificados en el master.','Falta tonalidad para calcular energía precisa.']:
            with self.assertRaises(ValueError):validate_answer({'answer':answer,'suggested_questions':[],'track_ids':[]},ctx)
