import unittest
import tempfile
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from egobits.adapters import Library, export_xml, diff_libraries, create_verified_backup
from egobits.core import PlanOptions, plan, PlanningError

ROOT = Path(__file__).resolve().parents[1]

class XmlExtendedTests(unittest.TestCase):
    def setUp(self):
        self.lib = Library(ROOT / 'examples/library.xml')

    def test_diff_libraries(self):
        with tempfile.TemporaryDirectory() as td:
            # Crear un segundo XML con una modificación de BPM en Track 1
            src_bytes = self.lib.source.read_bytes()
            mod_bytes = src_bytes.replace(b'AverageBpm="124"', b'AverageBpm="124.5"')
            p2 = Path(td) / 'modified.xml'
            p2.write_bytes(mod_bytes)

            lib2 = Library(p2)
            diff = diff_libraries(self.lib, lib2)

            self.assertEqual(diff['added_count'], 0)
            self.assertEqual(diff['removed_count'], 0)
            self.assertEqual(diff['modified_count'], 1)
            self.assertEqual(diff['modified_tracks'][0]['id'], '1')
            self.assertEqual(diff['modified_tracks'][0]['changes']['bpm']['before'], 124.0)
            self.assertEqual(diff['modified_tracks'][0]['changes']['bpm']['after'], 124.5)

    def test_create_verified_backup_success(self):
        with tempfile.TemporaryDirectory() as td:
            db_file = Path(td) / 'master.db'
            db_file.write_bytes(b'SQLITE_HEADER_DUMMY_DATA_12345')
            backup_dir = Path(td) / 'backups'

            receipt = create_verified_backup(db_file, backup_dir)
            self.assertTrue(receipt.verified_restore)
            self.assertTrue(Path(receipt.backup_path).exists())
            self.assertEqual(receipt.sha256, hashlib.sha256(b'SQLITE_HEADER_DUMMY_DATA_12345').hexdigest())

    def test_create_verified_backup_fails_if_source_missing(self):
        with tempfile.TemporaryDirectory() as td:
            missing_file = Path(td) / 'nonexistent.db'
            backup_dir = Path(td) / 'backups'
            with self.assertRaises(PlanningError):
                create_verified_backup(missing_file, backup_dir)

    def test_xml_export_special_chars_and_beatgrid_preserved(self):
        r = plan(self.lib.pool(['ROOT/X', 'ROOT/Y']), PlanOptions(count=4))
        with tempfile.TemporaryDirectory() as td:
            out_target = Path(td) / 'set_special_chars.xml'
            export_xml(self.lib, r, 'Fiesta & Noche <Club> 100%', out_target)

            reloaded = Library(out_target)
            # Verificar preservación de TEMPO y POSITION_MARK de Track 1
            node_1 = reloaded.nodes['1']
            tempo_el = node_1.find('TEMPO')
            cue_el = node_1.find('POSITION_MARK')
            self.assertIsNotNone(tempo_el)
            self.assertIsNotNone(cue_el)
            self.assertEqual(tempo_el.get('Bpm'), '124')
            self.assertEqual(cue_el.get('Name'), 'Entrada')

    def test_unicode_metadata_and_location_are_bridge_uris(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / 'source.xml'
            root = ET.Element('DJ_PLAYLISTS', Version='1.0.0')
            ET.SubElement(root, 'PRODUCT', Name='Test', Version='1', Company='Test')
            collection = ET.SubElement(root, 'COLLECTION', Entries='1')
            track = ET.SubElement(collection, 'TRACK', TrackID='1', Name='Peña & 東京',
                                  Artist='Björk', Location='file://localhost/C:/Música/東京 & Peña.mp3')
            ET.SubElement(track, 'TEMPO', Inizio='0', Bpm='124')
            ET.SubElement(track, 'POSITION_MARK', Name='Entrada ñ', Type='0', Start='0')
            playlists = ET.SubElement(root, 'PLAYLISTS')
            node = ET.SubElement(playlists, 'NODE', Type='1', Name='Origen', KeyType='0', Entries='1')
            ET.SubElement(node, 'TRACK', Key='1')
            source.write_bytes(ET.tostring(root, encoding='utf-8', xml_declaration=True))
            original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            exported = Path(td) / 'salida.xml'
            export_xml(Library(source), {'track_ids': ['1']}, 'Noche & Peña 東京', exported)
            reloaded = Library(exported)
            self.assertEqual(reloaded.nodes['1'].get('Name'), 'Peña & 東京')
            self.assertEqual(reloaded.nodes['1'].get('Artist'), 'Björk')
            self.assertEqual(reloaded.nodes['1'].get('Location'),
                             'file://localhost/C:/M%C3%BAsica/%E6%9D%B1%E4%BA%AC%20%26%20Pe%C3%B1a.mp3')
            self.assertEqual(reloaded.nodes['1'].find('POSITION_MARK').get('Name'), 'Entrada ñ')
            self.assertEqual(reloaded.nodes['1'].find('TEMPO').get('Bpm'), '124')
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)

if __name__ == '__main__':
    unittest.main()
