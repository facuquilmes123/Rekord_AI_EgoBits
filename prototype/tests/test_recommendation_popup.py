import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
import xml.etree.ElementTree as ET
from egobits.adapters.xml_adapter import Library
from egobits.core.models import PlanningError
from egobits.desktop.track_handoff import drag_file
from egobits.desktop.settings import SettingsStore, DEFAULTS
from egobits.desktop import service
from egobits.telemetry.audio_watch import AudioWatch


class RecommendationPopupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        xml=ET.Element('DJ_PLAYLISTS');collection=ET.SubElement(xml,'COLLECTION')
        for i in ('1','2','3'):
            path=self.root/f'tema á {i}.mp3';path.write_bytes(b'fixture')
            ET.SubElement(collection,'TRACK',TrackID=i,Name=f'Tema {i}',Artist=f'Artista {i}',AverageBpm='124',Tonality='8A',Genre='House',Location=path.as_uri().replace('file:///','file://localhost/'))
        self.source=self.root/'colección.xml';ET.ElementTree(xml).write(self.source,encoding='utf-8')
        self.lib=Library(self.source);self.store=SettingsStore(self.root/'settings.json')
        self.store.update({'notifications':{'enabled':True,'history_popup':True}})
        self.history={'source':'rekordbox_history','confirmed':False,'history_event_id':'new',
                      'recommendations':[vars(self.lib.tracks['2'])],'reason':'Historial'}
        self.patches=[patch.object(service,'_SETTINGS',self.store),patch.object(service,'current_library',return_value=(self.lib,None)),
                      patch.object(service._MONITOR,'check_state',return_value='open'),patch.object(service._HISTORY,'poll',return_value=self.history),
                      patch.object(service,'_LIVE_PROVIDER',None),patch.object(service._AUDIO_WATCH,'snapshot',return_value={})]
        for p in self.patches:p.start()

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def test_history_popup_is_explicitly_unconfirmed_and_local(self):
        result=service.recommendation_popup()
        self.assertTrue(result['display']);self.assertFalse(result['confirmed'])
        self.assertEqual(result['source'],'rekordbox_history')
        self.assertEqual(result['recommendations'][0]['id'],'2')
        self.assertNotIn('location',result['recommendations'][0])

    def test_filter_or_candidate_change_creates_new_delivery_event(self):
        first=service.recommendation_popup()['event_id']
        self.assertEqual(service.recommendation_popup()['event_id'],first)
        self.store.update({'recommendation':{'max_bpm_delta':1}})
        second=service.recommendation_popup()['event_id']
        self.assertNotEqual(first,second)
        self.history['recommendations']=[vars(self.lib.tracks['3'])]
        self.assertNotEqual(service.recommendation_popup()['event_id'],second)

    def test_disabled_muted_closed_or_missing_candidate_suppresses_popup(self):
        for changes in ({'enabled':False},{'enabled':True,'silenced':True},{'enabled':True,'silenced':False,'history_popup':False}):
            self.store.update({'notifications':changes});self.assertFalse(service.recommendation_popup()['display'])
        self.store.update({'notifications':{'history_popup':True}})
        with patch.object(service._MONITOR,'check_state',return_value='unknown'):
            self.assertFalse(service.recommendation_popup()['display'])
        (self.root/'tema á 2.mp3').unlink()
        self.assertFalse(service.recommendation_popup()['display'])

    def test_audio_popup_requires_stability_freshness_and_same_collection(self):
        self.store.update({'notifications':{'history_popup':False}})
        audio={'popup_eligible':True,'source_revision':self.lib.revision,'track_id':'1'}
        with patch.object(service._AUDIO_WATCH,'snapshot',return_value=audio):
            result=service.recommendation_popup();self.assertTrue(result['display']);self.assertFalse(result['confirmed'])
        for bad in ({**audio,'popup_eligible':False},{**audio,'source_revision':'stale'}):
            with patch.object(service._AUDIO_WATCH,'snapshot',return_value=bad):self.assertFalse(service.recommendation_popup()['display'])

    def test_drag_resolves_unicode_id_and_rejects_stale_missing_unknown_or_non_audio(self):
        self.assertEqual(Path(drag_file(self.lib,'2',self.lib.revision)['path']).name,'tema á 2.mp3')
        for tid,revision in (('999',self.lib.revision),('2','stale')):
            with self.assertRaises(PlanningError):drag_file(self.lib,tid,revision)
        self.source.write_bytes(self.source.read_bytes()+b' ')
        with self.assertRaises(PlanningError):drag_file(self.lib,'2',self.lib.revision)

    def test_chat_returns_metadata_recommendations_without_claiming_master(self):
        from egobits.desktop.chat import execute_chat
        from egobits.ai.intents import RecommendLiveIntent
        live={**self.history,'reference_track':vars(self.lib.tracks['1']),'master_confirmed':False}
        result=execute_chat(RecommendLiveIntent(),self.lib,'open',live=live)
        self.assertEqual(result['recommendations'][0]['id'],'2')
        self.assertIn('No confirma la pista audible actual',result['response'])
        self.assertFalse(result['live']['confirmed'])
        self.assertEqual(result['context_reference']['track_id'],'1')

    def test_old_notification_settings_load_without_losing_preferences(self):
        old=json.loads(json.dumps(DEFAULTS));old['notifications'].pop('history_popup');old['notifications']['silenced']=True
        path=self.root/'old.json';path.write_text(json.dumps(old),encoding='utf-8')
        store=SettingsStore(path);self.assertIsNone(store.load_error)
        self.assertTrue(store.snapshot()['notifications']['silenced']);self.assertFalse(store.snapshot()['notifications']['history_popup'])
        self.assertNotIn('history_popup',json.loads(path.read_text())['notifications'])

    def test_audio_watch_rejects_missing_consent_or_bad_device_without_capture(self):
        watcher=AudioWatch()
        with patch('egobits.telemetry.audio_watch.audio_match.devices',return_value=[{'index':7}]):
            for args in ((['1','2'],7,False),(['1'],7,True),(['1','2'],0,True)):
                with self.assertRaises(PlanningError):watcher.start(self.lib,*args)
        self.assertFalse(watcher.snapshot()['active'])

    def test_stale_silence_and_stop_never_qualify_audio_popup(self):
        watcher=AudioWatch()
        with patch('egobits.telemetry.audio_watch.time.time',return_value=100):
            watcher.state.update(active=True,stable=True,matched=True,observed_at=98,allow_popup=True)
            self.assertTrue(watcher.snapshot()['popup_eligible'])
            watcher.state['observed_at']=94;self.assertFalse(watcher.snapshot()['popup_eligible'])
            watcher.state.update(observed_at=99,matched=False);self.assertFalse(watcher.snapshot()['popup_eligible'])
            watcher.stop();self.assertFalse(watcher.snapshot()['popup_eligible'])

    def test_continuous_capture_requires_two_matches_then_clears_on_silence(self):
        from types import SimpleNamespace
        watcher=AudioWatch();watcher.state.update(active=True,allow_popup=True)
        snapshots=[]
        def capture(*args,**kwargs):
            snapshots.append(watcher.snapshot())
            if len(snapshots)==4:watcher.stop_event.set()
            return []
        matches=[{'matched':True,'track_id':'1','reason':'match'}, {'matched':True,'track_id':'1','reason':'match'},
                 {'matched':False,'track_id':None,'reason':'Silencio'}, {'matched':False,'reason':'Silencio'}]
        with patch('egobits.telemetry.audio_watch.audio_match.decode',return_value=[]),\
             patch('egobits.telemetry.audio_watch.audio_match.features',return_value=SimpleNamespace(nbytes=256)),\
             patch('egobits.telemetry.audio_watch.audio_match.capture',side_effect=capture),\
             patch('egobits.telemetry.audio_watch.audio_match.identify',side_effect=matches),\
             patch.object(watcher.stop_event,'wait',return_value=False):
            watcher._run({'1':self.root/'a','2':self.root/'b'},0,watcher.stop_event)
        self.assertFalse(snapshots[1]['popup_eligible'])
        self.assertTrue(snapshots[2]['popup_eligible'])
        self.assertFalse(snapshots[3]['popup_eligible'])
        self.assertFalse(watcher.snapshot()['active'])

    def test_confirmed_source_retains_confirmed_status(self):
        with patch.object(service,'live_suggestion',return_value={'confirmed':True,'event_id':'verified','track_id':'2'}):
            result=service.recommendation_popup();self.assertTrue(result['display']);self.assertTrue(result['confirmed'])

    def test_audio_capture_stops_if_rekordbox_is_not_known_open(self):
        from types import SimpleNamespace
        watcher=AudioWatch(lambda:'unknown');watcher.state.update(active=True)
        with patch('egobits.telemetry.audio_watch.audio_match.decode',return_value=[]),\
             patch('egobits.telemetry.audio_watch.audio_match.features',return_value=SimpleNamespace(nbytes=256)),\
             patch('egobits.telemetry.audio_watch.audio_match.capture') as capture:
            watcher._run({'1':self.root/'a','2':self.root/'b'},0,watcher.stop_event)
            capture.assert_not_called()
        self.assertFalse(watcher.snapshot()['active'])

if __name__=='__main__':unittest.main()
