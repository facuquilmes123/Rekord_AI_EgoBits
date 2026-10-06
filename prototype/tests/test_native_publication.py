import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from egobits.adapters.native_write import NativePlaylistWriter, digest, save_journal
from egobits.adapters.windows_exclusive import WindowsExclusiveFiles
from egobits.core.models import PlanningError


@unittest.skipUnless(os.name == 'nt', 'Windows exclusive handles')
class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.db=self.root/'master.db'
        self.names=('master.db','masterPlaylists6.xml')
        for name in self.names: (self.root/name).write_bytes(b'original-'+name.encode())
        self.writer=NativePlaylistWriter(self.root/'ops',lambda:'closed',lambda:{'databases':[str(self.db)],'installations':[{'version':'7.2.19'}]})
        self.token='a'*32;self.work=self.writer.root/self.token
        (self.work/'backup').mkdir(parents=True);(self.work/'stage').mkdir()
        for n in self.names:
            (self.work/'backup'/n).write_bytes((self.root/n).read_bytes())
            (self.work/'stage'/n).write_bytes(b'new-'+n.encode())
        self.manifest={'state':'prepared','created_at':time.time(),'database':str(self.db),'files':{n:digest(self.root/n) for n in self.names},'staged':{n:digest(self.work/'stage'/n) for n in self.names},'name':'Test'}
        save_journal(self.work,self.manifest)
        self.writer.previews[self.token]=(time.monotonic()+600,self.work,'rev')
        self.inspector=patch('egobits.adapters.native_write.inspect',return_value={'integrity':'ok'});self.inspector.start();self.addCleanup(self.inspector.stop)
        # This fixture tests real Windows publication/rollback of opaque bytes.
        # SQLCipher schema compatibility has separate tests with real SQLite schemas.
        self.schema=patch('egobits.adapters.native_write.schema_signature',return_value='fixture-schema');self.schema.start();self.addCleanup(self.schema.stop)

    def test_real_os_lock_and_truncate(self):
        with WindowsExclusiveFiles([self.db]) as held:
            with self.assertRaises(OSError): self.db.read_bytes()
            held.write_from(self.db.name,self.work/'stage'/self.db.name)
            self.assertEqual(held.digest(self.db.name),self.manifest['staged'][self.db.name])
        self.assertEqual(self.db.read_bytes(),b'new-master.db')

    def test_apply_and_restore_with_pre_restore_backup(self):
        self.assertEqual(self.writer.apply(self.token,'rev')['state'],'applied')
        for n in self.names: self.assertEqual(digest(self.root/n),self.manifest['staged'][n])
        with self.assertRaises(PlanningError): self.writer.apply(self.token,'rev')
        preview=self.writer.prepare_restore(self.token)
        self.assertEqual(self.writer.restore(preview['token'])['state'],'applied')
        for n in self.names:
            self.assertEqual(digest(self.root/n),self.manifest['files'][n])
            self.assertEqual(digest(Path(preview['backup_directory'])/n),self.manifest['staged'][n])
        self.assertTrue(all(x['verified'] for x in self.writer.backups()))

    def test_changed_source_blocks(self):
        self.db.write_bytes(b'changed')
        with self.assertRaises(PlanningError):self.writer.apply(self.token,'rev')
        self.assertEqual(self.db.read_bytes(),b'changed')

    def test_changed_schema_blocks_publication_before_write(self):
        with patch('egobits.adapters.native_write.schema_signature',side_effect=['original-schema','changed-schema']):
            with self.assertRaises(PlanningError):self.writer.apply(self.token,'rev')
        self.assertEqual(digest(self.db),self.manifest['files'][self.db.name])

    def test_changed_schema_blocks_restore_before_new_backup(self):
        with patch('egobits.adapters.native_write.schema_signature',side_effect=['backup-schema','changed-schema']):
            with self.assertRaises(PlanningError):self.writer.prepare_restore(self.token)
        self.assertEqual(len(list(self.writer.root.iterdir())),1)

    def test_approval_preview_is_unavailable_after_ticket_consumption(self):
        self.assertEqual(self.writer.approval_preview(self.token)['operation'],'create_playlist')
        self.writer.apply(self.token,'rev')
        with self.assertRaises(PlanningError):self.writer.approval_preview(self.token)

    def test_backup_and_stage_tamper_block(self):
        for folder in ('backup','stage'):
            target=self.work/folder/self.db.name;old=target.read_bytes();target.write_bytes(b'tampered')
            with self.assertRaises(PlanningError):self.writer._publish(self.work,self.manifest)
            target.write_bytes(old)
        self.assertEqual(digest(self.db),self.manifest['files'][self.db.name])

    def test_partial_failure_rolls_back_both(self):
        original=WindowsExclusiveFiles.write_from;failed=False
        def fail_once(held,name,source):
            nonlocal failed
            if name==self.names[1] and Path(source).parent.name=='stage' and not failed:
                failed=True;raise OSError('Injected disk failure')
            return original(held,name,source)
        with patch.object(WindowsExclusiveFiles,'write_from',fail_once):
            with self.assertRaises(PlanningError):self.writer.apply(self.token,'rev')
        for n in self.names:self.assertEqual(digest(self.root/n),self.manifest['files'][n])
        self.assertEqual(json.loads((self.work/'journal.json').read_text())['state'],'rolled_back')

    def test_open_process_blocks_and_expired_ticket(self):
        self.writer.process_state=lambda:'open'
        with self.assertRaises(PlanningError):self.writer.apply(self.token,'rev')

    def test_process_reopens_during_write_rolls_back_under_locks(self):
        original=WindowsExclusiveFiles.write_from
        def reopen(held,name,source):
            result=original(held,name,source)
            if Path(source).parent.name=='stage': self.writer.process_state=lambda:'open'
            return result
        with patch.object(WindowsExclusiveFiles,'write_from',reopen):
            with self.assertRaises(PlanningError):self.writer.apply(self.token,'rev')
        for n in self.names:self.assertEqual(digest(self.root/n),self.manifest['files'][n])
        self.writer.previews[self.token]=(0,self.work,'rev')
        with self.assertRaises(PlanningError):self.writer.apply(self.token,'rev')

    def test_recovery_receipt_survives_restart(self):
        self.manifest['state']='publishing';save_journal(self.work,self.manifest)
        with self.assertRaises(PlanningError):self.writer.guard(self.db)
        self.writer.previews.clear()
        preview=self.writer.prepare_restore(self.token)
        self.writer.restore(preview['token'])
        self.writer.guard(self.db)

    def test_traversal_and_stale_restore_block(self):
        with self.assertRaises(PlanningError):self.writer.prepare_restore('../master.db')
        preview=self.writer.prepare_restore(self.token);self.db.write_bytes(b'changed-after-review')
        with self.assertRaises(PlanningError):self.writer.restore(preview['token'])
        self.assertEqual(self.db.read_bytes(),b'changed-after-review')
