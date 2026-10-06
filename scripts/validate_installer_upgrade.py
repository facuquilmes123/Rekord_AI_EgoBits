"""Run production Inno logic with a separate AppId and inert or full payload.

No real user install, startup value, Rekordbox process or collection is touched.
--full-payload tests real binaries/model extraction, but skips WebView installation.
Neither mode certifies a clean Windows host or changes the real user installation.
"""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import winreg
import sys
import argparse

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'installer'))
from package_single_installer import write_runtime_includes
GUID='B0A7331C-AD3D-4E78-9ED3-841D084CF533'
APP='Rekord AI Installer QA'
KEY=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{'+GUID+'}_is1'


def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def verify_install_log(path, runtime_count):
    content=path.read_text(encoding='utf-8-sig')
    assert 'Exception message:' not in content and 'Runtime error' not in content, content[-5000:]
    assert content.count('Runtime SHA-256 verified: ')==runtime_count, 'Missing runtime integrity callbacks'


def installed():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,KEY,0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as k:
        return {n:winreg.QueryValueEx(k,n)[0] for n in ('DisplayVersion','InstallLocation')}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--full-payload',action='store_true',help='Extract actual shell/backend/runtime/model using isolated QA identity')
    full=parser.parse_args().full_payload
    current=json.loads((ROOT/'release.json').read_text())['version']
    prefix,patch=current.rsplit('.',1)
    if int(patch)<1:raise SystemExit('Para versión x.y.0 especificar una fixture anterior antes de este ensayo')
    previous=prefix+'.'+str(int(patch)-1)
    try: installed()
    except FileNotFoundError: pass
    else: raise SystemExit('El AppId QA ya existe. Revisar el ensayo anterior antes de repetir.')
    lab=ROOT/'output/closure'/('upgrade-lab-'+str(time.time_ns()));lab.mkdir()
    fixture=lab/'fixture';fixture.mkdir()
    install=lab/'installed'
    if not install.resolve().is_relative_to(lab.resolve()): raise SystemExit('Destino fuera del laboratorio')
    files={
        'desktop/src-tauri/target/x86_64-pc-windows-msvc/release/egobits-desktop.exe':Path(os.environ['WINDIR'])/'System32/whoami.exe',
        'build/backend/egobits-backend.exe':Path(os.environ['WINDIR'])/'System32/whoami.exe',
        'desktop/src-tauri/icons/rekord-ia.ico':ROOT/'desktop/src-tauri/icons/rekord-ia.ico',
        'installer/watch_rekordbox.ps1':ROOT/'installer/watch_rekordbox.ps1',
        'installer/offline_assets.json':ROOT/'installer/offline_assets.json',
        'release.json':ROOT/'release.json',
    }
    if full:
        for name in tuple(files):
            if name.endswith('egobits-desktop.exe') or name.endswith('egobits-backend.exe'):files[name]=ROOT/name
    for name,source in files.items():
        target=fixture/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    model=fixture/'assets/models/Qwen3.5-4B-Q4_K_M.gguf';model.parent.mkdir(parents=True);model.write_bytes(b'QA inert model fixture')
    webview=fixture/'build/toolchain/MicrosoftEdgeWebView2RuntimeInstallerX64.exe';webview.parent.mkdir(parents=True);webview.write_bytes(b'QA WebView fixture, not executed')
    for name in ('assets/bin/qa.txt','assets/licenses/qa.txt'):
        path=fixture/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('Inert fixture')
    write_runtime_includes({'assets':[{'path':'assets/bin/qa.txt','sha256':sha(fixture/'assets/bin/qa.txt')}]},fixture/'installer')
    runtime_count=1
    if full:
        shutil.copy2(ROOT/'assets/models/Qwen3.5-4B-Q4_K_M.gguf',model)
        shutil.copytree(ROOT/'assets/bin',fixture/'assets/bin',dirs_exist_ok=True)
        shutil.copytree(ROOT/'assets/licenses',fixture/'assets/licenses',dirs_exist_ok=True)
        (fixture/'assets/bin/qa.txt').unlink()
        manifest=json.loads((ROOT/'installer/offline_assets.json').read_text())
        write_runtime_includes(manifest,fixture/'installer')
        runtime_count=sum(row['path'].startswith('assets/bin/') for row in manifest['assets'])
    source=(ROOT/'installer/egobits.iss').read_text(encoding='utf-8')
    source=source.replace('F57C7090-73DC-453B-96DF-8D9F3E215E10',GUID).replace('AppName=Rekord AI','AppName='+APP)
    source=source.replace('Local\\RekordAIApp','Local\\RekordAIInstallerQAApp').replace('Local\\RekordAISetup','Local\\RekordAIInstallerQASetup')
    source=source.replace('Name: "{autoprograms}\\Rekord AI"','Name: "{autoprograms}\\'+APP+'"').replace('Name: "{autodesktop}\\Rekord AI"','Name: "{autodesktop}\\'+APP+'"')
    source=source.replace('RekordAIEgoBitsWatcher','RekordAIInstallerQAWatcher')
    # WebView already installed is outside this upgrade logic test. Never run stub.
    source=source.replace('if WebViewInstalled then exit;','exit; { QA: runtime prerequisite intentionally excluded }')
    script=fixture/'installer/egobits.iss';script.write_text(source,encoding='utf-8')
    compiler=ROOT/'build/toolchain/inno/ISCC.exe'
    artifacts={}
    for version in (previous,current):
        if version==current and not full:
            shutil.copy2(Path(os.environ['WINDIR'])/'System32/hostname.exe',fixture/'build/backend/egobits-backend.exe')
        shell=fixture/'desktop/src-tauri/target/x86_64-pc-windows-msvc/release/egobits-desktop.exe'
        backend=fixture/'build/backend/egobits-backend.exe'
        (fixture/'installer/generated-assets.iss').write_text(f'#define ReleaseVersion "{version}"\n#define ModelHash "{sha(model)}"\n#define WebViewHash "{sha(webview)}"\n#define ShellHash "{sha(shell)}"\n#define BackendHash "{sha(backend)}"\n')
        with (lab/f'compile-{version}.log').open('w') as log:
            subprocess.run([str(compiler),'/DRepoRoot='+str(fixture),str(script)],stdout=log,stderr=subprocess.STDOUT,check=True)
        artifacts[version]=fixture/f'dist/Rekord_AI_Setup_{version}_x64.exe'
    args=['/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/TASKS=']
    report={'test_type':'isolated_full_payload' if full else 'isolated_inno_logic_fixture','real_user_install_modified':False,'real_rekordbox_closed':False,'webview_prerequisite_tested':False}
    uninstaller=None
    try:
        result=subprocess.run([str(artifacts[previous]),*args,'/DIR='+str(install),'/LOG='+str(lab/'install.log')])
        assert result.returncode==0
        uninstaller=install/'unins000.exe'
        verify_install_log(lab/'install.log',runtime_count)
        first=installed();assert first['DisplayVersion']==previous
        marker=install/'user-preservation-test.json';marker.write_text('User settings sentinel')
        backup=install/'native-backups-sentinel/receipt.json';backup.parent.mkdir();backup.write_text('Verified backup sentinel')
        hashes={str(p):sha(p) for p in (marker,backup)}
        old_backend=sha(install/'egobits-backend.exe')
        result=subprocess.run([str(artifacts[current]),*args,'/LOG='+str(lab/'upgrade.log')])
        assert result.returncode==0
        verify_install_log(lab/'upgrade.log',runtime_count)
        second=installed();assert second['DisplayVersion']==current
        assert Path(second['InstallLocation']).resolve()==install.resolve()
        assert all(sha(Path(p))==h for p,h in hashes.items())
        if not full:assert sha(install/'egobits-backend.exe')!=old_backend
        else:
            assert sha(install/'egobits-backend.exe')==sha(ROOT/'build/backend/egobits-backend.exe')
            assert sha(install/'egobits-desktop.exe')==sha(ROOT/'desktop/src-tauri/target/x86_64-pc-windows-msvc/release/egobits-desktop.exe')
            assert sha(install/'assets/models/Qwen3.5-4B-Q4_K_M.gguf')==sha(model)
        dll=ctypes.WinDLL('kernel32',use_last_error=True)
        dll.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_wchar_p];dll.CreateMutexW.restype=ctypes.c_void_p
        dll.CloseHandle.argtypes=[ctypes.c_void_p]
        mutex=dll.CreateMutexW(None,0,'Local\\RekordAIInstallerQAApp');assert mutex
        try: running=subprocess.run([str(artifacts[current]),*args,'/LOG='+str(lab/'running-blocked.log')])
        finally:dll.CloseHandle(mutex)
        assert running.returncode!=0
        downgrade=subprocess.run([str(artifacts[previous]),*args,'/LOG='+str(lab/'downgrade.log')])
        assert downgrade.returncode!=0 and installed()['DisplayVersion']==current
        assert all(sha(Path(p))==h for p,h in hashes.items())
        report.update(previous_version=previous,current_version=current,fresh_install=True,upgrade=True,previous_directory_reused=True,user_settings_and_backups_preserved=True,backend_replaced=not full,full_payload_hashes_verified=full,runtime_callbacks_verified=runtime_count,internal_errors=False,mutex_blocks_running_upgrade=True,downgrade_blocked=True)
    finally:
        if uninstaller and uninstaller.is_file():
            assert uninstaller.resolve().is_relative_to(lab.resolve())
            clean=subprocess.run([str(uninstaller),*args,'/LOG='+str(lab/'uninstall.log')]);report['qa_uninstall_exit_code']=clean.returncode
    try:installed();raise AssertionError('QA registry remains')
    except FileNotFoundError:report['qa_registry_removed']=True
    (lab/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(lab/'result.json')


if __name__=='__main__':main()
