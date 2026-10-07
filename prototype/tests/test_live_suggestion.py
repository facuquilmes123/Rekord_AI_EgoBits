import unittest
from datetime import datetime, timezone
from pathlib import Path

from egobits.adapters import Library
from egobits.desktop.live_suggestion import live_suggestion
from egobits.telemetry.provider import NowPlayingEvent, TelemetryProvider
from telemetry_fixture import TelemetrySimulator


class FakeRealProvider(TelemetryProvider):
    def __init__(self, confidence=0.98, audible=0.95):
        self.confidence, self.audible = confidence, audible

    def name(self):
        return 'test-provider'

    def is_available(self):
        return True

    def get_current_state(self):
        return NowPlayingEvent('1', 1, datetime.now(timezone.utc).isoformat(),
                               'test-provider', self.confidence, 'playing', self.audible)


class LiveSuggestionTests(unittest.TestCase):
    def setUp(self):
        self.lib = Library(Path(__file__).resolve().parents[1] / 'examples/library.xml')

    def test_no_provider_or_simulator_never_confirms(self):
        self.assertFalse(live_suggestion(self.lib, None)['confirmed'])
        self.assertFalse(live_suggestion(self.lib, TelemetrySimulator())['confirmed'])

    def test_low_confidence_never_confirms(self):
        self.assertFalse(live_suggestion(self.lib, FakeRealProvider(confidence=0.7))['confirmed'])
        self.assertFalse(live_suggestion(self.lib, FakeRealProvider(audible=0.7))['confirmed'])

    def test_real_fresh_compatible_candidate(self):
        result = live_suggestion(self.lib, FakeRealProvider())
        self.assertTrue(result['confirmed'])
        self.assertIn(result['track_id'], self.lib.tracks)

