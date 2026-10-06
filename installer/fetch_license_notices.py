"""Recover omitted Cargo license notices from the exact packaged VCS commit."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import urllib.error
import urllib.request
from build_offline_bundle import ROOT, sha256


def main():
    inventory_path = ROOT / 'assets/licenses/THIRD_PARTY_INVENTORY.json'
    inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
    raw = (ROOT / 'output/closure/cargo-metadata.json').read_bytes()
    metadata = json.loads(raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig'))
    packages = {(p['name'], p['version']): p for p in metadata['packages']}

    def recover(row):
        if row.get('ecosystem') != 'cargo' or row['notices']:
            return
        package = packages[row['name'], row['version']]
        vcs_path = Path(package['manifest_path']).parent / '.cargo_vcs_info.json'
        repository = (row['repository'] or '').removesuffix('/').removesuffix('.git')
        if not vcs_path.is_file() or not repository.startswith('https://github.com/'):
            return
        vcs = json.loads(vcs_path.read_text())
        commit = vcs['git']['sha1']
        repo = '/'.join(repository.split('/')[3:5])
        names = ['LICENSE', 'LICENSE-MIT', 'LICENSE-APACHE', 'LICENSE.md', 'LICENSE.txt', 'COPYING', 'COPYRIGHT']
        for filename in names:
            url = f'https://raw.githubusercontent.com/{repo}/{commit}/{filename}'
            try:
                with urllib.request.urlopen(url, timeout=15) as response:
                    content = response.read(2_000_000)
            except (urllib.error.URLError, TimeoutError):
                continue
            target = ROOT / 'assets/licenses/dependencies/cargo' / (row['name'] + '-' + row['version']) / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            row['notices'].append({'path': target.relative_to(ROOT).as_posix(), 'sha256': sha256(target), 'url': url, 'commit': commit})
        print(row['name'], len(row['notices']), flush=True)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(recover, inventory['components']))
    inventory_path.write_text(json.dumps(inventory, indent=2), encoding='utf-8')
    missing = [r['name'] for r in inventory['components'] if r.get('ecosystem') == 'cargo' and not r['notices']]
    print('Remaining:', missing)


if __name__ == '__main__':
    main()
