import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

INSTALLER = Path(__file__).resolve().parents[2] / 'installer'
sys.path.insert(0, str(INSTALLER))
import fetch_locked_assets as staging
sys.path.remove(str(INSTALLER))


class AssetStagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        cache = self.root / 'build/asset-cache'
        cache.mkdir(parents=True)
        archive = cache / 'runtime.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            output.writestr('server.exe', b'verified-binary')
        self.row = {'path': 'assets/bin/server.exe', 'archive_member': 'server.exe',
                    'download_id': 'runtime', 'size_bytes': 15,
                    'sha256': hashlib.sha256(b'verified-binary').hexdigest()}
        self.download = {'id': 'runtime', 'filename': 'runtime.zip', 'url': 'https://example.invalid/runtime.zip',
                         'size_bytes': archive.stat().st_size, 'sha256': staging.sha256(archive)}
        self.manifest = self.root / 'lock.json'
        self.manifest.write_text(json.dumps({'downloads': [self.download], 'assets': [self.row]}))
        for name, value in [('ROOT', self.root), ('MANIFEST', self.manifest), ('verify_assets', lambda: [])]:
            context = patch.object(staging, name, value)
            context.start()
            self.addCleanup(context.stop)

    def test_verified_archive_stages_exact_bytes(self):
        staging.prepare()
        self.assertEqual((self.root / self.row['path']).read_bytes(), b'verified-binary')

    def test_corrupt_cached_download_never_stages(self):
        (self.root / 'build/asset-cache/runtime.zip').write_bytes(b'corrupt')
        with self.assertRaises(ValueError):
            staging.prepare()
        self.assertFalse((self.root / self.row['path']).exists())

    def test_existing_corrupt_asset_is_preserved(self):
        target = self.root / self.row['path']
        target.parent.mkdir(parents=True)
        target.write_bytes(b'keep-evidence')
        with self.assertRaises(ValueError):
            staging.prepare()
        self.assertEqual(target.read_bytes(), b'keep-evidence')

    def test_archive_member_hash_must_match_before_publish(self):
        self.row['sha256'] = '0' * 64
        self.manifest.write_text(json.dumps({'downloads': [self.download], 'assets': [self.row]}))
        with self.assertRaises(ValueError):
            staging.prepare()
        self.assertFalse((self.root / self.row['path']).exists())
        self.assertFalse(list((self.root / 'assets').rglob('*.part')))

    def test_destination_escape_is_blocked(self):
        self.row['path'] = 'outside.exe'
        self.manifest.write_text(json.dumps({'downloads': [self.download], 'assets': [self.row]}))
        with self.assertRaises(ValueError):
            staging.prepare()
        self.assertFalse((self.root / 'outside.exe').exists())

    def test_unrelated_partial_file_is_preserved(self):
        target = self.root / self.row['path']
        target.parent.mkdir(parents=True)
        partial = target.with_suffix('.exe.part')
        partial.write_bytes(b'other-build')
        staging.prepare()
        self.assertEqual(partial.read_bytes(), b'other-build')

    def test_download_with_wrong_hash_is_not_published(self):
        source = self.root / 'build/asset-cache/runtime.zip'
        original = source.read_bytes()
        source.write_bytes(b'keep-original-evidence')
        response = io.BytesIO(b'x' * len(original))
        response.url = self.download['url']
        with patch.object(staging.urllib.request, 'urlopen', return_value=response):
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                staging.prepare(allow_download=True)
        self.assertEqual(source.read_bytes(), b'keep-original-evidence')
        self.assertFalse((self.root / self.row['path']).exists())

    def test_http_redirect_is_rejected(self):
        (self.root / 'build/asset-cache/runtime.zip').unlink()
        response = io.BytesIO(b'untrusted')
        response.url = 'http://example.invalid/runtime.zip'
        with patch.object(staging.urllib.request, 'urlopen', return_value=response):
            with self.assertRaisesRegex(ValueError, 'HTTPS'):
                staging.prepare(allow_download=True)
        self.assertFalse((self.root / self.row['path']).exists())
