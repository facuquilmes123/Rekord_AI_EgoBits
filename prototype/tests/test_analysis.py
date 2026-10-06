import unittest
from pathlib import Path
from egobits.core import (
    Library,
    compare_playlists,
    find_duplicates,
    audit_library,
    audit_setlist,
    explain_transition,
    Track
)

ROOT = Path(__file__).resolve().parents[1]

class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.lib = Library(ROOT / 'examples/library.xml')

    def test_playlist_compare(self):
        tracks_x = self.lib.pool(['ROOT/X'])
        tracks_y = self.lib.pool(['ROOT/Y'])
        cmp_res = compare_playlists(tracks_x, tracks_y, 'X', 'Y')

        self.assertEqual(cmp_res['total_a'], 3)
        self.assertEqual(cmp_res['total_b'], 4)
        # Track 3 está en ambas
        self.assertEqual(cmp_res['common_count'], 1)
        self.assertEqual(cmp_res['only_a_count'], 2)
        self.assertEqual(cmp_res['only_b_count'], 3)

    def test_library_duplicates(self):
        tracks = list(self.lib.tracks.values())
        # Crear copia sintética con un duplicado de título/artista
        dup_track = Track(
            id='99',
            title='Motor',
            artist='Tres',
            bpm=126.0,
            key='9A',
            genre='tech house',
            duration=330.0,
            location='file://localhost/C:/Music/Motor_copy.mp3'
        )
        dups = find_duplicates(tracks + [dup_track])
        self.assertEqual(len(dups), 1)
        self.assertEqual(dups[0]['signature'], 'tres - motor')
        self.assertEqual(dups[0]['count'], 2)

    def test_library_audit(self):
        tracks = list(self.lib.tracks.values())
        report = audit_library(tracks)
        self.assertEqual(report['total_tracks'], 6)
        # En library.xml, Track 5 no tiene tonality
        self.assertEqual(report['missing_key_count'], 1)
        self.assertIn('5', report['missing_key_ids'])
        self.assertEqual(report['missing_bpm_count'], 0)
        self.assertGreater(report['health_score'], 80.0)

    def test_setlist_audit_detects_issues(self):
        # Crear setlist con salto brusco de BPM y mismo artista
        t1 = Track('1', 'Uno', 'Artista A', 124.0, '8A', 'tech house', 300.0, 'loc')
        t2 = Track('2', 'Dos', 'Artista A', 132.0, '2A', 'tech house', 300.0, 'loc') # +8 BPM, choque armónico, mismo artista
        report = audit_setlist([t1, t2], max_bpm_step=3.0)

        self.assertFalse(report['approved'])
        issue_types = [i['type'] for i in report['issues']]
        self.assertIn('bpm_jump', issue_types)
        self.assertIn('harmonic_clash', issue_types)
        self.assertIn('adjacent_artist', issue_types)

    def test_explain_transition(self):
        t1 = self.lib.tracks['1'] # 124 BPM, 8A (Am)
        t2 = self.lib.tracks['2'] # 125 BPM, 8A
        exp = explain_transition(t1, t2)
        self.assertEqual(exp['bpm_delta'], 1.0)
        self.assertEqual(exp['harmonic_score'], 1.0)
        self.assertIn('Misma tonalidad', exp['harmonic_explanation'])

if __name__ == '__main__':
    unittest.main()
