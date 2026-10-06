"""Inventario conservador: dependencias resueltas, no una afirmación de enlace final."""
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys
from build_offline_bundle import ROOT, sha256


def main():
    destination = ROOT / 'assets/licenses/dependencies'
    destination.mkdir(parents=True, exist_ok=True)
    rows = []

    def copy(source, relative):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        return {'path': target.relative_to(ROOT).as_posix(), 'sha256': sha256(target)}

    data = (ROOT / 'output/closure/cargo-metadata.json').read_bytes()
    metadata = json.loads(data.decode('utf-16' if data.startswith(b'\xff\xfe') else 'utf-8-sig'))
    for package in metadata['packages']:
        if package['source'] is None:
            continue
        directory = Path(package['manifest_path']).parent
        name = package['name'] + '-' + package['version']
        notices = []
        for path in directory.rglob('*'):
            if path.is_file() and len(path.relative_to(directory).parts) <= 3 and path.name.lower().startswith(('license', 'licence', 'copying', 'notice', 'copyright')):
                notices.append(copy(path, Path('cargo') / name / path.relative_to(directory)))
        rows.append({'ecosystem': 'cargo', 'name': package['name'], 'version': package['version'],
                     'license': package['license'], 'source': package['source'],
                     'repository': package['repository'], 'scope': 'resolved; includes build and non-Windows dependencies',
                     'notices': notices})
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata['Name']
        notices = []
        for file in distribution.files or []:
            path = distribution.locate_file(file)
            if path.is_file() and path.name.lower().startswith(('license', 'licence', 'copying', 'notice', 'copyright')):
                notices.append(copy(path, Path('python-build') / (name + '-' + distribution.version) / path.name))
        rows.append({'ecosystem': 'python-build', 'name': name, 'version': distribution.version,
                     'license': distribution.metadata.get('License-Expression') or distribution.metadata.get('License'),
                     'scope': 'build environment; PyInstaller bootloader redistributed', 'notices': notices})
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    rows.append({'ecosystem': 'runtime', 'name': 'CPython', 'version': sys.version.split()[0],
                 'license': 'PSF-2.0 and bundled third-party notices',
                 'notices': [copy(python_license, Path('CPython/LICENSE.txt'))]})
    rows.extend(json.loads((ROOT / 'installer/offline_assets.json').read_text(encoding='utf-8'))['assets'])
    rows.append({'ecosystem': 'installer', 'name': 'Microsoft WebView2 standalone x64',
                 **json.loads((ROOT / 'installer/webview2.lock.json').read_text(encoding='utf-8'))})
    report = {'scope': 'Conservative inventory; native shell has not been linked. Runtime and build components are distinguished.',
              'components': rows}
    (ROOT / 'assets/licenses/THIRD_PARTY_INVENTORY.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    missing = [r['name'] for r in rows if r.get('ecosystem') == 'cargo' and not r['notices']]
    print(json.dumps({'components': len(rows), 'cargo_without_embedded_notice': missing}))


if __name__ == '__main__':
    main()
