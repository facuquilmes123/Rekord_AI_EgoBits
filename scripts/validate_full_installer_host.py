"""Install the real offline Setup on this host and verify preserved user files.

Explicit host repair validation; not isolated/clean-VM evidence. Does not launch
the app, close Rekordbox, modify its collection or remove user files.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import winreg

ROOT = Path(__file__).resolve().parents[1]
KEY = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{F57C7090-73DC-453B-96DF-8D9F3E215E10}_is1'


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as source:
        while chunk := source.read(1024 * 1024): result.update(chunk)
    return result.hexdigest()


def main():
    release = json.loads((ROOT / 'release.json').read_text())
    version = release['version']
    artifact = ROOT / f'dist/Rekord_AI_Setup_{version}_x64.exe'
    approved = json.loads((ROOT / 'output/closure/single-installer.json').read_text())
    if approved.get('version') != version or approved.get('installer_defender_scan') != 'HOST_DEFENDER_SCAN_PASSED' or digest(artifact) != approved['sha256']:
        raise SystemExit('No hay un artefacto con hash y análisis aprobados.')
    local = Path(os.environ['LOCALAPPDATA'])
    protected = [local / release['settings_folder'], local / release['native_backups_folder']]
    before = {p: digest(p) for folder in protected if folder.is_dir() for p in folder.rglob('*') if p.is_file()}
    output = ROOT / 'output/closure' / ('full-install-' + str(time.time_ns()))
    output.mkdir()
    report = {'scope': 'real_current_host_install_repair_and_same_version_reinstall',
              'version': version, 'clean_vm': False, 'internet_disabled': False,
              'real_rekordbox_closed': False, 'collection_write_executed': False,
              'protected_file_count': len(before), 'runs': []}
    report['protected_counts'] = {folder.name: sum(p.is_relative_to(folder) for p in before) for folder in protected}
    try:
        for label in ('repair', 'reinstall_upgrade'):
            result = subprocess.run([str(artifact), '/VERYSILENT', '/SUPPRESSMSGBOXES',
                                     '/NORESTART', '/LOG=' + str(output / (label + '.log'))], timeout=600)
            report['runs'].append({'kind': label, 'exit_code': result.returncode})
            if result.returncode: raise RuntimeError('Instalación rechazada; revisar log y Defender.')
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
                installed = winreg.QueryValueEx(key, 'InstallLocation')[0]
                installed_version = winreg.QueryValueEx(key, 'DisplayVersion')[0]
            folder = Path(installed)
            if installed_version != version: raise RuntimeError('Versión instalada incorrecta.')
            for name, key in [('egobits-desktop.exe', 'shell_sha256'), ('egobits-backend.exe', 'backend_sha256')]:
                if not (folder / name).is_file() or digest(folder / name) != approved[key]:
                    raise RuntimeError('Componente ausente o alterado después de instalar: ' + name)
            if any(not p.is_file() or digest(p) != checksum for p, checksum in before.items()):
                raise RuntimeError('Un archivo persistente cambió durante la instalación.')
            report.update(install_location=str(folder), executables_hash_verified=True,
                          existing_settings_and_backups_preserved=True)
        report['passed'] = True
    except Exception as exc:
        report.update(passed=False, error=str(exc))
        raise
    finally:
        (output / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(output / 'result.json')


if __name__ == '__main__': main()
