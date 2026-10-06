$ErrorActionPreference = 'Stop'
$rootDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$bootstrap = Join-Path $rootDir 'build/toolchain/vs_BuildTools.exe'
if (-not [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Abrí PowerShell como administrador y ejecutá este mismo script. MSVC/Windows SDK requieren instalación elevada.'
}
$signature = Get-AuthenticodeSignature -LiteralPath $bootstrap
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Microsoft Corporation') { throw 'Firma Microsoft inválida.' }
if (Get-Process -Name vs_BuildTools,vs_setup_bootstrapper -ErrorAction SilentlyContinue) {
    Write-Host 'La instalacion de Build Tools ya esta en curso. No se inicia otra instancia.'
    Write-Host 'Conserva abierta la ventana original hasta que termine. Logs: %TEMP%\dd_setup_*.log'
    return
}
Write-Host 'Preparando herramientas SOLO para desarrollar/compilar EgoBits. Los usuarios finales no necesitan este script.'
Write-Host 'Se abrira el progreso de Microsoft Visual Studio Build Tools. Puede tardar varios minutos.'
$process = Start-Process -FilePath $bootstrap -WindowStyle Normal -ArgumentList '--passive --wait --norestart --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended --addProductLang en-US' -PassThru
while (-not $process.WaitForExit(15000)) {
    Write-Host ('Instalacion en curso... ' + (Get-Date -Format 'HH:mm:ss'))
}
if ($process.ExitCode -notin @(0,3010)) { throw "Build Tools falló: $($process.ExitCode). Revisá los logs dd_setup de TEMP." }
Write-Host "Build Tools finalizó: $($process.ExitCode). 3010 indica reinicio pendiente."
