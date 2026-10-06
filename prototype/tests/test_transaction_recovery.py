import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from egobits.adapters.transaction_recovery import TransactionRecovery, _digest
from egobits.adapters.native_write import NativePlaylistWriter
from egobits.adapters.windows_exclusive import WindowsExclusiveFiles
from egobits.core.models import PlanningError


try:
    import sqlcipher3  # noqa: F401
    HAVE_SQLCIPHER = True
except ImportError:
    HAVE_SQLCIPHER = False


@unittest.skipUnless(os.name == "nt", "Windows HANDLE operations")
class WindowsRecoveryHandleTests(unittest.TestCase):
    def test_handle_copy_and_exact_sidecar_recreation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "master.db-wal"
            copied = root / "backup-wal"
            recreated = root / "master.db-shm"
            source.write_bytes(b"wal fixture")
            with WindowsExclusiveFiles([source]) as held:
                held.copy_to(source.name, copied)
            self.assertEqual(copied.read_bytes(), b"wal fixture")
            with WindowsExclusiveFiles([recreated], create_missing=[recreated]) as held:
                held.write_from(recreated.name, copied)
                self.assertEqual(held.digest(recreated.name), _digest(copied))
            self.assertEqual(recreated.read_bytes(), b"wal fixture")


@unittest.skipUnless(os.name == "nt" and HAVE_SQLCIPHER, "SQLCipher recovery fixture requires Windows")
class TransactionRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.db = self.folder / "master.db"
        self.xml = self.folder / "masterPlaylists6.xml"
        self.xml.write_text("<DJ_PLAYLISTS/>", encoding="utf-8")
        self._make_crashed_wal()
        self.state = "closed"
        self.writer = NativePlaylistWriter(
            self.folder / "playlist-operations",
            lambda: self.state,
            lambda: {"databases": [str(self.db)], "installations": [{"version": "7.2.19.0342"}]},
        )
        self.recovery = TransactionRecovery(
            self.folder / "native-operations",
            lambda: self.state,
            lambda: {"databases": [str(self.db)], "installations": [{"version": "7.2.19.0342"}]},
            self.writer,
        )

    def _make_crashed_wal(self):
        from egobits.adapters.sqlcipher_read import driver_and_key

        driver, key = driver_and_key()
        conn = driver.connect(str(self.db))
        try:
            conn.execute("PRAGMA key='" + key.replace("'", "''") + "'")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA wal_autocheckpoint=0")
            conn.executescript("""
                CREATE TABLE djmdContent(ID TEXT);
                CREATE TABLE djmdPlaylist(ID TEXT);
                CREATE TABLE djmdSongPlaylist(ID TEXT);
                CREATE TABLE agentRegistry(ID TEXT);
                CREATE TABLE committed_events(value TEXT);
            """)
            conn.commit()
        finally:
            conn.close()
        code = """
import os, sys
from egobits.adapters.sqlcipher_read import driver_and_key
d, key = driver_and_key(); c = d.connect(sys.argv[1])
c.execute(\"PRAGMA key='\" + key.replace(\"'\", \"''\") + \"'\")
c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA wal_autocheckpoint=0')
c.execute('INSERT INTO committed_events(value) VALUES (?)', ('committed-before-crash',)); c.commit()
os._exit(0)
"""
        environment = dict(os.environ)
        prototype = str(Path(__file__).resolve().parents[1])
        environment["PYTHONPATH"] = prototype + os.pathsep + environment.get("PYTHONPATH", "")
        # This is a cold Python+SQLCipher child on an overloaded Windows host;
        # it is a fixture limit only and does not affect product operations.
        result = subprocess.run([sys.executable, "-c", code, str(self.db)], env=environment, capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(Path(str(self.db) + "-wal").is_file(), "child crash must retain a WAL fixture")
        self.assertTrue(Path(str(self.db) + "-shm").is_file(), "child crash must retain a SHM fixture")

    def _committed(self):
        from egobits.adapters.sqlcipher_read import connection
        with connection(self.db) as conn:
            return conn.execute("SELECT value FROM committed_events").fetchall()

    def test_checkpoint_keeps_committed_content_and_raw_backup(self):
        preview = self.recovery.prepare()
        self.assertEqual(preview["operation"], "recover_transactions")
        self.assertEqual(set(preview["files"]), {"master.db", "master.db-wal", "master.db-shm", "masterPlaylists6.xml"})
        review = self.recovery.approval_preview(preview["token"])
        self.assertEqual(review["operation"], "recover_transactions")
        result = self.recovery.apply(preview["token"])
        self.assertEqual(result["state"], "applied")
        self.writer.guard(self.db)
        self.assertEqual(self._committed(), [("committed-before-crash",)])
        journal = json.loads((Path(result["backup_directory"]).parent / "journal.json").read_text())
        for name, value in journal["files"].items():
            self.assertEqual(_digest(Path(result["backup_directory"]) / name), value)

    def test_open_or_changed_collection_blocks_without_writing(self):
        self.state = "open"
        with self.assertRaises(PlanningError):
            self.recovery.prepare()
        self.state = "closed"
        rollback_journal = Path(str(self.db) + "-journal")
        rollback_journal.write_bytes(b"pending rollback fixture")
        with self.assertRaises(PlanningError):
            self.recovery.prepare()
        rollback_journal.unlink()
        preview = self.recovery.prepare()
        before = _digest(self.db)
        self.xml.write_text("<changed/>", encoding="utf-8")
        changed_xml = _digest(self.xml)
        with self.assertRaises(PlanningError):
            self.recovery.apply(preview["token"])
        self.assertEqual(_digest(self.db), before)
        self.assertEqual(_digest(self.xml), changed_xml)
        journal = self.recovery.root / preview["token"] / "journal.json"
        self.assertEqual(json.loads(journal.read_text())["state"], "prepared")

    def test_restore_preserves_db_and_wal_and_rejects_arbitrary_tickets(self):
        prepared = self.recovery.prepare()
        result = self.recovery.apply(prepared["token"])
        source = json.loads((Path(result["backup_directory"]).parent / "journal.json").read_text())
        restore = self.recovery.prepare_restore(result["operation_id"])
        current_backup = Path(restore["backup_directory"])
        restored = self.recovery.restore(restore["token"])
        self.assertEqual(restored["state"], "restored")
        self.assertEqual(self._committed(), [("committed-before-crash",)])
        # SQLite may refresh the volatile WAL-index (`-shm`) while validating a
        # restored collection.  The persistent database and WAL must remain exact.
        for name in ("master.db", "master.db-wal"):
            value = source["files"][name]
            self.assertEqual(_digest(self.folder / name), value)
        self.assertTrue((current_backup / "master.db").is_file())
        with self.assertRaises(PlanningError):
            self.recovery.prepare_restore("../" + result["operation_id"])
        with self.assertRaises(PlanningError):
            self.recovery.restore("not-a-ticket")

    def test_interrupted_restore_is_recoverable_after_backend_restart(self):
        prepared = self.recovery.prepare()
        recovered = self.recovery.apply(prepared["token"])
        restore = self.recovery.prepare_restore(recovered["operation_id"])
        interrupted = Path(restore["backup_directory"]).parent
        manifest_path = interrupted / "journal.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["state"] = "restoring"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        restarted = TransactionRecovery(
            self.folder / "native-operations",
            lambda: self.state,
            lambda: {"databases": [str(self.db)], "installations": [{"version": "7.2.19.0342"}]},
            self.writer,
        )
        listing = {item["id"]: item for item in restarted.backups()}
        self.assertTrue(listing[interrupted.name]["verified"])
        self.assertEqual(listing[interrupted.name]["state"], "restoring")

        retry = restarted.prepare_restore(interrupted.name)
        current = json.loads((Path(retry["backup_directory"]).parent / "journal.json").read_text())
        result = restarted.restore(retry["token"])
        self.assertEqual(result["state"], "restored")
        for name, value in current["staged"].items():
            self.assertEqual(_digest(self.folder / name), value)
