param([string]$BundleRoot = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = 'Stop'
$bundleDir = (Resolve-Path -LiteralPath $BundleRoot).Path
$manifest = Get-Content -Raw -LiteralPath (Join-Path $bundleDir 'installer/offline_assets.json') | ConvertFrom-Json
$models = @($manifest.assets | Where-Object { $_.path -like 'assets/models/*.gguf' })
if ($models.Count -ne 1) { throw 'Se requiere exactamente un modelo declarado.' }
$row = $models[0]
if ($row.path -notmatch '^assets/models/[A-Za-z0-9_.-]+\.gguf$' -or $row.sha256 -notmatch '^[a-fA-F0-9]{64}$') { throw 'Manifiesto de modelo inválido.' }
$source = Join-Path $bundleDir $row.path
if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $row.sha256) { throw 'Hash del modelo fuente inválido.' }
$modelDir = Join-Path $env:LOCALAPPDATA 'Rekord AI EgoBits/assets/models'
New-Item -ItemType Directory -Path $modelDir -Force | Out-Null
$target = Join-Path $modelDir (Split-Path -Leaf $row.path)
if (Test-Path -LiteralPath $target) {
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -eq $row.sha256) {
        Write-Host 'El modelo verificado ya está instalado.'
        exit 0
    }
    throw 'Existe otro modelo con el mismo nombre. Conservado; movelo a un respaldo antes de reinstalar.'
}
$temporary = Join-Path $modelDir ('model-' + [guid]::NewGuid().ToString() + '.tmp')
try {
    Copy-Item -LiteralPath $source -Destination $temporary
    if ((Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash -ne $row.sha256) { throw 'La copia del modelo no coincide.' }
    Move-Item -LiteralPath $temporary -Destination $target
} finally {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary }
}
Write-Host 'Modelo instalado y verificado sin conexión.'
