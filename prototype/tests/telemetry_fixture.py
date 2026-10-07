from __future__ import annotations
from datetime import datetime, timezone
from typing import Literal
from egobits.telemetry.provider import TelemetryProvider, NowPlayingEvent

class TelemetrySimulator(TelemetryProvider):
    """Simulador de telemetrÃ­a de cabina para pruebas deterministas y QA."""
    def __init__(self, initial_track_id: str = '1', deck_id: int = 1):
        self._name = 'Simulador de TelemetrÃ­a (QA Mode)'
        self._available = True
        self._current_track_id = initial_track_id
        self._deck_id = deck_id
        self._state: Literal['playing', 'paused', 'stopped'] = 'playing'
        self._audible_confidence = 0.95
        self._last_observed = datetime.now(timezone.utc).isoformat()

    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return self._available

    def set_availability(self, available: bool):
        self._available = available

    def set_playback(self, track_id: str, deck_id: int = 1, state: Literal['playing', 'paused', 'stopped'] = 'playing', audible_confidence: float = 0.95):
        self._current_track_id = track_id
        self._deck_id = deck_id
        self._state = state
        self._audible_confidence = audible_confidence
        self._last_observed = datetime.now(timezone.utc).isoformat()

    def make_stale(self):
        """Simula una pÃ©rdida de seÃ±al configurando la Ãºltima observaciÃ³n hace 1 hora."""
        self._last_observed = '2000-01-01T00:00:00+00:00'

    def get_current_state(self) -> NowPlayingEvent | None:
        if not self._available:
            return None
        return NowPlayingEvent(
            track_id=self._current_track_id,
            deck_id=self._deck_id,
            observed_at_utc=self._last_observed,
            source='simulator',
            confidence=0.98,
            playback_state=self._state,
            audible_confidence=self._audible_confidence
        )
