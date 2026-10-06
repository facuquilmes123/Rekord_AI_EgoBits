"""Crash-safe checkpoint and restoration of a closed Rekordbox SQLCipher collection.

The original database is never replaced by a staged copy.  A recovery snapshot
contains the database and every present WAL sidecar before the checkpoint.  If
the checkpoint fails after it begins, those exact bytes are written back through
exclusive Windows handles.  Sidecars are never deleted by this adapter.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import threading
import time

from .sqlcipher_read import connection, inspect
from .windows_exclusive import WindowsExclusiveFiles
from ..core.models import PlanningError


_TOKEN = re.compile(r"[0-9a-f]{32}")
_VERSION = re.compile(r"[67]\.\d+(?:\.\d+){0,2}")
_NAMES = ("master.db", "master.db-wal", "master.db-shm", "masterPlaylists6.xml")
# `restoring` is deliberately recoverable after a backend crash: its `backup`
# is the complete pre-restore current state, and can itself be restored.
_RECOVERABLE = {"prepared", "checkpointing", "applied", "recovery_required", "rolled_back", "restored", "prepared_restore", "restoring"}


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def _save_journal(work: Path, manifest: dict) -> None:
    pending = work / "journal.pending"
    with pending.open("w", encoding="utf-8") as stream:
        json.dump(manifest, stream, sort_keys=True, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(pending, work / "journal.json")


class TransactionRecovery:
    """Prepare/review/apply a SQLCipher WAL checkpoint; approval lives in the caller."""

    def __init__(self, root, process_state, discover, native_writer, *, ticket_seconds=600):
        base = Path(root).resolve()
        self.root = base if base.name == "transaction-recovery" else base / "transaction-recovery"
        self.process_state = process_state
        self.discover = discover
        self.native_writer = native_writer
        self.ticket_seconds = ticket_seconds
        self.previews: dict[str, tuple[float, Path, str]] = {}
        self.lock = threading.Lock()

    def _detected_database(self) -> Path:
        discovered = self.discover()
        raw = discovered.get("databases", []) if isinstance(discovered, dict) else []
        try:
            databases = {Path(item).resolve(strict=True) for item in raw}
        except (OSError, TypeError):
            raise PlanningError("No se pudo validar la base de la instalación detectada") from None
        if len(databases) != 1:
            raise PlanningError("Seleccioná una única colección Rekordbox detectada antes de recuperar transacciones")
        db = databases.pop()
        if db.name != "master.db":
            raise PlanningError("La base detectada no es el master.db nativo")
        versions = discovered.get("installations", []) if isinstance(discovered, dict) else []
        values = [row.get("version") for row in versions if isinstance(row, dict)]
        if not values or not all(isinstance(value, str) and _VERSION.fullmatch(value.strip()) for value in values):
            raise PlanningError("Sólo se admite Rekordbox 6/7 con versión identificada")
        return db

    def _assert_closed(self, db: Path) -> None:
        if self.process_state() != "closed":
            raise PlanningError("Cerrá Rekordbox y sus agentes antes de recuperar transacciones")
        if self._detected_database() != db.resolve(strict=True):
            raise PlanningError("La base ya no coincide con la instalación detectada")
        if (db.parent / "master.db-journal").is_file():
            raise PlanningError("Hay un rollback journal activo; esta recuperación sólo admite WAL")
        if getattr(self.native_writer, "stop_requested", threading.Event()).is_set():
            raise PlanningError("Rekord AI se está cerrando; volvé a abrirlo antes de recuperar")

    def _writer_lock(self):
        lock = getattr(self.native_writer, "lock", None)
        if lock is None or not lock.acquire(blocking=False):
            raise PlanningError("Hay una operación nativa en curso; esperá a que finalice")
        return lock

    def _files(self, db: Path) -> list[Path]:
        result = []
        for name in _NAMES:
            path = db.parent / name
            if path.is_file():
                if path.resolve(strict=True).parent != db.parent.resolve(strict=True):
                    raise PlanningError("La colección contiene una ruta no segura")
                result.append(path)
        if not result or result[0].name != "master.db":
            raise PlanningError("Falta master.db; no hay una colección recuperable")
        return result

    def _space(self, files: list[Path]) -> None:
        total = sum(path.stat().st_size for path in files)
        reserve = max(64 * 1024 ** 2, total)
        target = self.root
        while not target.exists():
            target = target.parent
        if shutil.disk_usage(target).free < total * 2 + reserve or shutil.disk_usage(files[0].parent).free < reserve:
            raise PlanningError("Espacio insuficiente para el respaldo y la recuperación")

    def _new_work(self) -> tuple[str, Path]:
        self.root.mkdir(parents=True, exist_ok=True)
        token = secrets.token_hex(16)
        work = self.root / token
        work.mkdir()
        (work / "backup").mkdir()
        (work / "stage").mkdir()
        return token, work

    def _valid_id(self, value: str) -> bool:
        return isinstance(value, str) and bool(_TOKEN.fullmatch(value))

    def _load(self, operation_id: str) -> tuple[Path, dict]:
        if not self._valid_id(operation_id):
            raise PlanningError("Respaldo inválido")
        work = self.root / operation_id
        journal = work / "journal.json"
        try:
            manifest = json.loads(journal.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise PlanningError("Recibo de recuperación ilegible") from None
        if work.parent != self.root or not isinstance(manifest, dict) or manifest.get("operation") not in {"recover_transactions", "restore_transactions"}:
            raise PlanningError("Recibo de recuperación inválido")
        return work, manifest

    def _validate_manifest(self, work: Path, manifest: dict, *, stage=False) -> None:
        if not isinstance(manifest.get("database"), str):
            raise PlanningError("Recibo sin base válida")
        db = Path(manifest["database"])
        if db != self._detected_database():
            raise PlanningError("El recibo pertenece a otra colección")
        hashes = manifest.get("staged" if stage else "files")
        if not isinstance(hashes, dict) or not hashes or any(name not in _NAMES or not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value) for name, value in hashes.items()):
            raise PlanningError("Recibo de respaldo inválido")
        folder = work / ("stage" if stage else "backup")
        for name, value in hashes.items():
            path = folder / name
            if path.parent != folder or not path.is_file() or _digest(path) != value:
                raise PlanningError("El respaldo fue alterado")

    def _snapshot(self, work: Path, db: Path, *, folder="backup") -> dict[str, str]:
        files = self._files(db)
        target = work / folder
        hashes: dict[str, str] = {}
        with WindowsExclusiveFiles(files) as held:
            self._assert_closed(db)
            for path in files:
                name = path.name
                hashes[name] = held.digest(name)
                held.copy_to(name, target / name)
                if _digest(target / name) != hashes[name]:
                    raise PlanningError("El respaldo no coincide con el archivo bloqueado")
        return hashes

    def _current_hashes(self, db: Path, expected: dict[str, str]) -> None:
        names = {path.name for path in self._files(db)}
        if names != set(expected):
            raise PlanningError("Los archivos de transacción cambiaron desde la revisión")
        with WindowsExclusiveFiles([db.parent / name for name in expected]) as held:
            self._assert_closed(db)
            if any(held.digest(name) != value for name, value in expected.items()):
                raise PlanningError("La colección cambió desde el respaldo")

    def prepare(self):
        with self.lock:
            held = self._writer_lock()
            try:
                db = self._detected_database()
                self._assert_closed(db)
                self._space(self._files(db))
                # Readability/schema are checked before any journal or file operation.
                if inspect(db)["integrity"] != "ok":
                    raise PlanningError("La base SQLCipher no supera integridad; se preservó sin cambios")
                token, work = self._new_work()
                _save_journal(work, {"operation": "recover_transactions", "state": "preparing", "created_at": time.time(), "database": str(db)})
                hashes = self._snapshot(work, db)
                self._assert_closed(db)
                manifest = {"operation": "recover_transactions", "state": "prepared", "created_at": time.time(), "database": str(db), "files": hashes, "schema": "rekordbox-6-7"}
                _save_journal(work, manifest)
                self.previews[token] = (time.monotonic() + self.ticket_seconds, work, "recover_transactions")
                return {"operation": "recover_transactions", "token": token, "backup_directory": str(work / "backup"), "files": sorted(hashes), "expires_seconds": self.ticket_seconds, "requires_confirmation": True}
            finally:
                held.release()

    def approval_preview(self, token):
        if not self._valid_id(token):
            raise PlanningError("Propuesta inválida")
        with self.lock:
            item = self.previews.get(token)
            if not item or item[0] < time.monotonic():
                raise PlanningError("La propuesta venció")
            work, operation = item[1], item[2]
            _, manifest = self._load(work.name)
            if manifest.get("state") not in {"prepared", "prepared_restore"} or manifest.get("operation") != operation:
                raise PlanningError("Propuesta no aplicable")
            digest = hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            return {"token": token, "operation": operation, "digest": digest, "summary": "Se realizará un checkpoint SQLCipher con respaldo completo de DB, WAL, SHM y XML presentes." if operation == "recover_transactions" else "Se restaurará el estado completo respaldado. El estado actual queda respaldado antes de escribir."}

    def _checkpoint(self, db: Path) -> dict:
        # BEGIN EXCLUSIVE ends before wal_checkpoint: SQLite forbids checkpointing
        # from inside an open transaction. locking_mode remains exclusive for this connection.
        with connection(db, readonly=False) as conn:
            mode = conn.execute("PRAGMA locking_mode=EXCLUSIVE").fetchone()
            if not mode or str(mode[0]).casefold() != "exclusive":
                raise PlanningError("SQLite no confirmó el bloqueo exclusivo")
            conn.execute("BEGIN EXCLUSIVE")
            conn.execute("COMMIT")
            row = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            if row is None or len(row) != 3 or row[0] != 0:
                raise PlanningError("SQLite no pudo completar el checkpoint WAL")
            if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise PlanningError("El checkpoint no supera integridad")
            return {"busy": row[0], "log_frames": row[1], "checkpointed_frames": row[2]}

    def _restore_locked(self, work: Path, manifest: dict) -> None:
        db = self._detected_database()
        target = manifest["staged"] if manifest["operation"] == "restore_transactions" else manifest["files"]
        self._validate_manifest(work, manifest, stage=manifest["operation"] == "restore_transactions")
        current = {path.name: path for path in self._files(db)}
        extra = set(current) - set(target)
        # We never delete a sidecar that was absent from the backed-up state.
        # If one must be retired, keep it in this operation's isolated area via
        # a held HANDLE.  Cross-volume retirement cannot be made atomic.
        retirement = work / "retired" / manifest.get("state", "recovery")
        if extra:
            if db.anchor.casefold() != work.anchor.casefold():
                raise PlanningError("No es seguro retirar sidecars en otro volumen")
            retirement.mkdir(parents=True, exist_ok=True)
            if any((retirement / name).exists() for name in extra):
                raise PlanningError("Ya existe una copia retirada; se requiere recuperación manual")
        names = sorted(set(target) | set(current))
        paths = [db.parent / name for name in names]
        # Missing backup sidecars may have been removed by SQLite.  CREATE_NEW is
        # restricted to those exact names from the signed-by-hash local receipt.
        create_missing = [path for path in paths if path.name in target and path.name not in current]
        with WindowsExclusiveFiles(paths, allow_rename=bool(extra), create_missing=create_missing) as held:
            self._assert_closed(db)
            for name in ("master.db", "master.db-wal", "master.db-shm", "masterPlaylists6.xml"):
                if name in target:
                    held.write_from(name, work / ("stage" if manifest["operation"] == "restore_transactions" else "backup") / name)
            for name in sorted(extra):
                held.rename(name, retirement / name)
            if any(held.digest(name) != value for name, value in target.items()):
                raise PlanningError("La restauración no coincide con el respaldo")

    def apply(self, token):
        if not self._valid_id(token):
            raise PlanningError("Propuesta inválida")
        with self.lock:
            item = self.previews.pop(token, None)
            if not item or item[0] < time.monotonic() or item[2] != "recover_transactions":
                raise PlanningError("La propuesta venció o ya fue utilizada")
            work, manifest = self._load(item[1].name)
            if manifest.get("state") != "prepared":
                raise PlanningError("Propuesta no aplicable")
            held = self._writer_lock()
            mutation_started = False
            try:
                db = self._detected_database()
                self._validate_manifest(work, manifest)
                self._assert_closed(db)
                self._current_hashes(db, manifest["files"])
                manifest["state"] = "checkpointing"
                _save_journal(work, manifest)  # durable intent before any SQLCipher write
                self._assert_closed(db)
                mutation_started = True  # _checkpoint may now alter DB/WAL.
                manifest["checkpoint"] = self._checkpoint(db)
                self._assert_closed(db)
                # `_checkpoint` performs quick_check through its writable,
                # exclusive connection.  Do not reopen read-only here: on a
                # closed WAL database that can recreate -wal/-shm after SQLite
                # has safely retired them on the last RW close.
                manifest["post_checkpoint"] = {path.name: _digest(path) for path in self._files(db)}
                manifest["state"] = "applied"
                _save_journal(work, manifest)
                return {"operation": "recover_transactions", "operation_id": work.name, "state": "applied", "backup_directory": str(work / "backup"), "checkpoint": manifest["checkpoint"]}
            except Exception:
                # A failed discovery/hash/closed-state check has not touched the
                # collection.  Restoring the older snapshot here would destroy
                # the newly detected data, so propagate it unchanged.
                if not mutation_started:
                    raise
                try:
                    self._restore_locked(work, manifest)
                    manifest["state"] = "rolled_back"
                    _save_journal(work, manifest)
                except Exception:
                    manifest["state"] = "recovery_required"
                    _save_journal(work, manifest)
                    raise PlanningError("El checkpoint quedó pendiente de recuperación; el respaldo sigue disponible") from None
                raise PlanningError("El checkpoint falló y se restauró el respaldo verificado") from None
            finally:
                held.release()

    def backups(self):
        if not self.root.exists():
            return []
        result = []
        for journal in self.root.glob("*/journal.json"):
            try:
                work, manifest = self._load(journal.parent.name)
                if manifest.get("operation") not in {"recover_transactions", "restore_transactions"} or manifest.get("state") not in _RECOVERABLE:
                    raise ValueError
                self._validate_manifest(work, manifest)
                if manifest["operation"] == "restore_transactions":
                    self._validate_manifest(work, manifest, stage=True)
                result.append({"id": work.name, "operation": manifest["operation"], "name": "Recuperación de transacciones", "state": manifest["state"], "created_at": manifest.get("created_at", 0), "verified": True, "restores": manifest.get("restores")})
            except (OSError, ValueError, PlanningError):
                result.append({"id": journal.parent.name, "operation": "recovery", "name": "Respaldo de recuperación ilegible", "state": "invalid", "created_at": 0, "verified": False})
        return sorted(result, key=lambda item: item["created_at"], reverse=True)

    def prepare_restore(self, operation_id):
        with self.lock:
            held = self._writer_lock()
            try:
                origin, original = self._load(operation_id)
                if original.get("operation") not in {"recover_transactions", "restore_transactions"} or original.get("state") not in _RECOVERABLE:
                    raise PlanningError("El respaldo no se puede restaurar")
                self._validate_manifest(origin, original)
                db = self._detected_database()
                self._assert_closed(db)
                self._space(self._files(db))
                token, work = self._new_work()
                _save_journal(work, {"operation": "restore_transactions", "state": "preparing_restore", "created_at": time.time(), "database": str(db), "restores": operation_id})
                current = self._snapshot(work, db)
                staged = {}
                for name, value in original["files"].items():
                    source = origin / "backup" / name
                    target = work / "stage" / name
                    with source.open("rb") as read, target.open("xb") as write:
                        shutil.copyfileobj(read, write)
                        write.flush(); os.fsync(write.fileno())
                    if _digest(target) != value:
                        raise PlanningError("El respaldo original fue alterado")
                    staged[name] = value
                self._assert_closed(db)
                manifest = {"operation": "restore_transactions", "state": "prepared_restore", "created_at": time.time(), "database": str(db), "files": current, "staged": staged, "restores": operation_id}
                _save_journal(work, manifest)
                self.previews[token] = (time.monotonic() + self.ticket_seconds, work, "restore_transactions")
                return {"operation": "restore_transactions", "token": token, "backup_directory": str(work / "backup"), "restores": operation_id, "expires_seconds": self.ticket_seconds, "requires_confirmation": True}
            finally:
                held.release()

    def restore(self, token):
        if not self._valid_id(token):
            raise PlanningError("Propuesta inválida")
        with self.lock:
            item = self.previews.pop(token, None)
            if not item or item[0] < time.monotonic() or item[2] != "restore_transactions":
                raise PlanningError("La propuesta venció o ya fue utilizada")
            work, manifest = self._load(item[1].name)
            if manifest.get("state") != "prepared_restore":
                raise PlanningError("Restauración no aplicable")
            held = self._writer_lock()
            mutation_started = False
            try:
                db = self._detected_database()
                self._validate_manifest(work, manifest)
                self._validate_manifest(work, manifest, stage=True)
                self._assert_closed(db)
                self._current_hashes(db, manifest["files"])
                manifest["state"] = "restoring"
                _save_journal(work, manifest)
                self._assert_closed(db)
                mutation_started = True  # _restore_locked may replace DB/WAL.
                self._restore_locked(work, manifest)
                self._assert_closed(db)
                if inspect(db)["integrity"] != "ok":
                    raise PlanningError("La restauración no supera integridad")
                manifest["state"] = "restored"
                _save_journal(work, manifest)
                origin, previous = self._load(manifest["restores"])
                previous["state"] = "restored"
                _save_journal(origin, previous)
                return {"operation": "restore_transactions", "operation_id": work.name, "state": "restored", "backup_directory": str(work / "backup"), "restores": manifest["restores"]}
            except Exception:
                if not mutation_started:
                    raise
                try:
                    self._restore_locked(work, {**manifest, "operation": "recover_transactions", "files": manifest["files"]})
                    manifest["state"] = "rolled_back"
                    _save_journal(work, manifest)
                except Exception:
                    manifest["state"] = "recovery_required"
                    _save_journal(work, manifest)
                    raise PlanningError("La restauración quedó pendiente; el respaldo actual sigue disponible") from None
                raise PlanningError("La restauración falló y se recuperó el estado actual") from None
            finally:
                held.release()
