from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Literal

class PlanningError(ValueError):
    """Excepción base para errores de validación y planificación determinista."""
    pass

@dataclass(frozen=True)
class Track:
    id: str
    title: str
    artist: str
    bpm: float | None
    key: str | None
    genre: str
    duration: float | None
    location: str
    energy: float | None = None
    energy_source: str | None = None

@dataclass(frozen=True)
class Transition:
    from_id: str
    to_id: str
    bpm_delta: float
    harmonic_score: float | None
    energy_delta: float | None

@dataclass(frozen=True)
class PlanOptions:
    count: int | None = 10
    mode: Literal['bpm', 'energy'] = 'bpm'
    max_bpm_step: float = 3.0
    harmonic: bool = True
    same_genre: bool = False
    avoid_adjacent_artist: bool = True
    beam_width: int = 24
    allow_insufficient: bool = False

    def __post_init__(self):
        if self.mode not in ('bpm', 'energy'):
            raise PlanningError('Modo inválido; debe ser "bpm" o "energy"')
        if self.count is not None and (type(self.count) is not int or self.count < 1):
            raise PlanningError('Cantidad fuera de rango; debe ser al menos 1')
        if type(self.max_bpm_step) not in (int, float) or not math.isfinite(self.max_bpm_step) or not 0 < self.max_bpm_step <= 30:
            raise PlanningError('Salto BPM inválido')
        if type(self.beam_width) is not int or not 1 <= self.beam_width <= 64:
            raise PlanningError('Ancho de búsqueda inválido')
        if any(type(value) is not bool for value in (self.harmonic, self.same_genre, self.avoid_adjacent_artist, self.allow_insufficient)):
            raise PlanningError('Las restricciones deben ser booleanas')

@dataclass
class PlanResult:
    track_ids: list[str]
    mode: str
    score: float
    transitions: list[dict]
    excluded: dict[str, str]
    algorithm: str
    duration_sum_seconds: float | None
    warnings: list[str]
    tracks: list[dict]
    adjustments: list[str] = field(default_factory=list)
