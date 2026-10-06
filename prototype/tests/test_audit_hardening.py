import hashlib
import hmac
import sqlite3
import tempfile
import unittest
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from egobits.adapters.native_write import NativePlaylistWriter, schema_signature
from egobits.ai.sidecar_client import LlamaSidecarClient, sidecar_environment
from egobits.core.models import PlanningError
from egobits.desktop import service
from egobits.telemetry.history import HistoryObserver


class AuditHardeningTests(unittest.TestCase):
    def test_common_tracks_question_compares_complete_playlists(self):
        from egobits.ai.parser import parse_natural_language_intent
        from egobits.ai.intents import ComparePlaylistsIntent,UnknownIntent
        for query in ('¿Hay canciones en común entre ROOT/X y ROOT/Y?','Qué pistas comparten ROOT/X y ROOT/Y','Mostrá las canciones compartidas entre ROOT/X y ROOT/Y'):
            intent=parse_natural_language_intent(query,['ROOT/X','ROOT/Y'])
            self.assertIsInstance(intent,ComparePlaylistsIntent)
            self.assertEqual((intent.playlist_a,intent.playlist_b),('ROOT/X','ROOT/Y'))
        self.assertIsInstance(parse_natural_language_intent('¿Qué tienen en común estas tonalidades?',[]),UnknownIntent)

    def test_sidecar_does_not_inherit_desktop_approval_credentials(self):
        with patch.dict('os.environ',{'EGB_NATIVE_APPROVAL_KEY':'fixture-native','egb_session_token':'fixture-session','LLAMA_OLD':'fixture-old','HF_TOKEN':'fixture-hf','SYSTEMROOT':'C:/Windows'},clear=True):
            self.assertEqual(sidecar_environment('fixture-ai'),{'SYSTEMROOT':'C:/Windows','LLAMA_API_KEY':'fixture-ai'})

    def test_question_search_scans_filters_without_model(self):
        from egobits.ai.parser import parse_natural_language_intent
        from egobits.ai.intents import SearchTracksIntent,UnknownIntent
        result=parse_natural_language_intent('Qué tech house de 124 BPM 8A tengo?')
        self.assertIsInstance(result,SearchTracksIntent)
        self.assertEqual(result.genre,'tech house');self.assertEqual(result.key,'8A');self.assertEqual(result.query,'')
        self.assertEqual(result.bpm_min,123.9)
        self.assertIsInstance(parse_natural_language_intent('Qué es BPM?'),UnknownIntent)

    def test_mcp_uses_same_validated_collection_filters(self):
        from egobits import mcp_server
        from egobits.adapters.xml_adapter import Library
        from egobits.policy import State
        lib=Library(Path(__file__).resolve().parents[1]/'examples/library.xml')
        track=next(iter(lib.tracks.values()))
        with patch.object(mcp_server,'get_library',return_value=lib),patch.object(mcp_server,'current_state',return_value=State.CLOSED):
            result=mcp_server.search_tracks(genre=track.genre,bpm_min=track.bpm,bpm_max=track.bpm,key=track.key)
            self.assertIn(track.id,[t['id'] for t in result['tracks']])
            with self.assertRaises(PlanningError):mcp_server.search_tracks(bpm_min=float('nan'))

    def test_runtime_installer_has_explicit_hash_for_each_file(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'installer'))
        from package_single_installer import runtime_includes
        manifest={'assets':[{'path':'assets/bin/llama.dll','sha256':'a'*64},{'path':'assets/models/model.gguf','sha256':'b'*64}]}
        files,checks=runtime_includes(manifest)
        self.assertIn('Hash: "'+'a'*64+'"',files);self.assertIn('VerifyRuntimeFile',files)
        self.assertIn("VerifyRuntimeFile('{app}\\assets\\bin\\llama.dll', '"+'a'*64+"')",files)
        self.assertIn('llama.dll',checks);self.assertNotIn('gguf',checks)
        for path in ('assets/bin/../bad.dll','assets/bin/bad".dll'):
            with self.assertRaises(ValueError):runtime_includes({'assets':[{'path':path,'sha256':'a'*64}]})

    def test_versions_are_anchored_and_unknown_is_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            db=Path(td).resolve()/'master.db';db.touch()
            for version,accepted in [('7.2.19',True),('6.8.5',True),('17.2',False),('16.8',False),('',False),('unknown 7.2',False)]:
                writer=NativePlaylistWriter(Path(td)/'ops',lambda:'closed',lambda:{'databases':[str(db)],'installations':[{'version':version}]})
                if accepted:writer.guard(db)
                else:
                    with self.assertRaises(PlanningError):writer.guard(db)

    def test_schema_signature_compares_schema_not_track_data(self):
        @contextmanager
        def connect(path):
            db=sqlite3.connect(path)
            try:
                with db:yield db
            finally:db.close()
        with tempfile.TemporaryDirectory() as td, patch('egobits.adapters.native_write.connection',side_effect=connect):
            path=Path(td)/'fixture.db'
            with connect(path) as db:db.execute('CREATE TABLE track(id TEXT)')
            initial=schema_signature(path)
            with connect(path) as db:db.execute("INSERT INTO track VALUES ('one')")
            self.assertEqual(schema_signature(path),initial)
            with connect(path) as db:db.execute('ALTER TABLE track ADD COLUMN title TEXT')
            self.assertNotEqual(schema_signature(path),initial)

    def test_low_space_blocks_before_backup_creation(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'master.db';path.write_bytes(b'fixture')
            writer=NativePlaylistWriter(Path(td)/'ops',lambda:'closed',lambda:{})
            with patch('egobits.adapters.native_write.shutil.disk_usage',return_value=SimpleNamespace(free=0)):
                with self.assertRaises(PlanningError):writer.ensure_space([path])
            self.assertFalse(writer.root.exists())

    def test_native_approval_is_bound_to_operation_and_digest(self):
        preview={'token':'a'*32,'operation':'create_playlist','digest':'b'*64}
        body={'token':preview['token'],'confirmed':True,'approval_digest':preview['digest']}
        message=f"create_playlist:{preview['token']}:{preview['digest']}".encode()
        body['approval_signature']=hmac.new(b'fixture-key',message,'sha256').hexdigest()
        with patch.object(service,'_SESSION_TOKEN','fixture-session'),patch.object(service,'_NATIVE_APPROVAL_KEY','fixture-key'),patch.object(service._NATIVE,'approval_preview',return_value=preview):
            service.verify_native_approval(body,'create_playlist')
            for changed in ({'confirmed':False},{'approval_digest':'c'*64},{'approval_signature':'0'*64},{'approval_signature':True}):
                with self.assertRaises(PlanningError):service.verify_native_approval({**body,**changed},'create_playlist')
            with self.assertRaises(PlanningError):service.verify_native_approval(body,'restore')
        with patch.object(service,'_SESSION_TOKEN',None):
            with self.assertRaises(PlanningError):service.verify_native_approval(body,'create_playlist')

    def test_wrong_sidecar_owner_never_sends_authorization(self):
        client=LlamaSidecarClient(port=12345,api_key='fixture-key')
        client.owner_process=Mock(pid=101);client.owner_process.poll.return_value=None
        with patch('psutil.Process') as process,patch.object(client._opener,'open') as request:
            process.return_value.net_connections.return_value=[]
            self.assertFalse(client.is_alive());request.assert_not_called()
            with self.assertRaises(PlanningError):client.generate_intent('test')
            request.assert_not_called()
            process.return_value.net_connections.return_value=[SimpleNamespace(status='LISTEN',laddr=SimpleNamespace(ip='127.0.0.1',port=12345))]
            client._verify_owner()
            client.owner_process.poll.return_value=1
            with self.assertRaises(PlanningError):client._verify_owner()

    def test_collection_change_resets_history_even_inside_poll_interval(self):
        observer=HistoryObserver(lambda:{'databases':['fixture.db']},lambda:'open')
        fake=Mock();fake.__enter__=Mock(return_value=fake);fake.__exit__=Mock()
        fake.execute.return_value.fetchall.return_value=[('old','1','t','C:/fixture.mp3')]
        with patch('egobits.telemetry.history.connection',return_value=fake):
            observer.poll(SimpleNamespace(revision='first',tracks={}))
            observer.current=('old','1','t','C:/fixture.mp3')
            result=observer.poll(SimpleNamespace(revision='second',tracks={}))
            self.assertIsNone(observer.current);self.assertEqual(result['recommendations'],[])
            self.assertTrue(result['connected'])
            self.assertEqual(fake.execute.call_count,2)
        observer.reset();self.assertIsNone(observer.seen);self.assertEqual(observer.last_poll,0)


if __name__=='__main__':unittest.main()
