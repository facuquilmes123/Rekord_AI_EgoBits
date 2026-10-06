import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('antivirus_gate', Path(__file__).resolve().parents[2] / 'installer/antivirus_gate.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class AntivirusGateTests(unittest.TestCase):
    def test_missing_payload_is_blocked_without_scan(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(gate.subprocess, 'run') as run:
            with self.assertRaises(RuntimeError):
                gate.scan_payload([Path(temp) / 'missing.exe'], Path(temp) / 'scan.log')
            run.assert_not_called()

    def test_detection_and_scan_error_both_block_release(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload = root / 'app.exe'; payload.write_bytes(b'inert test')
            scanner = root / 'Windows Defender/MpCmdRun.exe'
            scanner.parent.mkdir(); scanner.write_bytes(b'inert scanner')
            with patch.dict(gate.os.environ, {'ProgramData': temp, 'ProgramFiles': temp}):
                for code in (2, 5):
                    with self.subTest(code=code), patch.object(gate.subprocess, 'run', return_value=subprocess.CompletedProcess([], code)):
                        with self.assertRaises(RuntimeError):
                            gate.scan_payload([payload], root / 'scan.log')
                with patch.object(gate.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
                    self.assertEqual(gate.scan_payload([payload], root / 'scan.log'), 'HOST_DEFENDER_SCAN_PASSED')
                    args = run.call_args.args[0]
                    self.assertIn('-DisableRemediation', args)
                    self.assertEqual(args[args.index('-File') + 1], str(payload.resolve()))

    def test_payload_changed_during_scan_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload = root / 'app.exe'; payload.write_bytes(b'original')
            scanner = root / 'Windows Defender/MpCmdRun.exe'
            scanner.parent.mkdir(); scanner.write_bytes(b'inert scanner')
            def mutate(*args, **kwargs):
                payload.write_bytes(b'changed')
                return subprocess.CompletedProcess([], 0)
            with patch.dict(gate.os.environ, {'ProgramData': temp, 'ProgramFiles': temp}), patch.object(gate.subprocess, 'run', side_effect=mutate):
                with self.assertRaises(RuntimeError):
                    gate.scan_payload([payload], root / 'scan.log')
