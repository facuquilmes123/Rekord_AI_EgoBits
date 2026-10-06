"""Verify upstream provenance and the prototype suite after extracting this ZIP."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'research/upstream_manifest.json').read_text(encoding='utf-8'))
for row in manifest:
    target=(root/row['local_path']).resolve()
    if not target.is_relative_to(root.resolve()):raise SystemExit('Ruta de manifiesto fuera del kit')
    if hashlib.sha256(target.read_bytes()).hexdigest()!=row['sha256']:
        raise SystemExit(f'Hash inválido: {target}')
print(f'{len(manifest)} archivos upstream verificados')
subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=root/'prototype',check=True)
