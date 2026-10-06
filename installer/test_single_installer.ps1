$ErrorActionPreference = 'Stop'
$rootDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$reportPath = Join-Path $rootDir 'output/closure/installer-host-test.json'
$build = Get-Content -Raw -LiteralPath (Join-Path $rootDir 'output/closure/single-installer.json') | ConvertFrom-Json
$artifact = (Resolve-Path -LiteralPath $build.path).Path
if ((Get-FileHash -LiteralPath $artifact).Hash -ne $build.sha256) { throw 'Instalador alterado.' }
$registry = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{F57C7090-73DC-453B-96DF-8D9F3E215E10}_is1'
if (Test-Path -LiteralPath $registry) { throw 'Ya existe una instalacion; no se modifica para este ensayo.' }
$testRoot = Join-Path $rootDir 'output/closure'
$installDir = Join-Path $testRoot ('installed-qa-' + [Guid]::NewGuid().ToString('N'))
if (-not ([IO.Path]::GetFullPath($installDir)).StartsWith($testRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Ruta de ensayo fuera del proyecto.' }
$report = [ordered]@{installer_sha256=$build.sha256;environment='Current Windows development host';network_disabled=$false;clean_vm=$false;install_dir=$installDir;install_exit=$null;uninstall_exit=$null;checks=@{}}
$installLog = Join-Path $testRoot 'inno-host-install.log'
$uninstallLog = Join-Path $testRoot 'inno-host-uninstall.log'
try {
    $arguments = @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/NOICONS','/TASKS=',('/DIR="'+$installDir+'"'),('/LOG="'+$installLog+'"'))
    $process = Start-Process -FilePath $artifact -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
    $report.install_exit = $process.ExitCode
    if ($process.ExitCode -ne 0) { throw "Instalacion fallo: $($process.ExitCode)" }
    $manifest = Get-Content -Raw -LiteralPath (Join-Path $installDir 'installer/offline_assets.json') | ConvertFrom-Json
    foreach ($asset in $manifest.assets) {
        $path = [IO.Path]::GetFullPath((Join-Path $installDir $asset.path))
        if (-not $path.StartsWith($installDir + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Ruta de activo invalida.' }
        if ((Get-FileHash -LiteralPath $path).Hash -ne $asset.sha256) { throw "Activo instalado alterado: $($asset.path)" }
    }
    $report.checks.all_installed_assets_sha256 = $true
    $report.checks.shell_sha256 = (Get-FileHash -LiteralPath (Join-Path $installDir 'egobits-desktop.exe')).Hash -eq $build.shell_sha256
    $report.checks.backend_sha256 = (Get-FileHash -LiteralPath (Join-Path $installDir 'egobits-backend.exe')).Hash -eq $build.backend_sha256
    & powershell -NoProfile -File (Join-Path $PSScriptRoot 'test_portable_backend.ps1') -Backend (Join-Path $installDir 'egobits-backend.exe') -ResourceRoot $installDir -EvidenceRoot $testRoot
    if ($LASTEXITCODE -ne 0) { throw 'Smoke del backend instalado fallo.' }
    $report.checks.installed_real_inference = $true
} finally {
    $uninstaller = Join-Path $installDir 'unins000.exe'
    if (Test-Path -LiteralPath $uninstaller) {
        $process = Start-Process -FilePath $uninstaller -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/LOG="'+$uninstallLog+'"')) -WindowStyle Hidden -Wait -PassThru
        $report.uninstall_exit = $process.ExitCode
        $report.checks.app_removed = -not (Test-Path -LiteralPath (Join-Path $installDir 'egobits-desktop.exe'))
        $report.checks.registration_removed = -not (Test-Path -LiteralPath $registry)
    }
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reportPath -Encoding UTF8
}
if ($report.install_exit -ne 0 -or $report.uninstall_exit -ne 0 -or $report.checks.Values -contains $false) { throw 'Fallo ensayo del instalador; revisar reporte.' }
Write-Host "PASS instalacion/modelo/inferencia/desinstalacion en host. No certifica VM limpia/offline: $reportPath"
