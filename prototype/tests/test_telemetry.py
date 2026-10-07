import unittest
from telemetry_fixture import TelemetrySimulator
from egobits.telemetry import NowPlayingEvent
from egobits.policy import capability, State

class TelemetryTests(unittest.TestCase):
    def test_simulator_fresh_and_audible(self):
        sim = TelemetrySimulator(initial_track_id='2', deck_id=1)
        event = sim.get_current_state()
        self.assertIsNotNone(event)
        self.assertTrue(event.is_fresh(max_age_seconds=5.0))
        self.assertTrue(event.is_audible(min_confidence=0.85))

    def test_simulator_stale_event_rejected(self):
        sim = TelemetrySimulator()
        sim.make_stale()
        event = sim.get_current_state()
        self.assertFalse(event.is_fresh(max_age_seconds=5.0))
        self.assertFalse(event.is_audible())

        # PolÃ­tica de recommend.live rechaza cuando la seÃ±al no estÃ¡ vigente
        cap = capability('recommend.live', State.OPEN, snapshot=True, live_fresh=event.is_audible())
        self.assertFalse(cap.enabled)
        self.assertIn('lectura en vivo vigente', cap.reason)

    def test_simulator_paused_deck_not_audible(self):
        sim = TelemetrySimulator()
        sim.set_playback('3', deck_id=2, state='paused')
        event = sim.get_current_state()
        self.assertFalse(event.is_audible())

if __name__ == '__main__':
    unittest.main()
