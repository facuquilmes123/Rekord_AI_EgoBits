"""Build deterministic ZIP from this kit, excluding transient Python artifacts."""
import hashlib
import sys
import zipfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
target=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else root.parent/'Rekord_AI_EgoBits_Investigacion_y_Kit_Codex.zip'
files=sorted(p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo'))
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in files:
        rel=Path(root.name)/p.relative_to(root)
        entry=zipfile.ZipInfo(rel.as_posix(),(2026,9,23,0,0,0))
        entry.compress_type=zipfile.ZIP_DEFLATED
        entry.external_attr=0o644<<16
        z.writestr(entry,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
with zipfile.ZipFile(target) as z:
    if z.testzip() is not None:raise RuntimeError('ZIP corrupto')
print(f'{target} | {len(files)} archivos | {target.stat().st_size} bytes | sha256={hashlib.sha256(target.read_bytes()).hexdigest()}')
