"""Entrega ZIP64: instalador MSI/NSIS, modelo y copiado local verificado."""
import hashlib
import json
from pathlib import Path
import zipfile
from build_offline_bundle import ROOT, verify_assets, verify_upstream


def main():
    errors = verify_assets() + verify_upstream()
    if errors:
        raise SystemExit('\n'.join(errors))
    bundles = ROOT/'desktop/src-tauri/target/x86_64-pc-windows-msvc/release/bundle'
    installers = list(bundles.glob('msi/*.msi')) + list(bundles.glob('nsis/*-setup.exe'))
    if not installers:
        raise SystemExit('No hay instaladores compilados; no se genera una entrega ficticia.')
    manifest = json.loads((ROOT/'installer/offline_assets.json').read_text(encoding='utf-8'))
    files = [(path, 'installers/'+path.name) for path in installers]
    files += [(ROOT/row['path'],row['path']) for row in manifest['assets'] if row['path'].endswith('.gguf')]
    files += [(path,path.relative_to(ROOT).as_posix()) for path in (ROOT/'assets/licenses').rglob('*') if path.is_file()]
    files += [(ROOT/name,name) for name in ('installer/offline_assets.json','installer/install_model.ps1','installer/register_autostart.ps1','installer/watch_rekordbox.ps1','docs/EMPAQUETADO_WINDOWS.md')]
    output=ROOT/'dist'; output.mkdir(exist_ok=True)
    target=output/'Rekord_AI_EgoBits_Windows_offline.zip'
    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_STORED,allowZip64=True) as archive:
        hashes={}
        for path,name in files:
            archive.write(path,name)
            with path.open('rb') as stream: hashes[name]=hashlib.file_digest(stream,'sha256').hexdigest()
        archive.writestr('SHA256.json',json.dumps(hashes,indent=2))
    print(f'Entrega creada: {target}')


if __name__=='__main__': main()
