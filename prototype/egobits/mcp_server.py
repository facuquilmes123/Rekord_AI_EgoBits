"""Adaptador MCP stdio tipado para Rekord AI.
Alineado con el catálogo schemas/tool_catalog.json y protegido por políticas deterministas.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any

from .adapters.xml_adapter import Library, export_xml, diff_libraries
from .core.models import PlanOptions, PlanningError
from .core.planner import plan, harmonic_score
from .core.analysis import compare_playlists, find_duplicates, audit_library, explain_transition, audit_setlist
from .core.recommender import recommend, RecommendationOptions
from .desktop.tray_watcher import ProcessMonitor
from .policy import capability, State

try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP('Rekord AI')
except ImportError:
    # Si fastmcp no está instalado en el entorno actual
    mcp = None

_LIB: Library | None = None
_CURRENT_STATE = None

def current_state():
    return _CURRENT_STATE if _CURRENT_STATE is not None else State(ProcessMonitor().check_state())

def set_current_state(state: State):
    global _CURRENT_STATE
    _CURRENT_STATE = state

def get_library() -> Library:
    global _LIB
    if _LIB is None:
        from .desktop.service import get_or_load_library
        _LIB = get_or_load_library()
    return _LIB

def system_status() -> dict[str, Any]:
    try:
        lib = get_library()
        error = None
    except (OSError, ValueError) as exc:
        lib, error = None, str(exc)
    cap = capability('system.status', current_state(), snapshot=lib is not None)
    return {
        'status': 'online',
        'rekordbox_state': current_state().value,
        'snapshot_loaded': lib is not None,
        'snapshot_revision': lib.revision if lib else None,
        'tracks_count': len(lib.tracks) if lib else 0,
        'playlists_count': len(lib.playlists) if lib else 0,
        'source_path': str(lib.source) if lib else None,
        'library_error': error,
        'demo': bool(lib and lib.source == (Path(__file__).resolve().parents[1] / 'examples/library.xml').resolve()),
        'capability': vars(cap)
    }

def list_playlists() -> dict[str, Any]:
    lib = get_library()
    cap = capability('playlist.list', current_state(), snapshot=True)
    if not cap.enabled:
        raise PermissionError(cap.reason)
    return {
        'revision': lib.revision,
        'playlists': [{'path': p, 'count': len(ids)} for p, ids in lib.playlists.items()]
    }

def search_tracks(query: str = '', limit: int = 20, offset: int = 0,
                  genre: str = '', bpm_min: float | None = None, bpm_max: float | None = None,
                  key: str = '', energy_min: float | None = None, energy_max: float | None = None) -> dict[str, Any]:
    lib = get_library()
    cap = capability('library.search', current_state(), snapshot=True)
    if not cap.enabled:
        raise PermissionError(cap.reason)
    from .ai.intents import SearchTracksIntent
    from .core.search import search_library
    result=search_library(lib,SearchTracksIntent(query=query,limit=limit,offset=offset,genre=genre,
        bpm_min=bpm_min,bpm_max=bpm_max,key=key,energy_min=energy_min,energy_max=energy_max))
    return {**result,'revision':lib.revision}

def plan_playlist(
    playlists: list[str],
    count: int = 10,
    mode: str = 'bpm',
    max_bpm_step: float = 3.0,
    same_genre: bool = False,
    avoid_adjacent_artist: bool = True,
    harmonic: bool = True
) -> dict[str, Any]:
    lib = get_library()
    cap = capability('playlist.plan', current_state(), snapshot=True)
    if not cap.enabled:
        raise PermissionError(cap.reason)
    pool_tracks = lib.pool(playlists)
    opts = PlanOptions(
        count=count,
        mode=mode, # type: ignore
        max_bpm_step=max_bpm_step,
        same_genre=same_genre,
        avoid_adjacent_artist=avoid_adjacent_artist,
        harmonic=harmonic
    )
    result = plan(pool_tracks, opts)
    result['source_revision'] = lib.revision
    result['applied'] = False
    return result

def export_playlist_xml(result: dict[str, Any], name: str, target_path: str) -> dict[str, Any]:
    lib = get_library()
    cap = capability('playlist.export_xml', current_state(), snapshot=True)
    if not cap.enabled:
        raise PermissionError(cap.reason)
    if result.get('source_revision') != lib.revision:
        raise PlanningError('Recalculá la propuesta sobre la biblioteca actual')
    target = Path(target_path)
    out = export_xml(lib, result, name, target)
    return {
        'exported_file': str(out),
        'playlist_name': name,
        'track_count': len(result.get('track_ids', []))
    }

def compare_playlists_tool(playlist_a: str, playlist_b: str) -> dict[str, Any]:
    lib = get_library()
    cap = capability('playlist.compare', current_state(), snapshot=True)
    if not cap.enabled:
        raise PermissionError(cap.reason)
    tracks_a = lib.pool([playlist_a])
    tracks_b = lib.pool([playlist_b])
    return compare_playlists(tracks_a, tracks_b, playlist_a, playlist_b)

def audit_library_tool() -> dict[str, Any]:
    lib = get_library()
    cap = capability('library.audit', current_state(), snapshot=True)
    if not cap.enabled:
        raise PermissionError(cap.reason)
    return audit_library(list(lib.tracks.values()))

def duplicates_tool() -> dict[str, Any]:
    lib = get_library()
    cap = capability('library.duplicates', current_state(), snapshot=True)
    if not cap.enabled:
        raise PermissionError(cap.reason)
    return {'duplicates': find_duplicates(list(lib.tracks.values()))}

def explain_transition_tool(track_a_id: str, track_b_id: str) -> dict[str, Any]:
    lib = get_library()
    cap = capability('transition.explain', current_state(), snapshot=True)
    if not cap.enabled:
        raise PermissionError(cap.reason)
    if track_a_id not in lib.tracks or track_b_id not in lib.tracks:
        raise PlanningError('Track IDs no encontrados en la colección')
    return explain_transition(lib.tracks[track_a_id], lib.tracks[track_b_id])

def recommend_manual_tool(current_track_id: str, count: int = 5, max_bpm_delta: float = 4.0,
                          same_genre: bool = False, harmonic: bool = True,
                          max_energy_delta: float | None = None, avoid_same_artist: bool = True) -> dict[str, Any]:
    lib = get_library()
    cap = capability('recommend.manual', current_state(), snapshot=True, manual_track_id=True)
    if not cap.enabled:
        raise PermissionError(cap.reason)
    if current_track_id not in lib.tracks:
        raise PlanningError(f'Pista actual {current_track_id} no encontrada')
    return recommend(lib.tracks[current_track_id], list(lib.tracks.values()), RecommendationOptions(count=count, max_bpm_delta=max_bpm_delta,
        same_genre=same_genre, harmonic=harmonic, max_energy_delta=max_energy_delta, avoid_same_artist=avoid_same_artist))

def describe_track_tool(track_id: str) -> dict[str, Any]:
    lib = get_library()
    if track_id not in lib.tracks:
        raise PlanningError('ID de pista inexistente')
    return {'track': vars(lib.tracks[track_id]), 'source_revision': lib.revision, 'source': str(lib.source)}

def diff_library_tool(other_xml: str) -> dict[str, Any]:
    return diff_libraries(get_library(), Library(Path(other_xml)))

def audit_setlist_tool(track_ids: list[str], max_bpm_step: float = 3.0) -> dict[str, Any]:
    lib = get_library()
    if not track_ids or len(track_ids) > 100 or any(tid not in lib.tracks for tid in track_ids):
        raise PlanningError('Setlist inválido: 1..100 IDs existentes')
    PlanOptions(max_bpm_step=max_bpm_step)
    return audit_setlist([lib.tracks[tid] for tid in track_ids], max_bpm_step)

def apply_native_tool(*args, **kwargs) -> dict[str, Any]:
    cap = capability('playlist.apply_native', current_state())
    if not cap.enabled:
        raise PermissionError(cap.reason)
    raise NotImplementedError('La escritura nativa requiere revisión y confirmación en la aplicación Windows; no está expuesta por MCP')

# Registro condicional en FastMCP si está disponible
if mcp:
    mcp.tool(name='system.status', annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': False})(system_status)
    mcp.tool(name='playlist.list', annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': False})(list_playlists)
    mcp.tool(name='library.search', annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': False})(search_tracks)
    mcp.tool(name='playlist.plan', annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': False})(plan_playlist)
    mcp.tool(name='playlist.export_xml', annotations={'readOnlyHint': False, 'destructiveHint': False, 'openWorldHint': False})(export_playlist_xml)
    mcp.tool(name='playlist.compare', annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': False})(compare_playlists_tool)
    mcp.tool(name='library.audit', annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': False})(audit_library_tool)
    mcp.tool(name='library.duplicates', annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': False})(duplicates_tool)
    mcp.tool(name='transition.explain', annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': False})(explain_transition_tool)
    mcp.tool(name='recommend.manual', annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': False})(recommend_manual_tool)
    mcp.tool(name='track.describe', annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': False})(describe_track_tool)
    mcp.tool(name='library.diff', annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': False})(diff_library_tool)
    mcp.tool(name='setlist.audit', annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': False})(audit_setlist_tool)

if __name__ == '__main__':
    if mcp:
        mcp.run(transport='stdio')
    else:
        raise SystemExit('SDK MCP no instalado: instalá la dependencia opcional declarada prototype[mcp].')
