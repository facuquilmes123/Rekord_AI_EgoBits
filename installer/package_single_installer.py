"""Build the single offline graphical installer from verified local artifacts."""
import json
import subprocess
import re
from build_offline_bundle import ROOT, sha256, verify_assets, verify_upstream
from release_contract import verify_release
from antivirus_gate import scan_payload


def verify_frozen_sources(backend):
    """Reject edits made after PyInstaller analyzed a module, before delivery."""
    from PyInstaller.archive.readers import CArchiveReader
    from types import CodeType
    def semantic(code):
        return (code.co_code,tuple(semantic(c) if isinstance(c,CodeType) else c for c in code.co_consts),
                code.co_names,code.co_varnames,code.co_argcount,code.co_posonlyargcount,
                code.co_kwonlyargcount,code.co_flags,code.co_freevars,code.co_cellvars,code.co_exceptiontable)
    archive=CArchiveReader(str(backend))
    pyz=archive.open_embedded_archive(next(name for name in archive.toc if name.endswith('.pyz')))
    checked=0
    for name in pyz.toc:
        if name!='egobits' and not name.startswith('egobits.'):continue
        base=ROOT/'prototype'/name.replace('.','/')
        source=base/'__init__.py' if pyz.toc[name][0]==1 else base.with_suffix('.py')
        if not source.is_file():raise ValueError(f'Falta fuente del módulo congelado: {name}')
        expected=compile(source.read_text(encoding='utf-8'),str(source),'exec',optimize=0)
        if semantic(expected)!=semantic(pyz.extract(name)):
            raise ValueError(f'Backend desactualizado respecto de la fuente: {name}. Recompilar antes de empaquetar.')
        checked+=1
    if not checked:raise ValueError('Backend sin módulos verificables')
    entries={name.replace('\\','/'):name for name in archive.toc}
    ui=ROOT/'prototype/egobits/desktop/ui'
    for source in ui.rglob('*'):
        if not source.is_file():continue
        key='egobits/desktop/ui/'+source.relative_to(ui).as_posix()
        if key not in entries or archive.extract(entries[key])!=source.read_bytes():
            raise ValueError(f'Interfaz congelada desactualizada: {source.name}. Recompilar backend antes de empaquetar.')
    return checked


def runtime_includes(manifest):
    files=[];checks=[];names=set()
    for row in sorted(manifest['assets'],key=lambda row:row['path']):
        path=row['path']
        if not path.startswith('assets/bin/'):continue
        name=path[len('assets/bin/'):]
        checksum=row['sha256']
        if not re.fullmatch(r'[A-Za-z0-9_.-]+',name) or name in ('.','..') or name.casefold() in names or not re.fullmatch('[0-9a-f]{64}',checksum):
            raise ValueError('Activo runtime inválido o duplicado')
        names.add(name.casefold())
        files.append(f'Source: "{{#RepoRoot}}\\assets\\bin\\{name}"; DestDir: "{{app}}\\assets\\bin"; Flags: ignoreversion; Hash: "{checksum}"; AfterInstall: VerifyRuntimeFile(\'{{app}}\\assets\\bin\\{name}\', \'{checksum}\')')
        checks.append(f"    if not FileExists(ExpandConstant('{{app}}\\assets\\bin\\{name}')) then exit;\n    if CompareText(GetSHA256OfFile(ExpandConstant('{{app}}\\assets\\bin\\{name}')), '{checksum}') <> 0 then exit;")
    if not files:raise ValueError('El instalador no contiene runtime local')
    code='function RuntimePayloadValid: Boolean;\nbegin\n  Result := False;\n  try\n'+'\n'.join(checks)+'\n    Result := True;\n  except\n    Result := False;\n  end;\nend;\n'
    return '\n'.join(files)+'\n',code


def write_runtime_includes(manifest, directory):
    files,code=runtime_includes(manifest)
    (directory/'generated-runtime-files.iss').write_text(files,encoding='utf-8')
    (directory/'generated-runtime-checks.iss').write_text(code,encoding='utf-8')


def main():
    release = verify_release()
    errors = verify_assets() + verify_upstream()
    if errors: raise SystemExit('\n'.join(errors))
    compiler = ROOT / 'build/toolchain/inno/ISCC.exe'
    shell = ROOT / 'desktop/src-tauri/target/x86_64-pc-windows-msvc/release/egobits-desktop.exe'
    backend = ROOT / 'build/backend/egobits-backend.exe'
    if not all(path.is_file() for path in (compiler, shell, backend)):
        raise SystemExit('Falta compilador Inno, shell Tauri o backend real.')
    try:frozen_modules=verify_frozen_sources(backend)
    except (ValueError,ImportError) as exc:raise SystemExit(str(exc))
    executable_payload = [shell, backend, *sorted((ROOT / 'assets/bin').glob('*.exe')),
                          *sorted((ROOT / 'assets/bin').glob('*.dll'))]
    try:
        antivirus = scan_payload(executable_payload, ROOT / 'output/closure/defender-payload.log')
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(str(exc))
    manifest = json.loads((ROOT / 'installer/offline_assets.json').read_text())
    write_runtime_includes(manifest,ROOT/'installer')
    model = next(row for row in manifest['assets'] if row['path'].endswith('.gguf'))
    webview = json.loads((ROOT / 'installer/webview2.lock.json').read_text())
    webview_file = ROOT / 'build/toolchain/MicrosoftEdgeWebView2RuntimeInstallerX64.exe'
    if webview_file.stat().st_size != webview['size_bytes'] or sha256(webview_file) != webview['sha256']:
        raise SystemExit('WebView2 alterado.')
    generated = ROOT / 'installer/generated-assets.iss'
    generated.write_text(f'#define ReleaseVersion "{release["version"]}"\n#define ModelHash "{model["sha256"]}"\n#define WebViewHash "{webview["sha256"]}"\n#define ShellHash "{sha256(shell)}"\n#define BackendHash "{sha256(backend)}"\n')
    artifact = ROOT / ('dist/Rekord_AI_Setup_'+release['version']+'_x64.exe')
    if artifact.exists(): raise SystemExit('Se conserva instalador anterior; moverlo antes de reconstruir.')
    log_path = ROOT / 'output/closure/inno-build.log'
    with log_path.open('w', encoding='utf-8') as log:
        result = subprocess.run([str(compiler), '/DRepoRoot=' + str(ROOT), str(ROOT / 'installer/egobits.iss')],
                                stdout=log, stderr=subprocess.STDOUT)
    if result.returncode: raise SystemExit(f'ISCC falló: {result.returncode}; ver {log_path}')
    if not artifact.is_file() or artifact.stat().st_size >= 4_200_000_000:
        raise SystemExit('Artefacto ausente o excede límite de instalador único.')
    digest = sha256(artifact)
    try:
        scan_payload([artifact], ROOT / 'output/closure/defender-installer.log')
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(f'Instalador generado pero NO aprobado para entrega: {exc}')
    artifact.with_suffix('.exe.sha256').write_text(digest + '  ' + artifact.name + '\n')
    report = {'path': str(artifact), 'size_bytes': artifact.stat().st_size, 'sha256': digest,
              'build_exit_code': result.returncode, 'shell_sha256': sha256(shell),
              'backend_sha256': sha256(backend), 'model_sha256': model['sha256'],
              'webview_sha256': webview['sha256'], 'installation_test': 'NOT_TESTED',
              'antivirus': antivirus, 'installer_defender_scan': 'HOST_DEFENDER_SCAN_PASSED',
              'authenticode': 'NOT_SIGNED','version':release['version'],'app_id':release['app_id'],
              'supports_fresh_install_and_upgrade':True,'update_mode':release['update_mode'],
              'frozen_source_modules_verified':frozen_modules}
    (ROOT / 'output/closure/single-installer.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
