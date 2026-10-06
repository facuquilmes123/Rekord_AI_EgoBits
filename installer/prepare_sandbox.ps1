param([Parameter(Mandatory=$true)][string]$Kit)
$ErrorActionPreference = 'Stop'
$Kit = (Resolve-Path -LiteralPath $Kit).Path
if (-not (Test-Path -LiteralPath (Join-Path $Kit 'egobits-backend.exe'))) { throw 'Seleccionar el kit ejecutable extraido.' }
$evidence = Join-Path $Kit 'sandbox-evidence'
New-Item -ItemType Directory -Force -Path $evidence | Out-Null
$escapeKit = [Security.SecurityElement]::Escape($Kit)
$escapeEvidence = [Security.SecurityElement]::Escape($evidence)
$configuration = @"
<Configuration>
  <Networking>Disable</Networking>
  <MappedFolders>
    <MappedFolder><HostFolder>$escapeKit</HostFolder><SandboxFolder>C:\EgoBitsQA</SandboxFolder><ReadOnly>true</ReadOnly></MappedFolder>
    <MappedFolder><HostFolder>$escapeEvidence</HostFolder><SandboxFolder>C:\EgoBitsEvidence</SandboxFolder><ReadOnly>false</ReadOnly></MappedFolder>
  </MappedFolders>
  <LogonCommand><Command>powershell.exe -NoProfile -File C:\EgoBitsQA\installer\test_portable_backend.ps1 -Backend C:\EgoBitsQA\egobits-backend.exe -ResourceRoot C:\EgoBitsQA -RequireOffline -EvidenceRoot C:\EgoBitsEvidence</Command></LogonCommand>
</Configuration>
"@
$target = Join-Path $Kit 'EgoBits-offline.wsb'
$configuration | Set-Content -LiteralPath $target -Encoding UTF8
Write-Host "Configuracion preparada: $target. Requiere Windows Sandbox habilitado. No es una prueba de instalacion Tauri."
