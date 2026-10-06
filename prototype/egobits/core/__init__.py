from .models import Track, Transition, PlanOptions, PlanResult, PlanningError
from .planner import normalize_key, harmonic_score, number, plan
from .analysis import compare_playlists, find_duplicates, audit_library, audit_setlist, explain_transition

def __getattr__(name):
    # Compatibilidad del API previo sin importar adapters durante su inicialización.
    if name in ('Library', 'export_xml', 'diff_libraries'):
        from ..adapters import xml_adapter
        return getattr(xml_adapter, name)
    raise AttributeError(name)

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
