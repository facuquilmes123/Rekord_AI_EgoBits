param([string]$Python)
$ErrorActionPreference = 'Stop'
$rootDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $Python) { $Python = Join-Path $rootDir 'build/venv/Scripts/python.exe' }
& $Python (Join-Path $PSScriptRoot 'install_local_components.py') --install
if ($LASTEXITCODE -ne 0) { throw 'Componentes nativos/audio no verificados.' }
$buildDir = Join-Path $rootDir 'build'
$backendDist = Join-Path $buildDir 'backend'
$stageDir = Join-Path $rootDir 'desktop/src-tauri/binaries'
New-Item -ItemType Directory -Force -Path $stageDir,(Join-Path $rootDir 'output/closure') | Out-Null
$ErrorActionPreference = 'Continue' # PowerShell 5 trata stderr informativo como NativeCommandError.
& $Python -m PyInstaller --noconfirm --onefile --clean --name egobits-backend `
    --paths (Join-Path $rootDir 'prototype') --hidden-import egobits.desktop.service `
    --add-data ((Join-Path $rootDir 'prototype/examples') + ';examples') `
    --add-data ((Join-Path $rootDir 'prototype/egobits/desktop/ui') + ';egobits/desktop/ui') `
    --distpath $backendDist --workpath (Join-Path $buildDir 'pyinstaller') `
    --specpath $buildDir (Join-Path $PSScriptRoot 'backend_entry.py') *> (Join-Path $rootDir 'output/closure/pyinstaller.log')
$backendExit = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
if ($backendExit -ne 0) { throw 'Falló PyInstaller; ver output/closure/pyinstaller.log' }
$source = Join-Path $backendDist 'egobits-backend.exe'
$target = Join-Path $stageDir 'egobits-backend-x86_64-pc-windows-msvc.exe'
Copy-Item -LiteralPath $source -Destination $target -Force
$hash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $hash) { throw 'Hash de staging no coincide.' }
[pscustomobject]@{path=$source;sha256=$hash;size=(Get-Item -LiteralPath $source).Length} | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $rootDir 'output/closure/backend-build.json')
Write-Host "Backend compilado y verificado: $hash"
