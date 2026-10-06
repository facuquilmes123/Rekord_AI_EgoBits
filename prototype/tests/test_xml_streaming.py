import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from egobits.adapters import xml_adapter
from egobits.core.models import PlanningError


class StreamingXmlTests(unittest.TestCase):
    def test_xml_load_does_not_allocate_raw_file_copy(self):
        source=Path(__file__).resolve().parents[1]/'examples/library.xml'
        expected=hashlib.sha256(source.read_bytes()).hexdigest()
        with patch.object(Path,'read_bytes',side_effect=AssertionError('Must stream XML')):
            lib=xml_adapter.Library(source)
        self.assertEqual(lib.revision,expected);self.assertEqual(len(lib.tracks),6)
        self.assertIsNotNone(lib.nodes['1'].find('POSITION_MARK'))

    def test_limit_checked_before_opening(self):
        source=Path(__file__).resolve().parents[1]/'examples/library.xml'
        with patch.object(xml_adapter,'XML_LIMIT_BYTES',10,create=True),patch.object(Path,'open',side_effect=AssertionError('Must reject before read')):
            with self.assertRaises(PlanningError):xml_adapter.Library(source)

    def test_dtd_across_read_boundary_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'unsafe.xml'
            source.write_bytes(b' '*65533+b'<!DOCTYPE DJ_PLAYLISTS><DJ_PLAYLISTS/>')
            with self.assertRaisesRegex(PlanningError,'DTD'):xml_adapter.Library(source)
