"""Install approved local wheels for native/audio builds; never access the network."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]

def main(install=False):
    requirements=[]
    for component in ('native','audio'):
        for row in json.loads((ROOT/'installer'/f'{component}-wheels.lock.json').read_text()):
            wheel=(ROOT/'build'/f'{component}-wheels'/row['file']).resolve()
            if not wheel.is_relative_to(ROOT/'build') or wheel.suffix!='.whl': raise SystemExit('Ruta de wheel no admitida')
            if hashlib.sha256(wheel.read_bytes()).hexdigest()!=row['sha256']: raise SystemExit('Wheel alterado: '+wheel.name)
            with zipfile.ZipFile(wheel) as archive:
                metadata=archive.read(next(n for n in archive.namelist() if n.endswith('.dist-info/METADATA'))).decode()
                name=next(l[6:] for l in metadata.splitlines() if l.startswith('Name: '))
                version=next(l[9:] for l in metadata.splitlines() if l.startswith('Version: '))
                requirements.append(f'{name}=={version} --hash=sha256:{row["sha256"]}')
    print(f'{len(requirements)} wheels locales verificados por SHA-256')
    if install:
        path=ROOT/'build/native-audio-requirements.txt'
        path.write_text('\n'.join(requirements)+'\n')
        subprocess.run([sys.executable,'-m','pip','install','--no-index','--require-hashes',
                        '--find-links',str(ROOT/'build/native-wheels'),'--find-links',str(ROOT/'build/audio-wheels'),
                        '-r',str(path)],check=True)

if __name__=='__main__': main('--install' in sys.argv)
