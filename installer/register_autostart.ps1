param([string]$AppPath, [switch]$Remove)
$ErrorActionPreference = 'Stop'
$registryPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$valueName = 'RekordAIEgoBitsWatcher'
if ($Remove) {
    Remove-ItemProperty -LiteralPath $registryPath -Name $valueName -ErrorAction SilentlyContinue
    Write-Host 'Inicio automático desactivado para el próximo inicio de sesión.'
    exit 0
}
if (-not $AppPath) { throw 'Indicá -AppPath con la ruta del ejecutable instalado.' }
$appFile = (Resolve-Path -LiteralPath $AppPath).Path
if ([IO.Path]::GetExtension($appFile) -ne '.exe') { throw 'Aplicación inválida.' }
$settingsDir = Join-Path $env:LOCALAPPDATA 'Rekord AI EgoBits'
New-Item -ItemType Directory -Path $settingsDir -Force | Out-Null
$watcher = Join-Path $settingsDir 'watch_rekordbox.ps1'
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'watch_rekordbox.ps1') -Destination $watcher -Force
$command = 'powershell.exe -NoProfile -WindowStyle Hidden -File "' + $watcher + '" -AppPath "' + $appFile + '"'
New-ItemProperty -LiteralPath $registryPath -Name $valueName -Value $command -PropertyType String -Force | Out-Null
Write-Host 'Inicio automático registrado para el próximo inicio de sesión. Rekordbox activa el lanzamiento.'
