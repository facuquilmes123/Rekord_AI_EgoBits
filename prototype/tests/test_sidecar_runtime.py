import hashlib
import tempfile
import unittest
from pathlib import Path

from egobits.ai.sidecar_client import LlamaSidecarClient, LocalLlamaRuntime
from egobits.core.models import PlanningError


class SidecarRuntimeTests(unittest.TestCase):
    def test_non_loopback_endpoint_rejected(self):
        with self.assertRaises(ValueError):
            LlamaSidecarClient(host='0.0.0.0')

    def test_modified_model_prevents_process_start(self):
        with tempfile.TemporaryDirectory() as td:
            binary = Path(td) / 'llama-server.exe'
            model = Path(td) / 'model.gguf'
            binary.write_bytes(b'fake binary')
            model.write_bytes(b'changed model')
            binary_hash = hashlib.sha256(binary.read_bytes()).hexdigest()
            expected_model_hash = hashlib.sha256(b'original model').hexdigest()
            runtime = LocalLlamaRuntime(binary, model, binary_hash, expected_model_hash)
            with self.assertRaises(PlanningError):
                runtime.start(wait_seconds=0.1)
            self.assertIsNone(runtime.process)

