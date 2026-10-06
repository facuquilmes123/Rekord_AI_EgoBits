"""Fail-closed preflight for a self-contained Windows installer.

No downloads or output directories are created. Only hashes supplied from
locally inspected release artifacts in offline_assets.json are accepted.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'installer' / 'offline_assets.json'
REQUIRED = {
    'assets/bin/llama-server.exe',
    'assets/models/Qwen3.5-4B-Q4_K_M.gguf',
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify_assets(manifest: Path = MANIFEST) -> list[str]:
    errors: list[str] = []
    try:
        rows = json.loads(manifest.read_text(encoding='utf-8'))['assets']
    except (FileNotFoundError, ValueError, KeyError, TypeError) as exc:
        return [f'Manifiesto de activos inválido: {exc}']
    if not isinstance(rows, list):
        return ['El manifiesto debe contener una lista assets']
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            errors.append('Fila de activo inválida')
            continue
        relative = row.get('path')
        expected = row.get('sha256')
        if not isinstance(relative, str) or relative in seen:
            errors.append(f'Ruta de activo duplicada o inválida: {relative}')
            continue
        seen.add(relative)
        path = (ROOT / relative).resolve()
        if not path.is_relative_to((ROOT / 'assets').resolve()) or (ROOT / relative).is_symlink():
            errors.append(f'Ruta fuera de assets o enlace simbólico: {relative}')
            continue
        if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', expected):
            errors.append(f'SHA-256 real pendiente: {relative}')
        if not row.get('source') or not row.get('license'):
            errors.append(f'Procedencia o licencia no declarada: {relative}')
        if any(not row.get(key) for key in ('url','revision','author','size_bytes')):
            errors.append(f'Lockfile incompleto: {relative}')
        if not path.is_file():
            errors.append(f'Activo ausente: {relative}')
        elif isinstance(expected, str) and re.fullmatch(r'[0-9a-fA-F]{64}', expected):
            if path.stat().st_size != row.get('size_bytes'):
                errors.append(f'Tamaño no coincide: {relative}')
            if sha256(path) != expected.lower():
                errors.append(f'SHA-256 no coincide: {relative}')
    errors.extend(f'Activo requerido sin manifiesto: {path}' for path in sorted(REQUIRED - seen))
    bin_dir = ROOT / 'assets' / 'bin'
    if bin_dir.exists():
        unlisted = {p.relative_to(ROOT).as_posix() for p in bin_dir.rglob('*')
                    if p.is_file() and p.name != '.gitkeep'} - seen
        errors.extend(f'Binario sin hash declarado: {path}' for path in sorted(unlisted))
    return errors


def verify_upstream() -> list[str]:
    errors: list[str] = []
    try:
        rows = json.loads((ROOT / 'research' / 'upstream_manifest.json').read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        return [f'Manifiesto upstream inválido: {exc}']
    for row in rows:
        path = (ROOT / row['local_path']).resolve()
        if not path.is_relative_to((ROOT / 'upstream').resolve()) or not path.is_file():
            errors.append(f'Upstream ausente o fuera de upstream/: {row["local_path"]}')
        elif sha256(path) != row['sha256'].lower():
            errors.append(f'Upstream alterado: {row["local_path"]}')
    return errors


def main() -> int:
    errors = verify_upstream() + verify_assets()
    if errors:
        for error in errors:
            print(f'ERROR: {error}', file=sys.stderr)
        print('Build offline BLOQUEADO: no se creará un instalador incompleto.', file=sys.stderr)
        return 1
    print('OK: upstream y todos los activos offline coinciden con SHA-256 declarado.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
