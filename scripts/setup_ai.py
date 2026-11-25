"""Interactive & CLI downloader for Rekord AI local LLM engines and models.

Verifies HTTPS downloads, exact byte sizes, and SHA-256 hashes against
installer/ai_catalog.json before placing any runtime or weights into assets/.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / 'installer' / 'ai_catalog.json'
ACTIVE_CONFIG_PATH = ROOT / 'assets' / 'models' / 'active_ai.json'
CACHE_DIR = ROOT / 'build' / 'asset-cache'


def load_catalog(path: Path = CATALOG_PATH) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def detect_ram_gb() -> float | None:
    if os.name == 'nt':
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ('dwLength', ctypes.c_ulong),
                ('dwMemoryLoad', ctypes.c_ulong),
                ('ullTotalPhys', ctypes.c_ulonglong),
                ('ullAvailPhys', ctypes.c_ulonglong),
                ('ullTotalPageFile', ctypes.c_ulonglong),
                ('ullAvailPageFile', ctypes.c_ulonglong),
                ('ullTotalVirtual', ctypes.c_ulonglong),
                ('ullAvailVirtual', ctypes.c_ulonglong),
                ('ullAvailExtendedVirtual', ctypes.c_ulonglong),
            ]
        stat = MEMORYSTATUSEX(dwLength=ctypes.sizeof(MEMORYSTATUSEX))
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            return round(stat.ullTotalPhys / (1024 ** 3), 1)
    try:
        import psutil
        return round(psutil.virtual_memory().total / (1024 ** 3), 1)
    except Exception:
        return None


def recommend_profile(ram_gb: float | None) -> str:
    if ram_gb is None:
        return 'balanced'
    if ram_gb < 6.0:
        return 'lite'
    if ram_gb < 8.0:
        return 'compact'
    if ram_gb < 16.0:
        return 'balanced'
    return 'pro'


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def matches(path: Path, expected_size: int, expected_sha: str) -> bool:
    return (
        path.is_file()
        and path.stat().st_size == expected_size
        and sha256_file(path).lower() == expected_sha.lower()
    )


def download_verified(url: str, dest: Path, expected_size: int, expected_sha: str, label: str) -> Path:
    if not url.startswith('https://'):
        raise ValueError(f'Only HTTPS downloads are permitted: {url}')
    dest.parent.mkdir(parents=True, exist_ok=True)
    if matches(dest, expected_size, expected_sha):
        print(f'[OK] Cached & verified: {label}')
        return dest

    fd, tmp_name = tempfile.mkstemp(dir=dest.parent, suffix='.part')
    tmp_path = Path(tmp_name)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Rekord-AI-Setup/1.0'})
        with os.fdopen(fd, 'wb') as out, urllib.request.urlopen(req, timeout=120) as resp:
            if not resp.url.startswith('https://'):
                raise ValueError(f'Rejected non-HTTPS redirect: {resp.url}')
            total = int(resp.headers.get('Content-Length') or expected_size or 0)
            downloaded = 0
            last_pct = -1
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = int(downloaded * 100 / total)
                    if pct != last_pct and (pct % 5 == 0 or pct == 100):
                        mb_done = downloaded / (1024 * 1024)
                        mb_total = total / (1024 * 1024)
                        print(f'\rDownloading {label}: {pct:3d}% ({mb_done:.1f} / {mb_total:.1f} MiB)', end='', flush=True)
                        last_pct = pct
        print()
        if not matches(tmp_path, expected_size, expected_sha):
            raise ValueError(f'Verification failed (size or SHA-256 mismatch) for {label}')
        os.replace(tmp_path, dest)
        print(f'[OK] Verified SHA-256: {label}')
        return dest
    finally:
        tmp_path.unlink(missing_ok=True)


def extract_engine_archives(archives: list[Path], bin_dir: Path) -> list[dict]:
    bin_dir.mkdir(parents=True, exist_ok=True)
    for existing in list(bin_dir.iterdir()):
        if existing.name == '.gitkeep':
            continue
        if existing.is_file():
            existing.unlink()
        elif existing.is_dir():
            shutil.rmtree(existing)

    extracted: dict[str, dict] = {}
    for archive_path in archives:
        with zipfile.ZipFile(archive_path) as zf:
            for member in zf.infolist():
                if member.is_dir():
                    continue
                leaf = Path(member.filename).name
                if not leaf or not (leaf.lower().endswith('.exe') or leaf.lower().endswith('.dll')):
                    continue
                target = (bin_dir / leaf).resolve()
                if not target.is_relative_to(bin_dir.resolve()):
                    raise ValueError(f'Blocked zip path escape: {member.filename}')
                fd, tmp_name = tempfile.mkstemp(dir=bin_dir, suffix='.part')
                tmp_path = Path(tmp_name)
                try:
                    with os.fdopen(fd, 'wb') as out, zf.open(member) as src:
                        shutil.copyfileobj(src, out, 1024 * 1024)
                    os.replace(tmp_path, target)
                finally:
                    tmp_path.unlink(missing_ok=True)
                extracted[leaf] = {
                    'path': f'assets/bin/{leaf}',
                    'sha256': sha256_file(target),
                    'size_bytes': target.stat().st_size,
                }
    if 'llama-server.exe' not in extracted:
        raise ValueError('Engine archive did not contain llama-server.exe')
    return [extracted[k] for k in sorted(extracted)]


def install_profile(model_id: str, engine_id: str, root: Path = ROOT, catalog_path: Path = CATALOG_PATH) -> Path | None:
    if model_id == 'none':
        if ACTIVE_CONFIG_PATH.exists() and root == ROOT:
            ACTIVE_CONFIG_PATH.unlink()
        print('[OK] Deterministic-only mode selected (0 MB downloaded).')
        print('     All BPM/Camelot/energy planning, SQLCipher collection, Pro DJ Link, LUFS, and MCP tools work offline.')
        return None

    catalog = load_catalog(catalog_path)
    models = {m['id']: m for m in catalog['models']}
    engines = {e['id']: e for e in catalog['engines']}
    if model_id not in models:
        raise ValueError(f'Unknown model profile: {model_id}. Valid: {", ".join(models)}, none')
    if engine_id not in engines:
        raise ValueError(f'Unknown engine: {engine_id}. Valid: {", ".join(engines)}')

    model = models[model_id]
    engine = engines[engine_id]
    cache_dir = root / 'build' / 'asset-cache'

    archives_to_extract: list[Path] = []
    engine_zip = download_verified(
        engine['url'],
        cache_dir / engine['filename'],
        engine['size_bytes'],
        engine['sha256'],
        engine['name'],
    )
    archives_to_extract.append(engine_zip)
    for extra in engine.get('extra_archives', []):
        extra_zip = download_verified(
            extra['url'],
            cache_dir / extra['filename'],
            extra['size_bytes'],
            extra['sha256'],
            extra['filename'],
        )
        archives_to_extract.append(extra_zip)

    bin_files = extract_engine_archives(archives_to_extract, root / 'assets' / 'bin')

    model_target = (root / model['path']).resolve()
    if not model_target.is_relative_to((root / 'assets' / 'models').resolve()):
        raise ValueError('Model path escapes assets/models')
    download_verified(
        model['url'],
        model_target,
        model['size_bytes'],
        model['sha256'],
        model['name'],
    )

    active_payload = {
        'schema_version': 1,
        'model_id': model['id'],
        'model_path': model['path'],
        'model_sha256': model['sha256'],
        'engine_id': engine['id'],
        'gpu_layers': engine['gpu_layers'],
        'binary_path': 'assets/bin/llama-server.exe',
        'binary_sha256': next(f['sha256'] for f in bin_files if f['path'] == 'assets/bin/llama-server.exe'),
        'runtime_assets': bin_files,
    }
    active_file = root / 'assets' / 'models' / 'active_ai.json'
    active_file.parent.mkdir(parents=True, exist_ok=True)
    active_file.write_text(json.dumps(active_payload, indent=2) + '\n', encoding='utf-8')
    print(f'\n[READY] Active AI profile saved to {active_file.relative_to(root)}')
    print(f'        Model : {model["name"]}')
    print(f'        Engine: {engine["name"]} (gpu_layers={engine["gpu_layers"]})')
    return active_file


def print_catalog(catalog: dict, ram_gb: float | None) -> None:
    rec = recommend_profile(ram_gb)
    ram_txt = f'{ram_gb} GB detected' if ram_gb is not None else 'RAM unknown'
    print(f'\nRekord AI Local LLM Profiles ({ram_txt} -> recommended: {rec}):\n')
    for m in catalog['models']:
        size_mb = m['size_bytes'] / (1024 * 1024)
        size_str = f'{size_mb / 1024:.2f} GiB' if size_mb >= 1024 else f'{size_mb:.0f} MiB'
        tag = ' [RECOMMENDED FOR YOUR PC]' if m['id'] == rec else ''
        print(f"  - {m['id']:8s} | {m['name']:24s} | {size_str:9s} | Min {m['min_ram_gb']:2d} GB RAM{tag}")
        print(f"             {m['description']}")
        print(f"             URL: {m['url']}")
    print('\n  - none     | Deterministic Mode (No LLM) | 0 MiB     | Any PC')
    print('             Uses deterministic BPM/Camelot/energy planning, Pro DJ Link, LUFS, and MCP without AI chat.\n')
    print('Inference Engines (llama.cpp b11146):')
    for e in catalog['engines']:
        size_mb = e['size_bytes'] / (1024 * 1024)
        print(f"  - {e['id']:8s} | {e['name']:36s} | {size_mb:6.1f} MiB | {e['description']}")


def interactive_prompt(catalog: dict, ram_gb: float | None) -> tuple[str, str]:
    print_catalog(catalog, ram_gb)
    rec = recommend_profile(ram_gb)
    model_choice = input(f'Select AI model [lite / compact / balanced / pro / none] (default: {rec}): ').strip().lower() or rec
    if model_choice == 'none':
        return 'none', 'cpu'
    engine_choice = input('Select inference engine [cpu / vulkan / cuda] (default: cpu): ').strip().lower() or 'cpu'
    return model_choice, engine_choice


def main() -> int:
    parser = argparse.ArgumentParser(description='Download & verify Rekord AI local LLM engine and model.')
    parser.add_argument('--list', action='store_true', help='List available models, engines, and direct URLs.')
    parser.add_argument('--profile', choices=['lite', 'compact', 'balanced', 'pro', 'none'], help='Model tier to install.')
    parser.add_argument('--engine', choices=['cpu', 'vulkan', 'cuda'], default='cpu', help='llama.cpp runtime backend.')
    args = parser.parse_args()

    catalog = load_catalog()
    ram_gb = detect_ram_gb()
    if args.list:
        print_catalog(catalog, ram_gb)
        return 0

    if args.profile:
        model_id, engine_id = args.profile, args.engine
    else:
        model_id, engine_id = interactive_prompt(catalog, ram_gb)

    install_profile(model_id, engine_id)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
