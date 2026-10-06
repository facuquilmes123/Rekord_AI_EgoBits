import unittest
from egobits.ai import (
    sanitize_user_input,
    parse_natural_language_intent,
    PlanPlaylistIntent,
    SearchTracksIntent,
    AuditLibraryIntent,
    ExplainTransitionIntent,
    SystemStatusIntent
)

class AiIntentsTests(unittest.TestCase):
    def test_sanitize_user_input_strips_control_codes(self):
        malicious = "Track \x00\x1fTitle\x08; DROP TABLE tracks; --"
        cleaned = sanitize_user_input(malicious)
        self.assertNotIn('\x00', cleaned)
        self.assertNotIn('\x1f', cleaned)
        self.assertIn('Track Title; DROP TABLE tracks; --', cleaned)

    def test_parse_plan_bpm_intent(self):
        text = "Recorré las playlists ROOT/X y ROOT/Y subiendo BPM con 4 temas"
        intent = parse_natural_language_intent(text, ['ROOT/X', 'ROOT/Y'])
        self.assertIsInstance(intent, PlanPlaylistIntent)
        self.assertEqual(intent.count, 4)
        self.assertEqual(intent.mode, 'bpm')
        self.assertIn('ROOT/X', intent.playlists)
        self.assertIn('ROOT/Y', intent.playlists)

    def test_parse_plan_energy_intent(self):
        text = "Uní ROOT/X y ROOT/Y con energía creciente"
        intent = parse_natural_language_intent(text, ['ROOT/X', 'ROOT/Y'])
        self.assertIsInstance(intent, PlanPlaylistIntent)
        self.assertEqual(intent.mode, 'energy')

    def test_parse_audit_intent(self):
        text = "Auditá mi colección para ver qué pistas tienen problemas"
        intent = parse_natural_language_intent(text)
        self.assertIsInstance(intent, AuditLibraryIntent)

    def test_parse_search_intent(self):
        text = "Buscar temas de Tech House"
        intent = parse_natural_language_intent(text)
        self.assertIsInstance(intent, SearchTracksIntent)
        self.assertEqual(intent.query, '')
        self.assertEqual(intent.genre, 'tech house')

    def test_parse_explain_transition_intent(self):
        text = "Explicar transición entre 1 y 2"
        intent = parse_natural_language_intent(text)
        self.assertIsInstance(intent, ExplainTransitionIntent)
        self.assertEqual(intent.track_a_id, '1')
        self.assertEqual(intent.track_b_id, '2')

    def test_parse_status_intent(self):
        text = "¿Cómo está el sistema?"
        intent = parse_natural_language_intent(text)
        self.assertIsInstance(intent, SystemStatusIntent)

if __name__ == '__main__':
    unittest.main()
