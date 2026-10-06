"""Bundle the real backend and offline assets for isolated QA, not an installer."""
import json
from pathlib import Path
import zipfile
from build_offline_bundle import ROOT, sha256, verify_assets


def main():
    errors = verify_assets()
    if errors: raise SystemExit('\n'.join(errors))
    backend = ROOT / 'build/backend/egobits-backend.exe'
    if not backend.is_file(): raise SystemExit('Backend real ausente')
    smoke = json.loads((ROOT / 'output/closure/frozen-smoke.json').read_text())
    if smoke['sha256'] != sha256(backend) or not all(smoke['checks'].values()):
        raise SystemExit('El backend actual no coincide con un smoke aprobado')
    files = [(backend, 'egobits-backend.exe')]
    files += [(p, p.relative_to(ROOT).as_posix()) for p in (ROOT / 'assets').rglob('*') if p.is_file() and p.name != '.gitkeep']
    files += [(p, 'fixture/' + p.name) for p in (ROOT / 'output/closure/bridge-fixture-v2').iterdir() if p.is_file()]
    for name in ('offline_assets.json', 'test_bridge_fixture.ps1', 'test_portable_backend.ps1', 'prepare_sandbox.ps1'):
        files.append((ROOT / 'installer' / name, 'installer/' + name))
    for name in ('MATRIZ_CIERRE.md', 'PROTOCOLO_WINDOWS_REKORDBOX.md', 'INVESTIGACION_ACTUALIZACION.md'):
        files.append((ROOT / 'docs' / name, 'docs/' + name))
    for name in ('frozen-smoke.json', 'powershell-smoke.json', 'backend-build.json', 'backend-components.json',
                 'verify-kit.log', 'offline-preflight.log', 'tauri-nsis.log'):
        files.append((ROOT / 'output/closure' / name, 'evidence/' + name))
    target = ROOT / 'dist/Rekord_AI_EgoBits_backend_QA_offline.zip'
    hashes = {}
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for path, name in files:
            archive.write(path, name)
            hashes[name] = sha256(path)
        archive.writestr('SHA256.json', json.dumps(hashes, indent=2))
        archive.writestr('LEEME.txt', 'KIT DE QA DEL BACKEND. No es un instalador ni la app Tauri.\n'
            'Extraer completo. Ver docs/PROTOCOLO_WINDOWS_REKORDBOX.md.\n'
            'No modificar la coleccion personal. Ejecutar pruebas en VM/cuenta de ensayo.\n'
            'PowerShell: powershell -NoProfile -File installer/test_portable_backend.ps1 -Backend ./egobits-backend.exe -ResourceRoot .\n'
            'XML: powershell -NoProfile -File installer/test_bridge_fixture.ps1 -Backend ./egobits-backend.exe -Fixture ./fixture\n')
    # Verify all recorded member hashes without extracting over any existing file.
    import hashlib
    with zipfile.ZipFile(target) as archive:
        for name, expected in hashes.items():
            with archive.open(name) as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                    raise SystemExit('ZIP alterado: ' + name)
    digest = sha256(target)
    target.with_suffix('.zip.sha256').write_text(digest + '  ' + target.name + '\n')
    report = {'artifact': str(target), 'size_bytes': target.stat().st_size, 'sha256': digest,
              'verified_members': len(hashes), 'type': 'backend QA kit, not installer'}
    (ROOT / 'output/closure/qa-package.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
