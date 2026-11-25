import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import setup_ai  # noqa: E402
sys.path.remove(str(SCRIPTS))

from egobits.desktop import service  # noqa: E402


class AiCatalogAndSetupTests(unittest.TestCase):
    def test_catalog_has_valid_pinned_urls_and_hashes(self):
        catalog = setup_ai.load_catalog(ROOT / 'installer' / 'ai_catalog.json')
        model_ids = {m['id'] for m in catalog['models']}
        engine_ids = {e['id'] for e in catalog['engines']}
        self.assertEqual(model_ids, {'lite', 'compact', 'balanced', 'pro'})
        self.assertEqual(engine_ids, {'cpu', 'vulkan', 'cuda'})
        for entry in catalog['models'] + catalog['engines']:
            self.assertTrue(entry['url'].startswith('https://'))
            self.assertEqual(len(entry['sha256']), 64)
            self.assertGreater(entry['size_bytes'], 0)

    def test_recommend_profile_scales_with_ram(self):
        self.assertEqual(setup_ai.recommend_profile(4.0), 'lite')
        self.assertEqual(setup_ai.recommend_profile(6.0), 'compact')
        self.assertEqual(setup_ai.recommend_profile(8.0), 'balanced')
        self.assertEqual(setup_ai.recommend_profile(16.0), 'pro')

    def test_install_profile_verifies_and_resolves_in_service(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            (tmp / 'installer').mkdir()
            (tmp / 'assets' / 'models').mkdir(parents=True)
            (tmp / 'assets' / 'bin').mkdir(parents=True)

            # Build tiny synthetic engine zip and model bytes
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, 'w') as zf:
                zf.writestr('llama-server.exe', b'dummy-llama-server')
                zf.writestr('ggml.dll', b'dummy-ggml')
            zip_bytes = zip_buf.getvalue()
            model_bytes = b'dummy-qwen-0.8b-gguf'

            catalog = {
                'schema_version': 1,
                'models': [{
                    'id': 'lite',
                    'name': 'Test Lite',
                    'filename': 'test-lite.gguf',
                    'path': 'assets/models/test-lite.gguf',
                    'url': 'https://example.invalid/test-lite.gguf',
                    'sha256': hashlib.sha256(model_bytes).hexdigest(),
                    'size_bytes': len(model_bytes),
                    'min_ram_gb': 4,
                    'license': 'Apache-2.0',
                    'description': 'test',
                }],
                'engines': [{
                    'id': 'vulkan',
                    'name': 'Test Vulkan',
                    'filename': 'test-vulkan.zip',
                    'url': 'https://example.invalid/test-vulkan.zip',
                    'sha256': hashlib.sha256(zip_bytes).hexdigest(),
                    'size_bytes': len(zip_bytes),
                    'gpu_layers': 99,
                    'license': 'MIT',
                    'description': 'test',
                }],
            }
            cat_path = tmp / 'installer' / 'ai_catalog.json'
            cat_path.write_text(json.dumps(catalog), encoding='utf-8')

            def fake_urlopen(req, timeout=120):
                url = req.full_url if hasattr(req, 'full_url') else req
                data = zip_bytes if url.endswith('.zip') else model_bytes
                resp = io.BytesIO(data)
                resp.url = url
                resp.headers = {'Content-Length': str(len(data))}
                return resp

            with patch.object(setup_ai.urllib.request, 'urlopen', side_effect=fake_urlopen):
                active = setup_ai.install_profile('lite', 'vulkan', root=tmp, catalog_path=cat_path)

            self.assertTrue(active is not None and active.is_file())
            binary_path, model_path, _, model_sha, runtime_assets, gpu_layers = service.resolve_local_llama_spec(tmp)
            self.assertEqual(binary_path, tmp / 'assets/bin/llama-server.exe')
            self.assertEqual(model_path, tmp / 'assets/models/test-lite.gguf')
            self.assertEqual(model_sha, hashlib.sha256(model_bytes).hexdigest())
            self.assertEqual(gpu_layers, 99)
            self.assertEqual(len(runtime_assets), 2)


if __name__ == '__main__':
    unittest.main()
