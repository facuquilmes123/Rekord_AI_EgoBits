import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock
from egobits.adapters.native_write import NativePlaylistWriter
from egobits.adapters.xml_adapter import Library
from egobits.core.models import PlanningError
from egobits.telemetry.history import HistoryObserver

try:
    import numpy as np
except ImportError:
    np=None


class NativeGatesTests(unittest.TestCase):
    def test_open_unknown_cannot_prepare(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/'master.db';db.write_bytes(b'original')
            for state in ('open','unknown'):
                writer=NativePlaylistWriter(Path(folder)/'ops',lambda:state,lambda:{})
                with self.assertRaises(PlanningError): writer.prepare(None,[], 'x',db)
                self.assertEqual(db.read_bytes(),b'original')
            self.assertFalse((Path(folder)/'ops').exists())

    def test_publication_is_unavailable_even_with_token(self):
        writer=NativePlaylistWriter(Path('unused'),lambda:'closed',lambda:{})
        with self.assertRaises(PlanningError): writer.apply('any-token','revision')

    def test_journal_and_wal_block(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/'master.db';db.write_bytes(b'original')
            writer=NativePlaylistWriter(Path(folder)/'ops',lambda:'closed',lambda:{'databases':[str(db)],'installations':[{'version':'7.2.19'}]})
            Path(str(db)+'-wal').write_bytes(b'active')
            with self.assertRaises(PlanningError): writer.guard(db)


class HistoryTests(unittest.TestCase):
    def test_explicit_last_registered_reference_is_not_live_and_does_not_expire_as_audio(self):
        lib=Library(Path(__file__).resolve().parents[1]/'examples/library.xml')
        observer=HistoryObserver(lambda:{'databases':['test.db']},lambda:'open')
        fake=MagicMock();fake.__enter__.return_value=fake
        fake.execute.return_value.fetchall.return_value=[('old','1','t','C:/Music/Amanecer & Groove.mp3')]
        with patch('egobits.telemetry.history.connection',return_value=fake):
            result=observer.poll(lib,use_last_registered=True)
            self.assertTrue(result['recommendations']);self.assertFalse(result['confirmed'])
            self.assertEqual(result['reference_mode'],'last_registered')
            observer.changed_at-=600
            result=observer.poll(lib,use_last_registered=True)
            self.assertTrue(result['recommendations']);self.assertFalse(result['master_confirmed'])
            self.assertGreater(result['age_seconds'],599)

    def test_baseline_not_reported_and_new_history_never_master(self):
        lib=Library(Path(__file__).resolve().parents[1]/'examples/library.xml')
        observer=HistoryObserver(lambda:{'databases':['test.db']},lambda:'open')
        fake=MagicMock();fake.__enter__.return_value=fake
        fake.execute.return_value.fetchall.return_value=[('old','1','t','C:/Music/Amanecer & Groove.mp3')]
        with patch('egobits.telemetry.history.connection',return_value=fake):
            baseline=observer.poll(lib);self.assertFalse(baseline['recommendations']);self.assertTrue(baseline['connected'])
            fake.execute.return_value.fetchall.return_value=[('new','1','t2','C:/Music/Amanecer & Groove.mp3')]
            observer.last_poll=0;new=observer.poll(lib)
            self.assertTrue(new['recommendations']);self.assertFalse(new['confirmed']);self.assertFalse(new['master_confirmed'])


@unittest.skipIf(np is None,'Extra audio no instalado')
class AudioTests(unittest.TestCase):
    def setUp(self):
        from egobits.telemetry.audio_match import RATE
        self.rng=np.random.default_rng(84)
        self.audio=self.rng.normal(0,.1,RATE*12).astype(np.float32)

    def test_offset_match(self):
        from egobits.telemetry.audio_match import features,identify,HOP,RATE
        def signal():
            blocks=[]
            for _ in range(18):
                t=np.arange(HOP*8)/RATE
                frequencies=self.rng.uniform(120,4000,4)
                blocks.append(sum(np.sin(2*np.pi*f*t) for f in frequencies)*.08)
            return np.concatenate(blocks).astype(np.float32)
        a,b=signal(),signal()
        result=identify(a[HOP*20+HOP//3:HOP*20+HOP//3+RATE*6],{'a':features(a),'b':features(b)})
        self.assertTrue(result['matched']);self.assertEqual(result['track_id'],'a')
        self.assertFalse(result['master_confirmed']);self.assertFalse(result['confirmed'])

    def test_identical_candidates_are_ambiguous(self):
        from egobits.telemetry.audio_match import features,identify
        f=features(self.audio);result=identify(self.audio[:60000],{'a':f,'b':f})
        self.assertFalse(result['matched']);self.assertIsNone(result['track_id'])

    def test_silence_unknown_and_bad_input(self):
        from egobits.telemetry.audio_match import features,identify
        f=features(self.audio)
        self.assertFalse(identify(np.zeros(60000),{'a':f,'b':f})['matched'])
        with self.assertRaises(PlanningError): features(np.array([float('nan')]*2048))
