"""Bounded, read-only Windows discovery. Never opens the Rekordbox database."""
from pathlib import Path
import os
import json
import re
import xml.etree.ElementTree as ET


def discover(environ=None, registry=True):
    env = os.environ if environ is None else environ
    installs, configs, databases, exports, warnings = {}, [], set(), set(), []
    def executable(path, version=''):
        p = Path(path)
        if p.is_dir(): p = p / 'rekordbox.exe'
        if p.is_file() and p.name.lower() == 'rekordbox.exe':
            identity=str(p.resolve());raw=version or p.parent.name
            match=re.fullmatch(r'(?:rekordbox\s*)?(\d+\.\d+(?:\.\d+){0,2})',raw.strip(),re.I)
            candidate=match.group(1) if match else raw
            previous=installs.get(identity)
            if previous and re.fullmatch(r'\d+\.\d+(?:\.\d+){0,2}',previous['version']) and not version:return
            installs[identity]={'path':identity,'version':candidate}

    if registry and os.name == 'nt':
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(hive, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall', 0, winreg.KEY_READ | view) as root:
                        for i in range(winreg.QueryInfoKey(root)[0]):
                            try:
                                with winreg.OpenKey(root, winreg.EnumKey(root, i)) as key:
                                    def value(name):
                                        try: return str(winreg.QueryValueEx(key, name)[0])
                                        except OSError: return ''
                                    if 'rekordbox' in value('DisplayName').lower():
                                        location = value('InstallLocation')
                                        if location: executable(location, value('DisplayVersion'))
                                        icon = value('DisplayIcon').split(',')[0].strip('"')
                                        if icon: executable(icon, value('DisplayVersion'))
                            except OSError: continue
                except OSError: continue
    for variable in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA'):
        if not env.get(variable): continue
        root = Path(env[variable])
        for pattern in ('rekordbox*/rekordbox.exe', 'rekordbox*/rekordbox*/rekordbox.exe', 'Pioneer/rekordbox*/rekordbox.exe', 'Pioneer DJ/rekordbox*/rekordbox.exe', 'AlphaTheta/rekordbox*/rekordbox.exe'):
            for path in root.glob(pattern): executable(path)
    if env.get('APPDATA'):
        for vendor in ('Pioneer', 'Pioneer DJ', 'AlphaTheta'):
            base = Path(env['APPDATA']) / vendor
            for folder in base.glob('rekordbox*'):
                if not folder.is_dir(): continue
                configs.append(str(folder))
                db = folder / 'master.db'
                if db.is_file(): databases.add(str(db))
                for settings in folder.glob('*.settings'):
                    if 'backup' in settings.name.lower(): continue
                    try:
                        if settings.stat().st_size > 4_000_000: continue
                        raw = settings.read_bytes()
                        if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper(): continue
                        for element in ET.fromstring(raw).iter():
                            key, val = element.get('name'), element.get('val', '')
                            if not val: continue
                            if key == 'masterDbDirectory':
                                db = Path(val) / 'master.db'
                                if db.is_file(): databases.add(str(db))
                            if key == 'CollectionAutoExportXmlFile' and Path(val).is_file(): exports.add(str(Path(val)))
                    except (OSError, ET.ParseError): warnings.append('No se pudo leer una configuración de Rekordbox.')
            options = base / 'rekordboxAgent/storage/options.json'
            try:
                if options.is_file() and options.stat().st_size < 4_000_000:
                    for row in json.loads(options.read_text(encoding='utf-8')).get('options', []):
                        if isinstance(row, list) and len(row) == 2 and row[0] == 'db-path' and isinstance(row[1], str):
                            if Path(row[1]).is_file(): databases.add(str(Path(row[1])))
            except (OSError, ValueError, AttributeError): warnings.append('No se pudo leer la ubicación configurada por Rekordbox Agent.')
    return {'installations': list(installs.values()), 'configuration_directories': sorted(set(configs)),
            'databases': sorted(databases), 'export_candidates': sorted(exports), 'warnings': warnings,
            'requires_xml': not exports, 'database_access': 'not_opened',
            'next_step': 'Elegí el XML exportado de tu colección. Si todavía no existe, en Rekordbox usá Archivo → Exportar colección en formato XML.',
            'compatibility': 'Instalación detectada no implica compatibilidad certificada con su base de datos.'}
