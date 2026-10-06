from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal
import math

@dataclass(frozen=True)
class NowPlayingEvent:
    track_id: str
    deck_id: int
    observed_at_utc: str
    source: str
    confidence: float
    playback_state: Literal['playing', 'paused', 'stopped']
    audible_confidence: float

    def is_fresh(self, max_age_seconds: float = 5.0) -> bool:
        """Verifica si el evento fue observado dentro de la ventana de frescura tolerada."""
        try:
            obs = datetime.fromisoformat(self.observed_at_utc)
            delta = (datetime.now(timezone.utc) - obs).total_seconds()
            return 0 <= delta < max_age_seconds
        except Exception:
            return False

    def is_audible(self, min_confidence: float = 0.85) -> bool:
        """Determina si la pista se considera efectivamente audible en el master."""
        return (
            self.playback_state == 'playing' and
            type(self.confidence) in (int, float) and type(self.audible_confidence) in (int, float) and
            math.isfinite(self.confidence) and min_confidence < self.confidence <= 1 and
            math.isfinite(self.audible_confidence) and min_confidence < self.audible_confidence <= 1 and
            self.is_fresh()
        )

class TelemetryProvider(ABC):
    """Contrato base abstracto para cualquier proveedor de telemetría en tiempo real."""
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def get_current_state(self) -> NowPlayingEvent | None:
        pass
