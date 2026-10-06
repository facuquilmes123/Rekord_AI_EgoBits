"""Require a local Defender custom scan before packaging executable payloads.

No exclusions, restoration, protection changes or execution of the payload.
This is host evidence, not a guarantee against malware or other antivirus engines.
"""
import os
import hashlib
from pathlib import Path
import subprocess


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        while chunk := source.read(1024 * 1024): digest.update(chunk)
    return digest.hexdigest()


def scan_payload(paths, log_path):
    paths = [Path(p).resolve() for p in paths]
    if not paths or any(not p.is_file() for p in paths):
        raise RuntimeError('Payload ausente: revisar cuarentena y build antes de empaquetar.')
    platform = Path(os.environ.get('ProgramData', 'C:/ProgramData')) / 'Microsoft/Windows Defender/Platform'
    candidates = sorted(platform.glob('*/MpCmdRun.exe'), reverse=True)
    fallback = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Windows Defender/MpCmdRun.exe'
    scanner = next((p for p in [*candidates, fallback] if p.is_file()), None)
    if scanner is None:
        raise RuntimeError('No se puede verificar Defender. La entrega queda bloqueada.')
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open('w', encoding='utf-8') as log:
        for path in paths:
            before = file_hash(path)
            log.write(f'Scan: {path}\n'); log.flush()
            result = subprocess.run([str(scanner), '-Scan', '-ScanType', '3', '-File',
                                     str(path), '-DisableRemediation'],
                                    stdout=log, stderr=subprocess.STDOUT, timeout=600)
            if result.returncode != 0 or not path.is_file() or file_hash(path) != before:
                raise RuntimeError(f'Defender bloquea la entrega o no pudo analizar {path.name}; ver {log_path}')
    return 'HOST_DEFENDER_SCAN_PASSED'
