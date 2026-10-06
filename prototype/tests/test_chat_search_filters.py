from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from egobits.ai.intents import SearchTracksIntent, UnknownIntent
from egobits.ai.parser import parse_natural_language_intent
from egobits.ai.validation import intent_from_payload
from egobits.core.models import Track, PlanningError
from egobits.desktop.chat import execute_chat

QUERY = 'buscar en coleccion una pista techhouse de 124 bpm con tonalidad 8a y buena energia'


class ChatSearchFilterTests(unittest.TestCase):
    def setUp(self):
        base = Track('1', 'Tema & Á', 'DJ', 124, '8A', 'Tech House', 180, '', 8, 'DJ manual')
        self.lib = SimpleNamespace(revision='fixture', tracks={
            '1': base, '2': replace(base, id='2', bpm=125), '3': replace(base, id='3', key='9A'),
            '4': replace(base, id='4', genre='House'), '5': replace(base, id='5', energy=6),
            '6': replace(base, id='6', energy=None, energy_source=None)})

    def test_original_request_gets_structured_intent(self):
        intent = parse_natural_language_intent(QUERY)
        self.assertIsInstance(intent, SearchTracksIntent)
        self.assertEqual(intent.query, '')
        self.assertEqual(intent.genre, 'tech house')
        self.assertEqual(intent.key, '8A')
        self.assertEqual(intent.energy_min, 7)
        self.assertAlmostEqual(intent.bpm_min, 123.9)
        self.assertAlmostEqual(intent.bpm_max, 124.1)

    def test_filters_are_combined_and_energy_has_provenance(self):
        answer = execute_chat(parse_natural_language_intent(QUERY), self.lib, 'closed')
        self.assertEqual([t['id'] for t in answer['tracks']], ['1'])
        self.assertEqual(answer['total'], 1)
        self.assertEqual(answer['missing_energy_count'], 1)
        self.assertIn('8A', answer['response'])
        self.assertIn('DJ manual', answer['response'])
        self.assertFalse(answer['applied'])

    def test_unknown_energy_returns_labeled_alternatives(self):
        for tid, track in self.lib.tracks.items():
            self.lib.tracks[tid] = replace(track, energy=None, energy_source=None)
        answer = execute_chat(parse_natural_language_intent(QUERY), self.lib, 'closed')
        self.assertEqual(answer['total'], 0)
        self.assertEqual({t['id'] for t in answer['alternatives']}, {'1', '5', '6'})
        self.assertIn('sin confirmar energía', answer['response'])
        self.assertIn('No puedo confirmar', answer['response'])

    def test_energy_without_source_is_not_verified(self):
        self.lib.tracks = {'1': replace(self.lib.tracks['1'], energy_source=None)}
        answer = execute_chat(parse_natural_language_intent(QUERY), self.lib, 'closed')
        self.assertEqual(answer['total'], 0)
        self.assertEqual(len(answer['alternatives']), 1)

    def test_bpm_range_and_spaced_genre(self):
        intent = parse_natural_language_intent('buscar pistas de tech-house entre 123 y 126 bpm en tonalidad 8A')
        self.assertEqual(intent.genre, 'tech house')
        self.assertEqual((intent.bpm_min, intent.bpm_max), (123, 126))
        self.assertEqual(intent.query, '')
        answer = execute_chat(intent, self.lib, 'closed')
        self.assertEqual({t['id'] for t in answer['tracks']}, {'1', '2', '5', '6'})

    def test_invalid_key_and_inverted_ranges_rejected(self):
        for query in ('buscar techhouse 124 bpm tonalidad 13a', 'buscar techno entre 130 y 120 bpm',
                      'buscar house energia minima 99'):
            self.assertIsInstance(parse_natural_language_intent(query), UnknownIntent)

    def test_plain_title_search_and_genre_alias(self):
        answer = execute_chat(SearchTracksIntent(query='Tema & Á'), self.lib, 'closed')
        self.assertEqual(answer['total'], 6)
        answer = execute_chat(SearchTracksIntent(query='techhouse'), self.lib, 'closed')
        self.assertEqual(answer['total'], 5)

    def test_model_filter_validation_is_strict(self):
        good = {'action': 'library.search', 'params': {'query': '', 'genre': 'tech house',
                'bpm_min': 123.9, 'bpm_max': 124.1, 'key': '8a', 'energy_min': 7}}
        self.assertIsInstance(intent_from_payload(good, []), SearchTracksIntent)
        for key, value in (('bpm_min', True), ('bpm_min', float('nan')), ('energy_min', 11),
                           ('bpm_max', 120), ('key', '13A'), ('energy_min', 'alta')):
            bad = {'action': 'library.search', 'params': {**good['params'], key:value}}
            with self.assertRaises(PlanningError): intent_from_payload(bad, [])

    def test_supported_request_avoids_model_start(self):
        from egobits.desktop import service
        with patch.object(service, '_AI_LOCK') as lock:
            result = service.get_chat_intent(QUERY, [])
            self.assertIsInstance(result, SearchTracksIntent)
            lock.acquire.assert_not_called()
