"""Preparación de build: HTTPS + tamaño/SHA-256 antes de staging. Nunca se llama en runtime."""
import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile
import urllib.request
import zipfile
from build_offline_bundle import ROOT, MANIFEST, sha256, verify_assets


def matches(path, row):
    return path.is_file() and path.stat().st_size == row['size_bytes'] and sha256(path) == row['sha256']


def prepare(allow_download=False):
    lock = json.loads(MANIFEST.read_text(encoding='utf-8'))
    cache = ROOT/'build/asset-cache'
    cache.mkdir(parents=True, exist_ok=True)
    for download in lock['downloads']:
        rows = [row for row in lock['assets'] if row['download_id'] == download['id']]
        if all(matches(ROOT/row['path'], row) for row in rows):
            continue
        name = download['filename']
        if Path(name).name != name or not download['url'].startswith('https://'):
            raise ValueError('Descarga inválida en lockfile')
        source = cache/name
        if not matches(source, download):
            if not allow_download:
                raise ValueError(f'Activo ausente/alterado: {name}; prepará el build con --download')
            handle = tempfile.NamedTemporaryFile(dir=cache, suffix='.part', delete=False)
            temporary = Path(handle.name)
            try:
                with handle as output, urllib.request.urlopen(download['url'], timeout=60) as response:
                    if not response.url.startswith('https://'):
                        raise ValueError('Redirect sin HTTPS')
                    shutil.copyfileobj(response, output, 1024*1024)
                if not matches(temporary, download):
                    raise ValueError('Descarga rechazada: tamaño/SHA-256 no coincide')
                os.replace(temporary, source)
            finally:
                temporary.unlink(missing_ok=True)
        for row in rows:
            target = (ROOT/row['path']).resolve()
            if not target.is_relative_to((ROOT/'assets').resolve()):
                raise ValueError('Destino fuera de assets')
            if matches(target,row):
                continue
            if target.exists():
                raise ValueError(f'Activo alterado conservado: {target.name}; apartalo antes de recuperar')
            target.parent.mkdir(parents=True,exist_ok=True)
            handle = tempfile.NamedTemporaryFile(dir=target.parent, suffix='.part', delete=False)
            temporary = Path(handle.name)
            try:
                with handle as output:
                    if row.get('archive_member'):
                        with zipfile.ZipFile(source) as archive, archive.open(row['archive_member']) as stream:
                            shutil.copyfileobj(stream,output,1024*1024)
                    else:
                        with source.open('rb') as stream:
                            shutil.copyfileobj(stream,output,1024*1024)
                if not matches(temporary,row):
                    raise ValueError('Staging rechazado: tamaño/SHA-256 no coincide')
                os.replace(temporary,target)
            finally:
                temporary.unlink(missing_ok=True)
    errors=verify_assets()
    if errors: raise ValueError('\n'.join(errors))
    print('Activos de build verificados antes y después del staging.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--download',action='store_true')
    prepare(parser.parse_args().download)
