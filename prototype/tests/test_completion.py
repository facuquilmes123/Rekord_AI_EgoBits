import dataclasses
import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from egobits.adapters.xml_adapter import Library, export_xml
from egobits.adapters.native_read import NativeReadOnlyAdapter
from egobits.ai.parser import parse_natural_language_intent
from egobits.ai.intents import UnknownIntent
from egobits.ai.validation import intent_from_payload
from egobits.core.models import PlanningError
from egobits.core.recommender import recommend, RecommendationOptions
from egobits.desktop import service
from egobits.desktop.chat import execute_chat
from egobits.desktop.settings import SettingsStore
from egobits.desktop.live_suggestion import live_suggestion

EXAMPLE = Path(__file__).resolve().parents[1] / 'examples/library.xml'


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lib = Library(EXAMPLE)

    def test_real_collection_never_inherits_demo_energy(self):
        target = self.root / 'colección.xml'
        shutil.copyfile(EXAMPLE, target)
        with patch.object(service, '_GLOBAL_LIB', None), patch.object(service, '_SETTINGS', SettingsStore(self.root/'settings.json')), patch.dict(os.environ, {}, clear=True):
            loaded = service.get_or_load_library(target)
            self.assertTrue(all(t.energy is None for t in loaded.tracks.values()))

    def test_missing_selected_collection_never_falls_back(self):
        with patch.object(service, '_GLOBAL_LIB', None):
            with self.assertRaises(PlanningError):
                service.get_or_load_library(self.root/'missing.xml')

    def test_settings_persist_and_invalid_update_is_atomic(self):
        path = self.root/'settings.json'
        store = SettingsStore(path)
        store.update({'notifications': {'enabled': True}, 'recommendation': {'same_genre': True}})
        before = path.read_bytes()
        with self.assertRaises(PlanningError):
            store.update({'notifications': {'min_frequency_seconds': 0}})
        self.assertEqual(before, path.read_bytes())
        self.assertTrue(SettingsStore(path).snapshot()['notifications']['enabled'])

    def test_unknown_request_does_not_create_playlist(self):
        self.assertIsInstance(parse_natural_language_intent('hola', list(self.lib.playlists)), UnknownIntent)
        self.assertIsInstance(parse_natural_language_intent('creá una playlist', list(self.lib.playlists)), UnknownIntent)

    def test_invalid_count_does_not_truncate(self):
        self.assertIsInstance(parse_natural_language_intent('uní ROOT/X con 1000 temas', ['ROOT/X']), UnknownIntent)

    def test_artist_negation_is_respected(self):
        intent = parse_natural_language_intent('uní ROOT/X con 4 temas sin repetir artista', ['ROOT/X'])
        self.assertTrue(intent.avoid_adjacent_artist)

    def test_ambiguous_short_name_requires_full_path(self):
        self.assertIsInstance(parse_natural_language_intent('uní X', ['ROOT/X','OTRA/X']), UnknownIntent)
        intent = parse_natural_language_intent('uní ROOT/X', ['ROOT/X','OTRA/X'])
        self.assertEqual(intent.playlists, ('ROOT/X',))

    def test_parser_rejection_does_not_invoke_model(self):
        with patch.object(service, 'LocalLlamaRuntime') as runtime:
            intent = service.get_chat_intent('uní ROOT/X con 1000 temas', ['ROOT/X'])
            self.assertIsInstance(intent, UnknownIntent)
            runtime.assert_not_called()

    def test_model_cannot_request_write_or_invent_playlist(self):
        for payload in ({'action':'playlist.export_xml','params':{}}, {'action':'playlist.plan','params':{'playlists':['inventada']}}):
            with self.assertRaises(PlanningError):
                intent_from_payload(payload, list(self.lib.playlists))

    def test_supported_chat_actions_really_execute(self):
        queries = ['listar playlists', 'buscá pistas', 'compará ROOT/X y ROOT/Y', 'auditá colección', 'duplicados', 'describí pista 1', 'transición entre 1 y 2', 'recomendá desde pista 1', 'estado', 'en vivo']
        for query in queries:
            with self.subTest(query=query):
                intent = parse_natural_language_intent(query, list(self.lib.playlists))
                self.assertNotIsInstance(intent, UnknownIntent)
                result = execute_chat(intent, self.lib, 'closed')
                self.assertTrue(result['response'])
                self.assertFalse(result['applied'])

    def test_recommendation_missing_bpm_is_not_invented(self):
        track = dataclasses.replace(next(iter(self.lib.tracks.values())), bpm=None)
        with self.assertRaises(PlanningError):
            recommend(track, list(self.lib.tracks.values()), RecommendationOptions())

    def test_energy_filter_requires_reference_metadata(self):
        with self.assertRaises(PlanningError):
            recommend(self.lib.tracks['1'], list(self.lib.tracks.values()), RecommendationOptions(max_energy_delta=1))

    def test_genre_filter_and_bpm_margin(self):
        current = self.lib.tracks['1']
        other = dataclasses.replace(current, id='other', artist='otro', genre='different')
        data = recommend(current, [other], RecommendationOptions(same_genre=True))
        self.assertEqual(data['recommendations'], [])
        self.assertIn('other', data['excluded'])

    def test_changed_source_blocks_export(self):
        path = self.root/'source.xml'
        shutil.copyfile(EXAMPLE,path)
        lib = Library(path)
        path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaises(PlanningError):
            export_xml(lib, {'track_ids':['1']}, 'new', self.root/'new.xml')
        self.assertFalse((self.root/'new.xml').exists())

    def test_utf16_dtd_is_rejected(self):
        path = self.root/'bad.xml'
        path.write_bytes('<!DOCTYPE DJ_PLAYLISTS [<!ENTITY x "test">]><DJ_PLAYLISTS/>'.encode('utf-16'))
        with self.assertRaises(PlanningError):
            Library(path)

    def test_provider_failure_never_confirms(self):
        class Broken:
            def is_available(self): raise RuntimeError('provider failure')
        self.assertFalse(live_suggestion(self.lib, Broken())['confirmed'])

    def test_native_snapshot_uses_real_join_columns(self):
        path = self.root/'snapshot #á.sqlite'
        with sqlite3.connect(path) as conn:
            conn.executescript("CREATE TABLE djmdContent(ID,Title,ArtistID,BPM,KeyID); CREATE TABLE djmdArtist(ID,Name); CREATE TABLE djmdKey(ID,ScaleName); INSERT INTO djmdArtist VALUES('a','Artista'); INSERT INTO djmdKey VALUES('k','Am'); INSERT INTO djmdContent VALUES('1','Título','a',12400,'k');")
        conn.close()
        before = path.read_bytes()
        row = NativeReadOnlyAdapter(path).read_tracks_snapshot()[0]
        self.assertEqual((row['artist'],row['bpm'],row['key']),('Artista',124.0,'Am'))
        self.assertEqual(before,path.read_bytes())

    def test_encrypted_native_file_is_explicitly_unsupported(self):
        path=self.root/'encrypted.db'; path.write_bytes(b'not sqlite data')
        with self.assertRaisesRegex(PlanningError,'SQLCipher'):
            NativeReadOnlyAdapter(path)
