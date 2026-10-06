"""Fachada unificada y compatible de egobits.core.
Reexporta modelos, planificador, análisis y adaptador XML para compatibilidad total con tests existentes.
"""
from __future__ import annotations

from .core.models import Track, Transition, PlanOptions, PlanResult, PlanningError
from .core.planner import normalize_key, harmonic_score, number, plan
from .core.analysis import compare_playlists, find_duplicates, audit_library, audit_setlist, explain_transition
from .adapters.xml_adapter import Library, export_xml, diff_libraries

__all__ = [
    'Track',
    'Transition',
    'PlanOptions',
    'PlanResult',
    'PlanningError',
    'normalize_key',
    'harmonic_score',
    'number',
    'plan',
    'compare_playlists',
    'find_duplicates',
    'audit_library',
    'audit_setlist',
    'explain_transition',
    'Library',
    'export_xml',
    'diff_libraries',
]
