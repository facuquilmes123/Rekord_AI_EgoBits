param([switch]$SkipNativeBuild)
$ErrorActionPreference = 'Stop'
$rootDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $rootDir
$env:RUSTUP_HOME = Join-Path $rootDir 'build/toolchain/rustup'
$env:CARGO_HOME = Join-Path $rootDir 'build/toolchain/cargo'
$env:RUSTUP_TOOLCHAIN = 'stable-x86_64-pc-windows-msvc'
$env:PATH = (Join-Path $env:CARGO_HOME 'bin') + ';' + $env:PATH
$python = Join-Path $rootDir 'build/venv/Scripts/python.exe'
$cli = Join-Path $rootDir 'build/tauri-tools/node_modules/@tauri-apps/cli/tauri.js'
& $python installer/release_contract.py
if ($LASTEXITCODE -ne 0) { throw 'Contrato de release inconsistente.' }
& $python scripts/verify_kit.py *> (Join-Path $rootDir 'output/closure/prebuild-suite.log')
if ($LASTEXITCODE -ne 0) { throw 'Suite previa al build falló; ver output/closure/prebuild-suite.log.' }
$rustVersion = & rustc --version
if ($LASTEXITCODE -ne 0 -or $rustVersion -notmatch '^rustc 1\.98\.1 ') { throw 'El compilador Rust no coincide con toolchain.lock.json.' }
& $python installer/build_offline_bundle.py
if ($LASTEXITCODE -ne 0) { throw 'Activos offline no verificados.' }
& $python installer/prepare_webview2.py --pinned-only
if ($LASTEXITCODE -ne 0) { throw 'WebView2 no verificado.' }
& $python scripts/validate_installer_upgrade.py *> (Join-Path $rootDir 'output/closure/installer-regression.log')
if ($LASTEXITCODE -ne 0) { throw 'Regresión del instalador falló; ver installer-regression.log.' }
if (-not $SkipNativeBuild) {
    & (Join-Path $PSScriptRoot 'build_backend.ps1') -Python $python
    Push-Location (Join-Path $rootDir 'desktop/src-tauri')
    try {
        $ErrorActionPreference = 'Continue'
        & node $cli build --ci --no-bundle --target x86_64-pc-windows-msvc -- --locked --offline *> (Join-Path $rootDir 'output/closure/tauri-single-build.log')
        $code = $LASTEXITCODE
        $ErrorActionPreference = 'Stop'
        if ($code -ne 0) { throw "Tauri fallo: $code; ver output/closure/tauri-single-build.log" }
    } finally { Pop-Location }
}
& $python installer/package_single_installer.py
if ($LASTEXITCODE -ne 0) { throw 'Fallo el instalador unico; revisar inno-build.log.' }
Write-Host 'Setup.exe generado. La instalacion real se valida por separado.'
