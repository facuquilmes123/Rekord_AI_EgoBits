"""Fija la descarga de WebView2 que Tauri incorpora; bloquea cambios del enlace evergreen."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request
from build_offline_bundle import ROOT, sha256


def prepare(download=False, check_tauri_cache=True):
    lock=json.loads((ROOT/'installer/webview2.lock.json').read_text())
    if check_tauri_cache:
        with urllib.request.urlopen(urllib.request.Request(lock['upstream_url'],method='HEAD'),timeout=30) as response:
            if response.url != lock['url']:
                raise ValueError('WebView2 evergreen cambió: revisar versión/licencia y actualizar lockfile antes del build')
    guid=lock['url'].split('/')[-2]
    target=Path(os.environ['LOCALAPPDATA'])/'tauri/x64'/guid/'MicrosoftEdgeWebView2RuntimeInstallerX64.exe'
    source=ROOT/'build/toolchain/MicrosoftEdgeWebView2RuntimeInstallerX64.exe'
    if not source.is_file():
        if not download: raise ValueError('WebView2 ausente; usar --download durante preparación')
        source.parent.mkdir(parents=True,exist_ok=True)
        with urllib.request.urlopen(lock['url'],timeout=60) as response,source.open('xb') as output:
            shutil.copyfileobj(response,output,1024*1024)
    if source.stat().st_size != lock['size_bytes'] or sha256(source)!=lock['sha256']:
        raise ValueError('WebView2 rechazado por tamaño/SHA-256')
    command=("$ErrorActionPreference='Stop'; "
        "Import-Module ($PSHOME+'\\Modules\\Microsoft.PowerShell.Security\\Microsoft.PowerShell.Security.psd1'); "
        "$s=Get-AuthenticodeSignature -LiteralPath $env:EGB_WEBVIEW_FILE; "
        "if($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notmatch 'Microsoft Corporation'){exit 1}")
    powershell=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
    subprocess.run([str(powershell),'-NoProfile','-Command',command],check=True,
        env={**os.environ,'EGB_WEBVIEW_FILE':str(source)},creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if not check_tauri_cache:
        print('WebView2 fijado: firma Microsoft, tamaño y hash verificados; sin resolver Evergreen.')
        return
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists() and sha256(target)!=lock['sha256']:
        raise ValueError('Cache WebView2 alterada; se conserva para investigación')
    if not target.exists(): shutil.copyfile(source,target)
    if sha256(target)!=lock['sha256']: raise ValueError('Staging WebView2 alterado')
    print('WebView2: firma Microsoft, tamaño, hash y cache Tauri verificados.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--download',action='store_true')
    parser.add_argument('--pinned-only',action='store_true')
    args=parser.parse_args()
    prepare(args.download, not args.pinned_only)
