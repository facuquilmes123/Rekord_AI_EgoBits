"""Compare cached Cargo archives and extracted sources with the locked checksums.

No dependencies are downloaded, installed, executed or changed.
"""
import hashlib
import json
from pathlib import Path
import tarfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def main():
    lock_path = ROOT / 'desktop/src-tauri/Cargo.lock'
    lock = tomllib.loads(lock_path.read_text(encoding='utf-8'))
    registry = ROOT / 'build/toolchain/cargo/registry'
    errors, packages, files = [], [], 0
    for row in lock['package']:
        if not row.get('source', '').startswith('registry+'):
            continue
        name = row['name'] + '-' + row['version']
        archives = list((registry / 'cache').glob('*/' + name + '.crate'))
        sources = list((registry / 'src').glob('*/' + name))
        if len(archives) != 1 or len(sources) != 1:
            errors.append(name + ': missing or ambiguous archive/source')
            continue
        digest = hashlib.sha256(archives[0].read_bytes()).hexdigest()
        if digest != row['checksum']:
            errors.append(name + ': archive checksum mismatch')
            continue
        with tarfile.open(archives[0], 'r:gz') as archive:
            for member in archive:
                if not member.isfile():
                    continue
                relative = Path(member.name).relative_to(name)
                target = (sources[0] / relative).resolve()
                if not target.is_relative_to(sources[0].resolve()):
                    errors.append(name + ': unsafe source path'); continue
                stream = archive.extractfile(member)
                expected = hashlib.sha256(stream.read()).hexdigest()
                if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
                    errors.append(name + ': source differs: ' + str(relative))
                files += 1
        packages.append({'name': row['name'], 'version': row['version'], 'sha256': digest})
    report = {'scope': 'cargo_locked_archives_and_source_files', 'packages': packages,
              'files_checked': files, 'errors': errors, 'passed': not errors,
              'lock_sha256': hashlib.sha256(lock_path.read_bytes()).hexdigest(),
              'limits': 'Does not certify toolchain binaries, compiled output or absence of malware.'}
    output = ROOT / 'output/closure/rust-supply-chain-audit.json'
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'packages': len(packages), 'files': files, 'errors': errors[:20], 'report': str(output)}))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__': main()
