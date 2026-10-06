import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
from egobits.telemetry.audio_route import saved_route,probe_signal
from egobits.telemetry.audio_candidates import AudioCandidates
from egobits.adapters.xml_adapter import Library
from egobits.core.models import PlanningError


class AudioSetupTests(unittest.TestCase):
    def test_saved_route_only_suggests_unique_match_and_never_certifies(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)/'Pioneer/rekordbox6';base.mkdir(parents=True)
            (base/'rekordbox3.settings').write_text('<ROOT><VALUE name="audioDeviceManager"><DEVICESETUP audioOutputDeviceName="Realtek"/></VALUE></ROOT>')
            devices=[{'index':1,'name':'Realtek [Loopback]'}]
            result=saved_route(devices,folder)
            self.assertEqual(result['suggested_device_index'],1);self.assertFalse(result['master_confirmed'])
            self.assertIsNone(saved_route(devices+[{'index':2,'name':'Realtek [Loopback]'}],folder)['suggested_device_index'])

    def test_probe_requires_consent_before_any_capture(self):
        with patch('egobits.telemetry.audio_match.capture') as capture:
            with self.assertRaises(PlanningError):probe_signal(1,False)
            with self.assertRaises(PlanningError):probe_signal(True,True)
            capture.assert_not_called()

    def test_reference_candidates_use_history_but_never_mark_playback(self):
        lib=Library(Path(__file__).resolve().parents[1]/'examples/library.xml')
        fake=MagicMock();fake.__enter__.return_value=fake
        fake.execute.return_value.fetchall.return_value=[('C:/Music/Amanecer & Groove.mp3',)]
        with patch('egobits.telemetry.audio_candidates.connection',return_value=fake),patch('pathlib.Path.is_file',return_value=True):
            selector=AudioCandidates(lib,lambda:{'databases':['readonly.db']})
            ids=selector()
            self.assertEqual(ids[0],'1');self.assertGreaterEqual(len(ids),2);self.assertEqual(len(ids),len(set(ids)))
            self.assertTrue(set(ids)<=set(lib.tracks))
            self.assertTrue(fake.execute.call_args.args[0].startswith('SELECT'))
            from dataclasses import replace
            lib.tracks['duplicate']=replace(lib.tracks['1'],id='duplicate')
            with self.assertRaises(PlanningError):AudioCandidates(lib,lambda:{'databases':['readonly.db']})()

    def test_old_preferences_preserve_filters_and_reference_mode(self):
        from egobits.desktop.settings import SettingsStore,DEFAULTS
        import json
        data=json.loads(json.dumps(DEFAULTS));data['notifications'].pop('history_reference_mode');data['recommendation']['same_genre']=False
        for key in ('match_bpm','key_mode','min_duration_seconds'):data['recommendation'].pop(key)
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'settings.json';p.write_text(json.dumps(data))
            store=SettingsStore(p)
            self.assertIsNone(store.load_error);self.assertFalse(store.snapshot()['recommendation']['same_genre'])
            self.assertEqual(store.snapshot()['notifications']['history_reference_mode'],'new_entries')
            self.assertTrue(store.snapshot()['recommendation']['match_bpm']);self.assertEqual(json.loads(p.read_text()),data)
