import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import HTTPServer
from unittest.mock import Mock, patch
from egobits.desktop import service

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('release_contract',ROOT/'installer/release_contract.py')
contract=importlib.util.module_from_spec(spec);spec.loader.exec_module(contract)


class ReleaseTests(unittest.TestCase):
    def test_release_consistent_and_rejects_drift(self):
        self.assertEqual(contract.verify_release()['update_mode'],'manual_offline')
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)
            files=['release.json','desktop/src-tauri/tauri.conf.json','desktop/src-tauri/Cargo.toml','desktop/src-tauri/Cargo.lock','desktop/src-tauri/src/main.rs','prototype/pyproject.toml','prototype/egobits/desktop/service.py','prototype/egobits/adapters/xml_adapter.py','installer/egobits.iss']
            for file in files:
                dest=target/file;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/file,dest)
            self.assertEqual(contract.verify_release(target)['version'],contract.verify_release()['version'])
            release=target/'release.json';old=release.read_text();data=json.loads(old);data['version']='9.9.9';release.write_text(json.dumps(data))
            with self.assertRaises(ValueError):contract.verify_release(target)
            release.write_text(old);data=json.loads(old);data['app_id']='changed';release.write_text(json.dumps(data))
            with self.assertRaises(ValueError):contract.verify_release(target)


class ShutdownTests(unittest.TestCase):
    def test_shutdown_refuses_active_write_and_blocks_queued_new_writes(self):
        writer=Mock();writer.lock=threading.Lock();writer.stop_requested=threading.Event()
        actual=HTTPServer(('127.0.0.1',0),service.EgoBitsRequestHandler)
        worker=threading.Thread(target=actual.serve_forever,daemon=True);worker.start()
        url=f'http://127.0.0.1:{actual.server_port}'
        def post(path):return urllib.request.urlopen(urllib.request.Request(url+path,data=b'{}',headers={'X-EgoBits-Token':'qa-token','Content-Type':'application/json'}),timeout=2)
        try:
            with patch.object(service,'_NATIVE',writer),patch.object(service,'_SERVER',Mock()),patch.object(service,'_SESSION_TOKEN','qa-token'):
                writer.lock.acquire()
                try:
                    with self.assertRaises(urllib.error.HTTPError) as error:post('/api/shutdown')
                    self.assertEqual(error.exception.code,409);error.exception.close()
                    self.assertFalse(writer.stop_requested.is_set())
                finally:writer.lock.release()
                with post('/api/shutdown') as response:self.assertEqual(response.status,200)
                self.assertTrue(writer.stop_requested.is_set())
                with self.assertRaises(urllib.error.HTTPError) as error:post('/api/native/prepare')
                self.assertIn('cerrando',json.load(error.exception)['error']);error.exception.close()
                writer.prepare.assert_not_called()
        finally:
            actual.shutdown();actual.server_close();worker.join(timeout=2)
