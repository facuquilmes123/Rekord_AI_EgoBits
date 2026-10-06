import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from egobits.desktop import service
from egobits.desktop.settings import SettingsStore
from egobits.desktop.tray_watcher import ProcessMonitor


class SettingsApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = SettingsStore(Path(self.temp.name)/'settings.json')
        self.patches = [patch.object(service, '_SETTINGS', self.store),
                        patch.object(service, '_SESSION_TOKEN', 'local-test'),
                        patch.object(service, '_GLOBAL_LIB', None)]
        for item in self.patches: item.start()
        self.server = ThreadingHTTPServer(('127.0.0.1',0),service.EgoBitsRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2)
        for item in reversed(self.patches): item.stop()
        self.temp.cleanup()

    def post(self, path, data):
        request = urllib.request.Request(f'http://127.0.0.1:{self.server.server_port}'+path,
            data=json.dumps(data).encode(),headers={'Content-Type':'application/json','X-EgoBits-Token':'local-test'})
        try:
            with urllib.request.urlopen(request,timeout=4) as response:
                return response.status,json.load(response)
        except urllib.error.HTTPError as response:
            return response.code,json.load(response)

    def test_invalid_collection_preserves_selection_and_settings(self):
        old = service.get_or_load_library()
        code, body = self.post('/api/library', {'path':str(Path(self.temp.name)/'missing.xml')})
        self.assertEqual(code,400)
        self.assertIs(service._GLOBAL_LIB,old)
        self.assertFalse(self.store.path.exists())

    def test_array_body_and_unknown_setting_are_rejected(self):
        self.assertEqual(self.post('/api/settings',[])[0],400)
        self.assertEqual(self.post('/api/settings',{'shell':'cmd.exe'})[0],400)
        self.assertFalse(self.store.path.exists())

    def test_notification_update_is_persisted(self):
        code, body = self.post('/api/settings',{'notifications':{'silenced':True}})
        self.assertEqual(code,200)
        self.assertTrue(body['notifications']['silenced'])
        self.assertTrue(SettingsStore(self.store.path).snapshot()['notifications']['silenced'])

    def test_metadata_start_stops_audio_and_enables_one_click_popup(self):
        with patch.object(service._AUDIO_WATCH,'stop') as stop, patch.object(service,'recommendation_popup',return_value={'display':False,'reason':'Sin referencia'}):
            code,body=self.post('/api/history/start',{})
            self.assertEqual(code,200);stop.assert_called_once()
        prefs=self.store.snapshot()['notifications']
        self.assertTrue(prefs['enabled'] and prefs['history_popup'])
        self.assertFalse(prefs['silenced'])
        self.assertEqual(prefs['history_reference_mode'],'last_registered')


class WatcherEvidenceTests(unittest.TestCase):
    @patch('egobits.desktop.tray_watcher.sys.platform','win32')
    def test_invalid_tasklist_is_unknown(self):
        with patch.dict('sys.modules',{'psutil':None}), patch('subprocess.check_output', return_value='unexpected output'):
            self.assertEqual(ProcessMonitor().check_state(),'unknown')

    @patch('egobits.desktop.tray_watcher.sys.platform','win32')
    def test_only_exact_process_name_counts(self):
        with patch.dict('sys.modules',{'psutil':None}), patch('subprocess.check_output', return_value='"rekordbox.exe","123","Console"\n'):
            self.assertEqual(ProcessMonitor().check_state(),'open')
        with patch.dict('sys.modules',{'psutil':None}), patch('subprocess.check_output', return_value='"fake-rekordbox.exe","123","Console"\n'):
            self.assertEqual(ProcessMonitor().check_state(),'closed')
