from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class Intent:
    action: str

@dataclass(frozen=True)
class PlanPlaylistIntent(Intent):
    action: str = 'playlist.plan'
    playlists: tuple[str, ...] = ()
    count: int = 10
    mode: Literal['bpm', 'energy'] = 'bpm'
    max_bpm_step: float = 3.0
    same_genre: bool = False
    harmonic: bool = True
    avoid_adjacent_artist: bool = True
    out_name: str = 'Nueva Selección'

@dataclass(frozen=True)
class SearchTracksIntent(Intent):
    action: str = 'library.search'
    query: str = ''
    limit: int = 20
    offset: int = 0
    genre: str = ''
    bpm_min: float | None = None
    bpm_max: float | None = None
    key: str = ''
    energy_min: float | None = None
    energy_max: float | None = None

@dataclass(frozen=True)
class SimilarTracksIntent(Intent):
    action: str = 'library.similar'
    references: tuple[str, ...] = ()
    count: int = 10
    same_genre: bool = True
    key_mode: Literal['none', 'exact', 'compatible'] = 'compatible'
    match_bpm: bool = False
    match_energy: bool = False

@dataclass(frozen=True)
class MultiSearchIntent(Intent):
    action: str = 'library.multisearch'
    queries: tuple[str, ...] = ()

@dataclass(frozen=True)
class ComparePlaylistsIntent(Intent):
    action: str = 'playlist.compare'
    playlist_a: str = ''
    playlist_b: str = ''

@dataclass(frozen=True)
class AuditLibraryIntent(Intent):
    action: str = 'library.audit'

@dataclass(frozen=True)
class AuditSetlistIntent(Intent):
    action: str = 'setlist.audit'
    track_ids: tuple[str, ...] = ()
    max_bpm_step: float = 3.0

@dataclass(frozen=True)
class ExplainTransitionIntent(Intent):
    action: str = 'transition.explain'
    track_a_id: str = ''
    track_b_id: str = ''

@dataclass(frozen=True)
class RecommendManualIntent(Intent):
    action: str = 'recommend.manual'
    current_track_id: str = ''
    count: int = 5

@dataclass(frozen=True)
class RecommendLiveIntent(Intent):
    action: str = 'recommend.live'

@dataclass(frozen=True)
class SystemStatusIntent(Intent):
    action: str = 'system.status'

@dataclass(frozen=True)
class UnknownIntent(Intent):
    action: str = 'help'
    reason: str = 'No pude identificar una consulta admitida. Consultá el diccionario de funciones.'

@dataclass(frozen=True)
class ListPlaylistsIntent(Intent):
    action: str = 'playlist.list'

@dataclass(frozen=True)
class DuplicatesIntent(Intent):
    action: str = 'library.duplicates'

@dataclass(frozen=True)
class DescribeTrackIntent(Intent):
    action: str = 'track.describe'
    track_id: str = ''
