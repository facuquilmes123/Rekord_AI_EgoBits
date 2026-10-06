from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class State(str, Enum):
    OPEN = 'open'
    CLOSED = 'closed'
    UNKNOWN = 'unknown'

@dataclass(frozen=True)
class Capability:
    enabled: bool
    reason: str
    required_state: str

# Herramientas de solo lectura que operan sobre snapshot XML en cualquier estado
_ANY_SNAPSHOT_TOOLS = {
    'playlist.list',
    'library.search',
    'playlist.plan',
    'playlist.export_xml',
    'playlist.compare',
    'library.duplicates',
    'library.audit',
    'library.diff',
    'track.describe',
    'transition.explain',
    'setlist.audit',
    'recommend.manual',
}

def capability(
    tool: str,
    state: State,
    *,
    snapshot: bool = False,
    two_snapshots: bool = False,
    live_fresh: bool = False,
    writer_certified: bool = False,
    backup_verified: bool = False,
    revision_matches: bool = False,
    manual_track_id: bool = False,
    plan_present: bool = False,
    opt_in: bool = True
) -> Capability:
    """Verifica si una herramienta específica es elegible bajo el estado actual y sus precondiciones.
    Aplica el principio de Fail-Closed ante cualquier estado desconocido o requisito faltante.
    """
    if tool == 'system.status':
        return Capability(True, '', 'any')

    if tool == 'notification.configure':
        return Capability(True, '', 'any')

    if tool in _ANY_SNAPSHOT_TOOLS:
        if not snapshot:
            return Capability(False, 'Cargá una biblioteca local o snapshot XML', 'any')
        if tool == 'library.diff' and not two_snapshots:
            return Capability(False, 'Requiere dos snapshots para comparar', 'any')
        if tool == 'recommend.manual' and not manual_track_id:
            return Capability(False, 'Seleccioná una pista de referencia', 'any')
        return Capability(True, '', 'any')

    if tool == 'recommend.live':
        ok = (state == State.OPEN and snapshot and live_fresh and opt_in)
        if not ok:
            if state != State.OPEN:
                reason = 'Requiere Rekordbox abierto'
            elif not live_fresh:
                reason = 'Requiere lectura en vivo vigente y señal fresca de deck audible'
            elif not snapshot:
                reason = 'Requiere snapshot de colección cargado'
            else:
                reason = 'Requiere confirmación opt-in del usuario'
            return Capability(False, reason, 'open')
        return Capability(True, '', 'open')

    if tool == 'playlist.apply_native':
        if state != State.CLOSED:
            return Capability(False, 'Cerrá Rekordbox; si no se puede comprobar su estado, la escritura se bloquea', 'closed')
        if not writer_certified:
            return Capability(False, 'Adaptador de escritura aún no certificado para esta versión', 'closed')
        if not backup_verified:
            return Capability(False, 'Respaldo verificado requerido', 'closed')
        if not revision_matches:
            return Capability(False, 'La biblioteca cambió: recalcular propuesta', 'closed')
        return Capability(True, '', 'closed')

    if tool == 'device.export':
        if state!=State.CLOSED:return Capability(False,'Cerrá Rekordbox y sus agentes antes de preparar la exportación USB','closed')
        if not backup_verified or not revision_matches:return Capability(False,'Prepará el USB DeviceSQL en Laboratorio DJ: respaldo, revisión vigente y confirmación nativa','closed')
        return Capability(True,'Requiere revisión y confirmación nativa; Device Library Plus se gestiona desde Rekordbox','closed')

    return Capability(False, f'Función no admitida: {tool}', 'unsupported')

class NativeWriterUnavailable:
    """Escritor no disponible de forma deliberada en este kit inicial."""
    def apply(self, *args, **kwargs):
        raise NotImplementedError('Escritura nativa no implementada; usar XML')
