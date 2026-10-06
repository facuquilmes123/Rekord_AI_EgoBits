from __future__ import annotations
import hashlib
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from ..core.models import PlanningError

@dataclass(frozen=True)
class BackupReceipt:
    source_path: str
    backup_path: str
    sha256: str
    size_bytes: int
    created_at_utc: str
    verified_restore: bool

def create_verified_backup(source: Path, destination_dir: Path) -> BackupReceipt:
    """Crea un respaldo seguro de la base de datos de Rekordbox y verifica su integridad.
    Regla estricta: si el respaldo o la prueba de restauración en copia fallan, aborta
    inmediatamente lanzando PlanningError. Nunca continúa una mutación con respaldo fallido.
    """
    source = source.resolve()
    if not source.exists() or not source.is_file():
        raise PlanningError(f'Archivo fuente para respaldo no existe: {source}')

    raw_source = source.read_bytes()
    source_hash = hashlib.sha256(raw_source).hexdigest()

    destination_dir = destination_dir.resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    backup_file = destination_dir / f"{source.stem}_backup_{timestamp}_{source_hash[:8]}{source.suffix}"

    try:
        shutil.copy2(source, backup_file)
    except Exception as e:
        raise PlanningError(f'Fallo al escribir copia de respaldo: {e}')

    raw_backup = backup_file.read_bytes()
    backup_hash = hashlib.sha256(raw_backup).hexdigest()

    if backup_hash != source_hash:
        # Falla de integridad inmediata
        try:
            backup_file.unlink(missing_ok=True)
        except Exception:
            pass
        raise PlanningError('Discrepancia de hash SHA-256 en la copia de respaldo; abortando operación')

    # Ensayo de restauración sobre copia temporal en espacio aislado
    with tempfile.TemporaryDirectory() as td:
        test_restore = Path(td) / 'test_restore.db'
        try:
            shutil.copy2(backup_file, test_restore)
            if hashlib.sha256(test_restore.read_bytes()).hexdigest() != source_hash:
                raise ValueError('La prueba de restauración en copia no coincide')
        except Exception as e:
            try:
                backup_file.unlink(missing_ok=True)
            except Exception:
                pass
            raise PlanningError(f'Fallo al verificar restauración en copia de prueba: {e}')

    return BackupReceipt(
        source_path=str(source),
        backup_path=str(backup_file),
        sha256=backup_hash,
        size_bytes=len(raw_backup),
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        verified_restore=True
    )
