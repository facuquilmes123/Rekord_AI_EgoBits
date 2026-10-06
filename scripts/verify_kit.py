"""Verify upstream provenance and the prototype suite after extracting this ZIP."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'research/upstream_manifest.json').read_text(encoding='utf-8'))
for row in manifest:
    target=(root/row['local_path']).resolve()
    if not target.is_relative_to(root.resolve()):raise SystemExit('Ruta de manifiesto fuera del kit')
    if hashlib.sha256(target.read_bytes()).hexdigest()!=row['sha256']:
        raise SystemExit(f'Hash inválido: {target}')
print(f'{len(manifest)} archivos upstream verificados')
vendor=json.loads((root/'research/rekordbox-pdb.lock.json').read_text(encoding='utf-8'))
base=root/'prototype/egobits/vendor/rekordbox_pdb'
for name,expected in vendor['vendored_sha256'].items():
    target=(base/name).resolve()
    if not target.is_relative_to(base.resolve()) or hashlib.sha256(target.read_bytes()).hexdigest()!=expected:
        raise SystemExit('Hash de vendor inválido: '+name)
fixture=(root/vendor['fixture']['path']).resolve()
if not fixture.is_relative_to(root.resolve()) or hashlib.sha256(fixture.read_bytes()).hexdigest()!=vendor['fixture']['sha256']:
    raise SystemExit('Fixture DeviceSQL alterado')
print('Parser DeviceSQL y fixture verificados')
with tempfile.TemporaryDirectory(prefix='rekord-ai-tests-') as profile:
    environment={**os.environ,'LOCALAPPDATA':profile}
    for name in ('EGB_LIBRARY_XML','EGB_ENERGIES_JSON','EGB_SESSION_TOKEN','EGB_NATIVE_APPROVAL_KEY','EGB_RESOURCE_ROOT'):
        environment.pop(name,None)
    subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=root/'prototype',env=environment,check=True)
