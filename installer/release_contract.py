"""Reject release drift before building any installer; stable upgrade identity."""
import json
from pathlib import Path
import re
import tomllib

ROOT=Path(__file__).resolve().parents[1]


def verify_release(root=ROOT):
    release=json.loads((root/'release.json').read_text(encoding='utf-8'))
    version=release['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+',version): raise ValueError('Versión inválida')
    config=json.loads((root/'desktop/src-tauri/tauri.conf.json').read_text(encoding='utf-8'))
    python=tomllib.loads((root/'prototype/pyproject.toml').read_text(encoding='utf-8'))
    cargo=tomllib.loads((root/'desktop/src-tauri/Cargo.toml').read_text(encoding='utf-8'))
    lock=tomllib.loads((root/'desktop/src-tauri/Cargo.lock').read_text(encoding='utf-8'))
    shell=next(row for row in lock['package'] if row['name']=='egobits-desktop')
    service=(root/'prototype/egobits/desktop/service.py').read_text(encoding='utf-8')
    xml=(root/'prototype/egobits/adapters/xml_adapter.py').read_text(encoding='utf-8')
    if any(v!=version for v in (config['version'],python['project']['version'],cargo['package']['version'],shell['version'])):
        raise ValueError('Versiones de componentes inconsistentes con release.json')
    if f"'version': '{version}'" not in service or version not in xml: raise ValueError('Versión HTTP/XML inconsistente')
    if release['app_id']!='F57C7090-73DC-453B-96DF-8D9F3E215E10' or config['identifier']!=release['identifier'] or release['identifier']!='com.egobits.rekordai':
        raise ValueError('La identidad estable de actualización fue alterada')
    rust=(root/'desktop/src-tauri/src/main.rs').read_text(encoding='utf-8')
    if release['app_mutex']!=r'Local\RekordAIApp' or '"Local\\\\RekordAIApp"' not in rust:
        raise ValueError('El mutex de la aplicación no coincide con el contrato de actualización')
    iss=(root/'installer/egobits.iss').read_text(encoding='utf-8')
    expected=['AppId={{'+release['app_id']+'}', 'AppMutex='+release['app_mutex'], 'UsePreviousAppDir=yes','UsePreviousTasks=yes','PrivilegesRequired=lowest','ArchitecturesInstallIn64BitMode=x64os']
    if any(line not in iss.splitlines() for line in expected): raise ValueError('Contrato de actualización del instalador incompleto')
    if release['settings_folder']!='Rekord AI EgoBits' or release['native_backups_folder']!='Rekord AI/native-operations': raise ValueError('Ubicación persistente de datos alterada sin migración')
    return release


if __name__=='__main__': print('Contrato de release verificado: '+verify_release()['version'])
