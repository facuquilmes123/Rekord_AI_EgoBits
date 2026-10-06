param(
    [string]$Backend = (Join-Path $PSScriptRoot '../build/backend/egobits-backend.exe'),
    [string]$Fixture = (Join-Path $PSScriptRoot '../output/closure/bridge-fixture-v2')
)
$ErrorActionPreference = 'Stop'
$Backend = (Resolve-Path -LiteralPath $Backend).Path
$Fixture = (Resolve-Path -LiteralPath $Fixture).Path
$manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $Fixture 'fixture-hashes.json') | ConvertFrom-Json
foreach ($entry in $manifest.PSObject.Properties) {
    if ((Get-FileHash -LiteralPath (Join-Path $Fixture $entry.Name) -Algorithm SHA256).Hash -ne $entry.Value) { throw "Fixture alterado: $($entry.Name)" }
}
$run = Join-Path $Fixture ('run-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $run | Out-Null
$document = New-Object System.Xml.XmlDocument
$document.Load((Join-Path $Fixture 'template.xml'))
foreach ($track in $document.DJ_PLAYLISTS.COLLECTION.TRACK) {
    $oldUri = [Uri]$track.Location
    $filename = [IO.Path]::GetFileName($oldUri.LocalPath)
    $newUri = [Uri](Join-Path $Fixture $filename)
    $track.SetAttribute('Location', $newUri.AbsoluteUri.Replace('file:///', 'file://localhost/'))
}
$source = Join-Path $run 'source.xml'
$destination = Join-Path $run 'export.xml'
$settings = New-Object System.Xml.XmlWriterSettings
$settings.Encoding = New-Object System.Text.UTF8Encoding($false)
$writer = [Xml.XmlWriter]::Create($source, $settings)
try { $document.Save($writer) } finally { $writer.Dispose() }
$before = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
$oldPythonEncoding = $env:PYTHONIOENCODING
try {
    $env:PYTHONIOENCODING = 'utf-8'
    & $Backend --xml $source --playlist ROOT/Ensayo --count 3 --name 'EgoBits Bridge QA' --out $destination > (Join-Path $run 'export-log.json')
    if ($LASTEXITCODE -ne 0) { throw 'Falló exportación del backend real.' }
} finally { $env:PYTHONIOENCODING = $oldPythonEncoding }
$after = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
if ($before -ne $after) { throw 'Se modificó el XML fuente.' }
$export = New-Object System.Xml.XmlDocument
$export.Load($destination)
foreach ($track in $document.DJ_PLAYLISTS.COLLECTION.TRACK) {
    $result = $export.SelectSingleNode("//COLLECTION/TRACK[@TrackID='$($track.TrackID)']")
    if (-not $result -or $track.TEMPO.OuterXml -ne $result.TEMPO.OuterXml -or $track.POSITION_MARK.OuterXml -ne $result.POSITION_MARK.OuterXml) { throw 'TEMPO o POSITION_MARK no coincide.' }
    $localUri = [Uri]$result.Location.Replace('file://localhost/', 'file:///')
    if (-not (Test-Path -LiteralPath $localUri.LocalPath)) { throw 'Audio no localizable.' }
}
$order = @($export.SelectNodes("//PLAYLISTS//NODE[@Type='1']/TRACK") | ForEach-Object { $_.Key }) -join ','
if ($order -ne '1,2,3') { throw "Orden inesperado: $order" }
[ordered]@{source=$source;export=$destination;source_before=$before;source_after=$after;export_sha256=(Get-FileHash -LiteralPath $destination).Hash;backend_sha256=(Get-FileHash -LiteralPath $Backend).Hash;structural_checks='PASS';rekordbox_import='NOT_TESTED';expected_order=@('1','2','3')} | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $run 'evidence.json')
Write-Host "PASS estructural. Importacion real pendiente. XML: $destination"
