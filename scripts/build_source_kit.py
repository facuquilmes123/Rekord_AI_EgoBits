"""ZIP fuente reproducible y opcional ZIP64 con activos offline. No descarga nada."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'.git', '.venv', '__pycache__', 'node_modules', 'target', 'build', 'dist', '.pytest_cache', '.playwright-cli', 'output'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--include-assets', action='store_true')
    args = parser.parse_args()
    if args.include_assets:
        import subprocess, sys
        subprocess.run([sys.executable, str(ROOT/'installer/build_offline_bundle.py')], check=True)
    output = ROOT/'dist'
    output.mkdir(exist_ok=True)
    archive = output/('Rekord_AI_EgoBits_offline_source.zip' if args.include_assets else 'Rekord_AI_EgoBits_source.zip')
    hashes = {}
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as bundle:
        for path in sorted(ROOT.rglob('*')):
            relative = path.relative_to(ROOT)
            if not path.is_file() or path.is_symlink() or set(relative.parts) & EXCLUDED:
                continue
            if relative.as_posix().startswith('research/downloads/') or path.suffix in ('.pyc','.log'):
                continue
            if relative.parts[0] == 'assets' and relative.parts[1] in ('models','bin') and not args.include_assets:
                continue
            if path.name.startswith('.env') or path.suffix.lower() in ('.zip','.msi'):
                continue
            digest = hashlib.sha256()
            entry = zipfile.ZipInfo(relative.as_posix())
            entry.compress_type = zipfile.ZIP_STORED if path.suffix.lower() == '.gguf' else zipfile.ZIP_DEFLATED
            with path.open('rb') as source, bundle.open(entry, 'w', force_zip64=True) as target:
                for chunk in iter(lambda: source.read(1024*1024), b''):
                    digest.update(chunk)
                    target.write(chunk)
            hashes[relative.as_posix()] = digest.hexdigest()
        bundle.writestr('SOURCE_SHA256.json', json.dumps(hashes, indent=2))
    with archive.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n', encoding='ascii')
    print(f'{archive.name}: {len(hashes)} archivos; SHA-256 {digest}')


if __name__ == '__main__':
    main()
