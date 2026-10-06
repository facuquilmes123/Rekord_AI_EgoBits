import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from egobits.ai.verified_assets import VerifiedAssets
from egobits.ai.sidecar_client import LocalLlamaRuntime
from egobits.core.models import PlanningError


@unittest.skipUnless(os.name=='nt','Windows share protection')
class VerifiedAssetsTests(unittest.TestCase):
    def test_reuse_protects_bytes_and_rejects_new_expected_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'model.gguf';path.write_bytes(b'original')
            expected=hashlib.sha256(b'original').hexdigest();cache=VerifiedAssets()
            hasher=Mock(side_effect=LocalLlamaRuntime._hash)
            try:
                self.assertFalse(cache.verify(path,expected,hasher))
                self.assertTrue(cache.verify(path,expected,hasher))
                self.assertEqual(hasher.call_count,1)
                with self.assertRaises(OSError):path.write_bytes(b'modified')
                replacement=Path(folder)/'new.gguf';replacement.write_bytes(b'changed!')
                with self.assertRaises(OSError):os.replace(replacement,path)
                with self.assertRaises(PlanningError):cache.verify(path,'0'*64,hasher)
                with path.open('rb') as file:self.assertEqual(file.read(),b'original')
            finally:cache.close()
            path.write_bytes(b'modified')
            with self.assertRaises(PlanningError):cache.verify(path,expected,hasher)
            cache.close()
