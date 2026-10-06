param(
    [ValidateSet('msi', 'nsis', 'both')][string]$Format = 'nsis',
    [switch]$DownloadAssets
)
$ErrorActionPreference = 'Stop'
$rootDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $rootDir
$env:RUSTUP_HOME = Join-Path $rootDir 'build/toolchain/rustup'
$env:CARGO_HOME = Join-Path $rootDir 'build/toolchain/cargo'
$env:PATH = (Join-Path $env:CARGO_HOME 'bin') + ';' + $env:PATH
$python = Join-Path $rootDir 'build/venv/Scripts/python.exe'
$cli = Join-Path $rootDir 'build/tauri-tools/node_modules/@tauri-apps/cli/tauri.js'
if (-not (Test-Path -LiteralPath $python)) { throw 'Falta build/venv con requirements-build.lock.' }
if (-not (Test-Path -LiteralPath $cli)) { throw 'Falta CLI Tauri local; ver installer/toolchain.lock.json.' }
if ($DownloadAssets) { & $python installer/fetch_locked_assets.py --download }
else { & $python installer/fetch_locked_assets.py }
if ($LASTEXITCODE -ne 0) { throw 'Falló la preparación de activos fijados.' }
& $python installer/build_offline_bundle.py
if ($LASTEXITCODE -ne 0) { throw 'Falló el preflight offline.' }
if ($DownloadAssets) { & $python installer/prepare_webview2.py --download }
else { & $python installer/prepare_webview2.py }
if ($LASTEXITCODE -ne 0) { throw 'Falló WebView2 fijado.' }
& (Join-Path $PSScriptRoot 'build_backend.ps1') -Python $python
$formats = if ($Format -eq 'both') { @('nsis','msi') } else { @($Format) }
Push-Location (Join-Path $rootDir 'desktop/src-tauri')
try {
    foreach ($item in $formats) {
        $log = Join-Path $rootDir ('output/closure/tauri-' + $item + '.log')
        $ErrorActionPreference = 'Continue'
        & node $cli build --ci --bundles $item --target x86_64-pc-windows-msvc -- --locked *> $log
        $buildExit = $LASTEXITCODE
        $ErrorActionPreference = 'Stop'
        if ($buildExit -ne 0) { throw "Falló Tauri $item (código $buildExit); ver $log" }
    }
} finally { Pop-Location }
& $python installer/prepare_webview2.py
if ($LASTEXITCODE -ne 0) { throw 'WebView2 cambió durante el build; entrega bloqueada.' }
& $python installer/package_release.py
if ($LASTEXITCODE -ne 0) { throw 'Falló la entrega offline.' }
Write-Host 'Artefactos compilados. La matriz de cierre indica qué instalación y hardware fueron probados.'
