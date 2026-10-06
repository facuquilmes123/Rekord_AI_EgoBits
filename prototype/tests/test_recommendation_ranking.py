from dataclasses import replace
import unittest
from egobits.core.models import Track, PlanningError
from egobits.core.recommender import recommend,RecommendationOptions

class RecommendationRankingTests(unittest.TestCase):
    def setUp(self):
        self.current=Track('1','Actual','A',124,'8A','Tech House',180,'',7,'análisis local')

    def test_key_can_outweigh_small_bpm_difference_when_genre_filter_disabled(self):
        same=replace(self.current,id='2',artist='B',bpm=124.5)
        other=replace(self.current,id='3',artist='C',genre='Disco',key='9A')
        result=recommend(self.current,[self.current,other,same],RecommendationOptions(same_genre=False))
        self.assertEqual(result['recommendations'][0]['id'],'2')
        self.assertGreater(result['recommendations'][0]['compatibility_score'],result['recommendations'][1]['compatibility_score'])
        self.assertIn('Misma tonalidad',result['recommendations'][0]['match_reasons'])

    def test_defaults_require_bpm_genre_and_key(self):
        options=RecommendationOptions()
        self.assertTrue(options.match_bpm and options.same_genre and options.harmonic)
        wrong_genre=replace(self.current,id='2',artist='B',genre='Disco')
        far_bpm=replace(self.current,id='3',artist='B',bpm=140)
        wrong_key=replace(self.current,id='4',artist='B',key='2B')
        self.assertEqual(recommend(self.current,[wrong_genre,far_bpm,wrong_key],options)['recommendations'],[])

    def test_disabled_bpm_and_exact_key_and_duration(self):
        track=replace(self.current,id='2',artist='B',bpm=None)
        options=RecommendationOptions(match_bpm=False,key_mode='same',min_duration_seconds=180)
        self.assertEqual(len(recommend(self.current,[track],options)['recommendations']),1)
        self.assertEqual(recommend(self.current,[replace(track,key='9A'),replace(track,duration=100)],options)['recommendations'],[])
        with self.assertRaises(PlanningError):RecommendationOptions(match_bpm='false')
        with self.assertRaises(PlanningError):RecommendationOptions(min_duration_seconds=float('nan'))

    def test_genre_spelling_is_normalized_and_strict_filters_preserved(self):
        same=replace(self.current,id='2',artist='B',genre='tech-house')
        other=replace(self.current,id='3',artist='C',genre='Techno')
        result=recommend(self.current,[same,other],RecommendationOptions(same_genre=True))
        self.assertEqual([t['id'] for t in result['recommendations']],['2'])
        self.assertIn('3',result['excluded'])

    def test_energy_filter_requires_provenance_for_both_tracks(self):
        missing=replace(self.current,id='2',artist='B',energy_source=None)
        valid=replace(self.current,id='3',artist='C',energy=8)
        result=recommend(self.current,[missing,valid],RecommendationOptions(max_energy_delta=1))
        self.assertEqual([t['id'] for t in result['recommendations']],['3'])
        self.assertEqual(result['recommendations'][0]['match_details']['energy_delta'],1)
        with self.assertRaises(PlanningError):recommend(replace(self.current,energy_source=None),[valid],RecommendationOptions(max_energy_delta=1))

    def test_exact_bpm_and_zero_energy_margin_are_finite(self):
        track=replace(self.current,id='2',artist='B')
        row=recommend(self.current,[track],RecommendationOptions(max_bpm_delta=0,max_energy_delta=0))['recommendations'][0]
        self.assertEqual(row['compatibility_score'],100)

if __name__=='__main__':unittest.main()
