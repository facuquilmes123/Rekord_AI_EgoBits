import os
from pathlib import Path
import shutil
import tempfile
import unittest
from egobits.adapters.device_library import DeviceLibrary,UsbExports,PDB,contained
from egobits.core.models import PlanningError


class DeviceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.usb=self.root/'usb';p=self.usb/PDB;p.parent.mkdir(parents=True)
        shutil.copy2(Path(__file__).parent/'fixtures/devicesql-export.pdb',p)

    def test_read_and_path_escape_protection(self):
        lib=DeviceLibrary(self.usb);report=lib.inspect()
        self.assertGreater(report['total_tracks'],0);self.assertEqual(report['orphan_count'],0)
        self.assertFalse(report['tracks'][0]['file_available'])
        with self.assertRaises(PlanningError):contained(self.usb,'/../outside.wav')
        with self.assertRaises(PlanningError):contained(self.usb,'C:/outside.wav')

    @unittest.skipUnless(os.name=='nt','Native exclusive publish requires Windows')
    def test_prepare_apply_preserves_tracks_and_verified_backup(self):
        lib=DeviceLibrary(self.usb);track=lib.db.tracks[0]
        for rel in (track.file_path,track.analyze_path):
            self.assertTrue(rel);p=contained(self.usb,rel);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'fixture-present')
        before=(self.usb/PDB).read_bytes();manager=UsbExports(self.root/'backups',lambda:'closed')
        device=manager.register(self.usb);preview=manager.prepare(device['device_id'],'Test set',[str(track.id)])
        self.assertEqual((self.usb/PDB).read_bytes(),before)
        result=manager.apply(preview['token']);self.assertEqual(result['state'],'applied')
        after=DeviceLibrary(self.usb);self.assertEqual(len(after.db.tracks),len(lib.db.tracks))
        self.assertTrue(any(p.name=='Test set' for p in after.db.playlist_tree))
        self.assertEqual((Path(result['backup_directory'])/'original.pdb').read_bytes(),before)
        with self.assertRaises(PlanningError):manager.apply(preview['token'])
        restore=manager.prepare_restore(preview['token']);self.assertEqual(restore['operation'],'usb_restore')
        manager.apply(restore['token']);self.assertEqual((self.usb/PDB).read_bytes(),before)

    def test_open_rekordbox_and_tampered_proposal_blocked(self):
        manager=UsbExports(self.root/'backups',lambda:'open');d=manager.register(self.usb)
        with self.assertRaises(PlanningError):manager.prepare(d['device_id'],'Set',['1'])

    def test_cyclic_pages_rejected(self):
        import struct
        original=bytearray((self.usb/PDB).read_bytes());lib=DeviceLibrary(self.usb)
        table=next(t for t in lib.db.tables if t.first_page!=t.last_page)
        struct.pack_into('<I',original,table.first_page*lib.db.page_size+12,table.first_page)
        (self.usb/PDB).write_bytes(original)
        with self.assertRaises(PlanningError):DeviceLibrary(self.usb)

    @unittest.skipUnless(os.name=='nt','Windows exclusive writer')
    def test_new_track_exports_audio_and_preserves_unknown_analysis(self):
        try:import av
        except ImportError:self.skipTest('PyAV required')
        import wave,struct
        from dataclasses import replace
        from egobits.adapters.xml_adapter import Library
        from egobits.adapters.anlz_relocate import tags
        audio=self.root/'source.wav'
        with wave.open(str(audio),'wb') as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(48000);wav.writeframes(bytes(96000))
        encoded='/source.wav'.encode('utf-16-be')+b'\0\0'
        pp=b'PPTH'+struct.pack('>III',16,16+len(encoded),len(encoded))+encoded
        unknown=b'PVB2'+struct.pack('>II',12,16)+b'abcd'
        raw=b'PMAI'+struct.pack('>II',28,28+len(pp)+len(unknown))+bytes(16)+pp+unknown
        anlz=self.root/'ANLZ0000.DAT';anlz.write_bytes(raw)
        lib=Library(Path(__file__).parents[1]/'examples/library.xml');tid=next(iter(lib.tracks))
        lib.tracks[tid]=replace(lib.tracks[tid],location=audio.as_uri().replace('file:///','file://localhost/'),duration=1)
        lib.native_metadata={tid:{'analysis_path':str(anlz)}}
        manager=UsbExports(self.root/'backups',lambda:'closed');device=manager.register(self.usb)
        preview=manager.prepare(device['device_id'],'New audio',lib=lib,track_ids=[tid]);manager.apply(preview['token'])
        exported=DeviceLibrary(self.usb);track=next(t for t in exported.db.tracks if 'RekordAI-' in t.file_path)
        self.assertEqual(contained(self.usb,track.file_path).read_bytes(),audio.read_bytes())
        moved=contained(self.usb,track.analyze_path).read_bytes();self.assertEqual(tags(moved)[1][-1][1],unknown)
        self.assertIn(track.file_path.encode('utf-16-be'),moved);self.assertEqual(track.sample_rate,48000)
