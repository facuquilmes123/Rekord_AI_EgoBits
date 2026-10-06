import copy
from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from egobits.adapters.native_write import NativePlaylistWriter,digest
from egobits.adapters.duplicate_native import native_mapping,verify_changes,prepare
from egobits.adapters.audio_recovery import AudioRecovery,restore_plan
from egobits.adapters.xml_adapter import Library
from egobits.core.models import PlanningError
from egobits.desktop.duplicate_scan import DuplicateScan


class DuplicateMappingTests(unittest.TestCase):
    def setUp(self):
        self.before={'djmdContent':(['ID','UUID','FolderPath','Title'],[('1','u1','C:/a.mp3','Tema'),('2','u2','C:/b.mp3','Tema')]),
                     'djmdSongPlaylist':(['ID','ContentID','PlaylistID','TrackNo'],[('m','2','p',3)]),
                     'djmdSongHistory':(['ID','ContentID'],[('h','2')])}
        self.rule=[{'id':'2','keeper_id':'1','path':'C:/b.mp3','keeper_path':'C:/a.mp3'}]

    def test_metadata_conflicts_and_unknown_dependencies_protected(self):
        self.assertEqual(native_mapping(self.before,self.rule)[0],{'2':'1'})
        self.before['other']=(['ContentUUID'],[('u2',)])
        self.assertFalse(native_mapping(self.before,self.rule)[0])
        self.before.pop('other');self.before['djmdContent'][1][1]=('2','u2','C:/b.mp3','Remix')
        self.assertFalse(native_mapping(self.before,self.rule)[0])

    def test_remap_preserves_membership_order_and_history(self):
        after=copy.deepcopy(self.before);after['djmdContent'][1].pop()
        after['djmdSongPlaylist'][1][0]=('m','1','p',3);after['djmdSongHistory'][1][0]=('h','1')
        verify_changes(self.before,after,{'2':'1'})
        after['djmdSongPlaylist'][1][0]=('m','1','p',4)
        with self.assertRaises(PlanningError):verify_changes(self.before,after,{'2':'1'})

    def test_distinct_native_analysis_is_protected_even_with_identical_audio(self):
        cols,rows=self.before['djmdContent']
        self.before['djmdContent']=(cols+['AnalysisDataPath'],[rows[0]+('analysis-a',),rows[1]+('analysis-b',)])
        mapping,protected=native_mapping(self.before,self.rule)
        self.assertFalse(mapping);self.assertIn('ANLZ',protected[0]['reason'])


@unittest.skipUnless(os.name=='nt','Windows audio identity locks')
class AudioRecoveryTests(unittest.TestCase):
    def test_held_unicode_identity_moves_and_rolls_back_without_replacement(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'música 🎵.mp3';target=root/'recuperación 🎵.mp3';source.write_bytes(b'fixture audio')
            m={'audio_checks':{str(source):digest(source)},'audio_moves':[{'source':str(source),'target':str(target),'sha256':digest(source)}]}
            with AudioRecovery(m) as held:
                held.move();self.assertFalse(source.exists());self.assertTrue(target.exists())
                with self.assertRaises(OSError):target.read_bytes()
                held.rollback()
            self.assertEqual(source.read_bytes(),b'fixture audio');self.assertFalse(target.exists())
            target.write_bytes(b'occupied')
            with self.assertRaises(PlanningError):
                with AudioRecovery(m):pass
            self.assertEqual(target.read_bytes(),b'occupied')

    def test_crash_restore_plan_never_overwrites_recreated_original(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'a.mp3';target=root/'recovery.mp3';target.write_bytes(b'fixture')
            origin={'audio_moves':[{'source':str(source),'target':str(target),'sha256':digest(target)}]}
            checks,moves=restore_plan(origin);self.assertEqual(moves[0]['target'],str(source))
            source.write_bytes(b'new music')
            with self.assertRaises(PlanningError):restore_plan(origin)


try:
    import sqlcipher3
    import pyrekordbox
    HAVE_NATIVE=True
except ImportError:HAVE_NATIVE=False


@unittest.skipUnless(os.name=='nt' and HAVE_NATIVE,'Native encrypted Windows fixture')
class EncryptedDuplicateTests(unittest.TestCase):
    def setUp(self):
        from sqlalchemy import create_engine
        from pyrekordbox.db6 import tables
        from egobits.adapters.sqlcipher_read import driver_and_key
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.db=self.root/'master.db'
        driver,key=driver_and_key()
        def connect():
            conn=driver.connect(str(self.db));conn.execute("PRAGMA key='"+key.replace("'","''")+"'");return conn
        engine=create_engine('sqlite://',creator=connect)
        self.addCleanup(engine.dispose)
        # Upstream type annotations are stricter than the native SQLite schema;
        # optional native columns accept NULL. Keep actual PK constraints.
        nullable=[(c,c.nullable) for t in tables.Base.metadata.tables.values() for c in t.columns]
        try:
            for c,_ in nullable:
                if not c.primary_key:c.nullable=True
            tables.Base.metadata.create_all(engine)
        finally:
            for c,flag in nullable:c.nullable=flag
        self.a=self.root/'conservada.mp3';self.b=self.root/'duplicada.mp3'
        self.a.write_bytes(b'identical audio fixture');self.b.write_bytes(self.a.read_bytes())
        def values(table,**specified):
            for column in table.columns:
                if not column.nullable and column.default is None and column.name not in specified:
                    specified[column.name]=datetime.now() if 'datetime' in type(column.type).__name__.casefold() else 0 if column.type.python_type in (int,float) else ''
            return specified
        with engine.begin() as conn:
            conn.execute(tables.AgentRegistry.__table__.insert().values(**values(tables.AgentRegistry.__table__,registry_id='localUpdateCount',int_1=0)))
            for tid,p in [('1',self.a),('2',self.b)]:
                conn.execute(tables.DjmdContent.__table__.insert().values(**values(tables.DjmdContent.__table__,ID=tid,UUID='uuid'+tid,Title='Tema',FolderPath=str(p))))
        engine.dispose()
        (self.root/'masterPlaylists6.xml').write_text('<DJ_PLAYLISTS Version="1.0.0" AutomaticSync="0"><PRODUCT Version="7.2.19"/><PLAYLISTS/></DJ_PLAYLISTS>',encoding='utf-8')
        self.pid=patch('pyrekordbox.db6.database.get_rekordbox_pid',return_value=0);self.pid.start();self.addCleanup(self.pid.stop)
        native=pyrekordbox.Rekordbox6Database(path=self.db,db_dir=self.root)
        try:
            native.registry.clear_buffer()
            playlist=native.create_playlist('Fixture');native.add_to_playlist(playlist,'2');native.commit()
        finally:native.close();native.engine.dispose()
        xml=ET.Element('DJ_PLAYLISTS');coll=ET.SubElement(xml,'COLLECTION',Entries='2')
        for tid,p in [('1',self.a),('2',self.b)]:ET.SubElement(coll,'TRACK',TrackID=tid,Name='Tema',Artist='DJ',Location=p.as_uri().replace('file://','file://localhost',1))
        self.source=self.root/'source.xml';ET.ElementTree(xml).write(self.source,encoding='utf-8',xml_declaration=True)
        self.lib=Library(self.source);scan=DuplicateScan();data=scan.start(self.lib)
        deadline=time.monotonic()+5
        while scan.snapshot()['state']=='running' and time.monotonic()<deadline:time.sleep(.01)
        self.rule=scan.rule(self.lib,data['scan_id'],50)
        self.writer=NativePlaylistWriter(self.root/'ops',lambda:'closed',lambda:{'databases':[str(self.db)],'installations':[{'version':'7.2.19'}]})

    def test_encrypted_publication_and_joint_restoration(self):
        original=digest(self.db);xmlhash=digest(self.source)
        preview=prepare(self.writer,self.lib,self.rule,self.db)
        self.assertEqual(digest(self.db),original);self.assertTrue(self.b.exists())
        self.assertEqual(self.writer.approval_preview(preview['token'])['operation'],'consolidate_duplicates')
        result=self.writer.apply(preview['token'],self.lib.revision)
        self.assertEqual(result['state'],'applied');self.assertTrue(self.a.exists());self.assertFalse(self.b.exists())
        from egobits.adapters.sqlcipher_read import connection,inspect
        with connection(self.db) as conn:
            self.assertEqual(conn.execute('SELECT ID FROM djmdContent').fetchall(),[('1',)])
            self.assertEqual(conn.execute('SELECT ContentID FROM djmdSongPlaylist').fetchall(),[('1',)])
        self.assertEqual(inspect(self.db)['integrity'],'ok');self.assertEqual(digest(self.source),xmlhash)
        self.assertEqual(len(Library(Path(result['repaired_xml'])).tracks),1)
        recovery=self.writer.prepare_restore(preview['token']);self.writer.restore(recovery['token'])
        self.assertEqual(digest(self.db),original);self.assertTrue(self.b.exists());self.assertEqual(self.a.read_bytes(),self.b.read_bytes())

    def test_mid_publication_failure_restores_music_and_database(self):
        from egobits.adapters.windows_exclusive import WindowsExclusiveFiles
        original=digest(self.db);preview=prepare(self.writer,self.lib,self.rule,self.db)
        write=WindowsExclusiveFiles.write_from;failed=False
        def fail_once(held,name,source):
            nonlocal failed
            if Path(source).parent.name=='stage' and not failed:failed=True;raise OSError('fixture failure')
            return write(held,name,source)
        with patch.object(WindowsExclusiveFiles,'write_from',fail_once):
            with self.assertRaises(PlanningError):self.writer.apply(preview['token'],self.lib.revision)
        self.assertEqual(digest(self.db),original);self.assertTrue(self.b.exists())
        self.assertEqual(json.loads((self.writer.root/preview['token']/'journal.json').read_text())['state'],'rolled_back')

    def test_open_rekordbox_blocks_before_preparing(self):
        self.writer.process_state=lambda:'open'
        with self.assertRaises(PlanningError):prepare(self.writer,self.lib,self.rule,self.db)
        self.assertTrue(self.b.exists())

    def test_shared_file_consolidates_references_without_removing_music(self):
        from egobits.adapters.sqlcipher_read import connection
        with connection(self.db,readonly=False) as conn:
            conn.execute('UPDATE djmdContent SET FolderPath=? WHERE ID=?',(str(self.a),'2'));conn.commit()
        root=ET.parse(self.source)
        root.find('./COLLECTION/TRACK[@TrackID="2"]').set('Location',self.a.as_uri().replace('file://','file://localhost',1))
        root.write(self.source,encoding='utf-8',xml_declaration=True);lib=Library(self.source)
        scan=DuplicateScan();data=scan.start(lib)
        while scan.snapshot()['state']=='running':time.sleep(.01)
        preview=prepare(self.writer,lib,scan.rule(lib,data['scan_id'],50),self.db)
        self.assertEqual(preview['files'],0);self.writer.apply(preview['token'],lib.revision)
        self.assertTrue(self.a.exists())

    def test_audio_changed_after_preview_blocks_native_writes(self):
        original=digest(self.db);preview=prepare(self.writer,self.lib,self.rule,self.db)
        self.b.write_bytes(b'changed after review')
        with self.assertRaises(PlanningError):self.writer.apply(preview['token'],self.lib.revision)
        self.assertEqual(digest(self.db),original);self.assertTrue(self.b.exists())

    def test_recovery_survives_backend_restart(self):
        from egobits.adapters.native_write import save_journal
        original=digest(self.db);preview=prepare(self.writer,self.lib,self.rule,self.db)
        self.writer.apply(preview['token'],self.lib.revision)
        work=self.writer.root/preview['token'];manifest=json.loads((work/'journal.json').read_text());manifest['state']='publishing';save_journal(work,manifest)
        restarted=NativePlaylistWriter(self.writer.root,self.writer.process_state,self.writer.discover)
        with self.assertRaises(PlanningError):restarted.guard(self.db)
        restored=restarted.prepare_restore(preview['token']);restarted.restore(restored['token'])
        self.assertEqual(digest(self.db),original);self.assertTrue(self.b.exists());restarted.guard(self.db)

    def test_interrupted_truncated_database_recovers_verified_schema_and_music(self):
        from egobits.adapters.native_write import save_journal
        original=digest(self.db);preview=prepare(self.writer,self.lib,self.rule,self.db)
        self.writer.apply(preview['token'],self.lib.revision)
        work=self.writer.root/preview['token'];manifest=json.loads((work/'journal.json').read_text());manifest['state']='recovery_required';save_journal(work,manifest)
        self.db.write_bytes(b'power-loss fixture')
        restored=self.writer.prepare_restore(preview['token']);self.writer.restore(restored['token'])
        self.assertEqual(digest(self.db),original);self.assertTrue(self.b.exists())
