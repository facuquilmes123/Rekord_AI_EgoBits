import hashlib
import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from egobits.adapters.xml_adapter import Library
from egobits.core.models import PlanningError
from egobits.desktop.duplicate_scan import DuplicateScan


class FullDuplicateScanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'colección.xml'
        self.scan = DuplicateScan()

    def library(self, specifications, playlists=None):
        root = ET.Element('DJ_PLAYLISTS')
        collection = ET.SubElement(root, 'COLLECTION')
        for tid, name, data, cue, filename in specifications:
            path = self.root / filename
            if data is not None: path.write_bytes(data)
            row = ET.SubElement(collection, 'TRACK', TrackID=tid, Name=name, Artist='DJ',
                                TotalTime='100', AverageBpm='124', Tonality='8A', Location=path.as_uri().replace('file:///', 'file://localhost/'))
            if cue is not None: ET.SubElement(row, 'POSITION_MARK', Start=str(cue), Name='Cue')
        if playlists:
            tree = ET.SubElement(root, 'PLAYLISTS')
            folder = ET.SubElement(tree, 'NODE', Name='ROOT', Type='0')
            for name, ids in playlists.items():
                node = ET.SubElement(folder, 'NODE', Name=name, Type='1', KeyType='0')
                for tid in ids: ET.SubElement(node, 'TRACK', Key=tid)
        ET.ElementTree(root).write(self.source, encoding='utf-8', xml_declaration=True)
        return Library(self.source)

    def complete(self, lib):
        self.scan.start(lib)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            result = self.scan.snapshot()
            if result['state'] != 'running': return result
            time.sleep(.01)
        self.fail('El análisis de la colección sintética no terminó.')

    def pair(self, name='Tema', cue=0):
        return self.library([('1', name, b'identical', cue, 'música á uno.mp3'),
                             ('2', name, b'identical', cue, 'música dos.mp3')])

    def test_every_file_hashed_even_without_shared_metadata(self):
        lib = self.library([('1', 'Uno', b'identical', 0, 'a.mp3'),
                            ('2', 'Otro nombre', b'identical', 0, 'b.mp3'),
                            ('3', 'Diferente', b'unique', 0, 'c.mp3')])
        before = self.source.read_bytes()
        data = self.complete(lib)
        self.assertEqual(data['processed'], 3)
        self.assertEqual(data['hashed_files'], 3)
        self.assertEqual(data['bytes_read'], len(b'identical') * 2 + len(b'unique'))
        self.assertEqual(data['groups'][0]['score'], 100)
        self.assertEqual(len(data['groups']), 1)
        self.assertEqual(self.source.read_bytes(), before)

    def test_similar_metadata_is_never_automatic_deletion(self):
        lib = self.library([('1', 'Tema', b'recording', 0, 'a.mp3'),
                            ('2', 'Tema', b'remixxxxx', 0, 'b.mp3')])
        result = self.complete(lib)
        self.assertEqual(result['groups'][0]['score'], 85)
        rule = self.scan.rule(lib, result['scan_id'], 50)
        self.assertEqual(rule['selected'], [])
        self.assertEqual(len(rule['protected']), 1)

    def test_different_cues_protected_even_at_one_hundred(self):
        lib = self.library([('1', 'Tema', b'identical', 0, 'a.mp3'),
                            ('2', 'Tema', b'identical', 10, 'b.mp3')])
        data = self.complete(lib)
        self.assertTrue(data['groups'][0]['different_cues'])
        rule = self.scan.rule(lib, data['scan_id'], 100)
        self.assertEqual(rule['selected'], [])
        self.assertEqual(len(rule['protected']), 1)

    def test_rule_preserves_most_used_keeper_and_all_files(self):
        lib = self.library([('1', 'Tema', b'identical', 0, 'a.mp3'),
                            ('2', 'Tema', b'identical', 0, 'b.mp3')], {'Set': ['2']})
        data = self.complete(lib)
        rule = self.scan.rule(lib, data['scan_id'], 100)
        self.assertEqual(rule['selected'][0]['keeper_id'], '2')
        self.assertEqual(rule['selected'][0]['id'], '1')
        self.assertEqual(rule['files'], 1)
        self.assertFalse(rule['delete_enabled'])
        self.assertEqual((self.root / 'a.mp3').read_bytes(), b'identical')
        self.assertEqual((self.root / 'b.mp3').read_bytes(), b'identical')

    def test_shared_reference_preserves_windows_file(self):
        lib = self.library([('1', 'Tema', b'identical', 0, 'shared.mp3'),
                            ('2', 'Tema', b'identical', 0, 'shared.mp3')])
        data = self.complete(lib)
        self.assertEqual(data['hashed_files'], 1)
        rule = self.scan.rule(lib, data['scan_id'], 100)
        self.assertEqual(rule['references'], 1)
        self.assertEqual(rule['files'], 0)

    def test_empty_metadata_does_not_group_unrelated_audio(self):
        lib = self.library([('1', '', b'one', 0, 'a.mp3'), ('2', '', b'two', 0, 'b.mp3')])
        self.assertEqual(self.complete(lib)['groups'], [])

    def test_unavailable_file_is_visible_and_not_selected(self):
        lib = self.library([('1', 'Tema', b'one', 0, 'a.mp3'), ('2', 'Tema', None, 0, 'missing.mp3')])
        data = self.complete(lib)
        self.assertEqual(data['processed'], 2)
        self.assertEqual(len(data['unavailable']), 1)
        self.assertEqual(self.scan.rule(lib, data['scan_id'], 0)['selected'], [])

    def test_thresholds_and_wrong_scan_rejected(self):
        lib = self.pair(); data = self.complete(lib)
        for value in (-1, 101, True, '100', float('nan'), float('inf'), None):
            with self.assertRaises(PlanningError): self.scan.rule(lib, data['scan_id'], value)
        with self.assertRaises(PlanningError): self.scan.rule(lib, 'wrong', 100)

    def test_source_and_music_changes_invalidate_rule(self):
        lib = self.pair(); data = self.complete(lib)
        (self.root / 'música dos.mp3').write_bytes(b'changed')
        with self.assertRaises(PlanningError): self.scan.rule(lib, data['scan_id'], 100)
        self.source.write_bytes(self.source.read_bytes() + b' ')
        with self.assertRaises(PlanningError): self.scan.rule(lib, data['scan_id'], 100)
        with self.assertRaises(PlanningError): self.scan.start(lib)

    def test_cancelled_job_cannot_generate_rule(self):
        lib = self.pair()
        with patch.object(threading.Thread, 'start'):
            running = self.scan.start(lib)
            with self.assertRaises(PlanningError): self.scan.start(lib)
            self.scan.cancel(running['scan_id'])
            self.scan._run(lib)
        self.assertEqual(self.scan.snapshot()['state'], 'cancelled')
        with self.assertRaises(PlanningError): self.scan.rule(lib, running['scan_id'], 100)

    def test_http_authenticated_scan_and_rule(self):
        from egobits.desktop import service
        lib = self.pair()
        with patch.object(service, '_DUPLICATES', self.scan), patch.object(service, '_GLOBAL_LIB', lib), patch.object(service, '_SESSION_TOKEN', 'test-session'):
            server = ThreadingHTTPServer(('127.0.0.1', 0), service.EgoBitsRequestHandler)
            worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
            def request(path, body=None, authorized=True):
                headers = {'Content-Type': 'application/json'}
                if authorized: headers['X-EgoBits-Token'] = 'test-session'
                req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}{path}',
                                             data=None if body is None else json.dumps(body).encode(), headers=headers)
                with urllib.request.urlopen(req, timeout=4) as response: return json.load(response)
            try:
                with self.assertRaises(urllib.error.HTTPError) as error: request('/api/duplicates/scan', authorized=False)
                self.assertEqual(error.exception.code, 403)
                started = request('/api/duplicates/scan/start', {'source_revision': lib.revision})
                deadline = time.monotonic() + 4
                while time.monotonic() < deadline:
                    data = request('/api/duplicates/scan')
                    if data['state'] != 'running': break
                    time.sleep(.01)
                self.assertEqual(data['state'], 'complete')
                rule = request('/api/duplicates/rule', {'scan_id': started['scan_id'], 'threshold': 100})
                self.assertEqual(rule['references'], 1)
                self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), lib.revision)
            finally:
                server.shutdown(); server.server_close(); worker.join(timeout=2)
