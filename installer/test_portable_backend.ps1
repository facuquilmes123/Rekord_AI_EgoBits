param(
    [string]$Backend = (Join-Path $PSScriptRoot '../build/backend/egobits-backend.exe'),
    [string]$ResourceRoot = (Join-Path $PSScriptRoot '..'),
    [switch]$RequireOffline,
    [string]$EvidenceRoot = $env:TEMP,
    [string]$Fixture = (Join-Path $PSScriptRoot '../prototype/examples/library.xml')
)
$ErrorActionPreference = 'Stop'
$Backend = (Resolve-Path -LiteralPath $Backend).Path
$ResourceRoot = (Resolve-Path -LiteralPath $ResourceRoot).Path
$adapters = @(Get-NetAdapter -ErrorAction Stop | Where-Object Status -eq 'Up')
if ($RequireOffline -and $adapters.Count -gt 0) { throw 'Deshabilitar red en la VM antes de afirmar prueba offline.' }
$run = Join-Path $EvidenceRoot ('egobits-qa-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $run | Out-Null
$Fixture = (Resolve-Path -LiteralPath $Fixture).Path
$fixtureCopy = Join-Path $run 'qa-library.xml'
Copy-Item -LiteralPath $Fixture -Destination $fixtureCopy
$fixtureHash = (Get-FileHash -LiteralPath $fixtureCopy -Algorithm SHA256).Hash
$releaseContract = Join-Path $ResourceRoot 'release.json'
if (-not (Test-Path -LiteralPath $releaseContract)) { $releaseContract = Join-Path $ResourceRoot 'installer/release.json' }
$expectedVersion = (Get-Content -Raw -LiteralPath $releaseContract | ConvertFrom-Json).version
$random = New-Object byte[] 32
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($random) } finally { $rng.Dispose() }
$token = [BitConverter]::ToString($random).Replace('-', '')
$start = New-Object Diagnostics.ProcessStartInfo
$start.FileName = $Backend
$start.Arguments = '--serve --port 0'
$start.UseShellExecute = $false
$start.CreateNoWindow = $true
$start.RedirectStandardOutput = $true
$start.RedirectStandardError = $true
$start.EnvironmentVariables['LOCALAPPDATA'] = $run
$start.EnvironmentVariables['PATH'] = Join-Path $env:SystemRoot 'System32'
$start.EnvironmentVariables['EGB_SESSION_TOKEN'] = $token
$start.EnvironmentVariables['EGB_RESOURCE_ROOT'] = $ResourceRoot
foreach ($key in @('PYTHONHOME','PYTHONPATH','EGB_LIBRARY_XML','EGB_ENERGIES_JSON')) { $start.EnvironmentVariables.Remove($key) }
$start.EnvironmentVariables['EGB_LIBRARY_XML'] = $fixtureCopy
$process = New-Object Diagnostics.Process
$process.StartInfo = $start
$report = [ordered]@{backend_sha256=(Get-FileHash -LiteralPath $Backend).Hash;network_disabled=($adapters.Count -eq 0);os=[Environment]::OSVersion.VersionString;checks=@{};installer_test='NOT_TESTED';evidence=$run}
try {
    [void]$process.Start()
    $errorTask = $process.StandardError.ReadToEndAsync()
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $port = $null
    while ($timer.Elapsed.TotalSeconds -lt 45) {
        $lineTask = $process.StandardOutput.ReadLineAsync()
        if (-not $lineTask.Wait(45000)) { throw 'Timeout de inicio.' }
        $line = $lineTask.Result
        if ($null -eq $line) { throw 'Backend cerrado sin READY.' }
        if ($line -match '^EGB_READY:(\d+)$') { $port = [int]$Matches[1]; break }
    }
    if (-not $port) { throw 'Backend sin puerto verificado.' }
    $report.startup_seconds = [Math]::Round($timer.Elapsed.TotalSeconds, 2)
    $base = "http://127.0.0.1:$port"
    $headers = @{'X-EgoBits-Token'=$token}
    function Request([string]$Path, $Body) {
        if ($null -eq $Body) { return Invoke-RestMethod -Uri ($base+$Path) -Headers $headers -TimeoutSec 180 }
        $bytes = [Text.Encoding]::UTF8.GetBytes(($Body | ConvertTo-Json -Depth 20))
        Invoke-RestMethod -Uri ($base+$Path) -Method Post -Body $bytes -ContentType 'application/json; charset=utf-8' -Headers $headers -TimeoutSec 180
    }
    $status = Request '/api/status' $null
    $report.checks.fixture_loaded = $status.snapshot_revision -eq $fixtureHash.ToLower()
    $report.checks.backend_version = $status.version -eq $expectedVersion
    $report.version = $status.version
    $workspace = Invoke-WebRequest -UseBasicParsing -Uri ($base+'/workspace.js') -Headers $headers -TimeoutSec 20
    $popup = Invoke-WebRequest -UseBasicParsing -Uri ($base+'/live-popup.js') -Headers $headers -TimeoutSec 20
    $report.checks.packaged_native_confirmation_ui = $workspace.Content.Contains('approve_native_operation')
    $report.checks.packaged_popup_drag_ui = $popup.Content.Contains('drag_collection_track')
    $timer.Restart()
    $chat = Request '/api/chat' @{query='¿Hay canciones en común entre ROOT/X y ROOT/Y?'}
    $report.comparison_seconds = [Math]::Round($timer.Elapsed.TotalSeconds, 2)
    $report.checks.typed_comparison = $chat.intent.action -eq 'playlist.compare' -and $chat.comparison.common_count -eq 1
    $timer.Restart()
    $answer = Request '/api/chat' @{query='¿Qué estrategia usarías para un set largo con apertura tranquila y cierre intenso?'}
    $report.inference_seconds = [Math]::Round($timer.Elapsed.TotalSeconds, 2)
    $report.checks.real_llm = (Request '/api/status' $null).llm.state -eq 'ready'
    $report.checks.local_conversation = -not [string]::IsNullOrWhiteSpace($answer.response) -and $answer.answer_mode -ne 'unavailable'
    $plan = Request '/api/plan' @{playlists=@('ROOT/X','ROOT/Y');count=4}
    $export = Request '/api/export' @{result=$plan;name='Ensayo ñ 東京';target_path=(Join-Path $run 'export.xml')}
    $report.checks.xml = Test-Path -LiteralPath $export.exported_file
    $report.checks.fixture_preserved = (Get-FileHash -LiteralPath $fixtureCopy -Algorithm SHA256).Hash -eq $fixtureHash
    $report.checks.live_blocked = -not (Request '/api/live-suggestion' $null).confirmed
    $null = Request '/api/shutdown' @{}
    if (-not $process.WaitForExit(15000)) { throw 'No cerró el backend.' }
    $report.checks.clean_exit = $process.ExitCode -eq 0
    $errorTask.Result | Set-Content -LiteralPath (Join-Path $run 'backend-stderr.log') -Encoding UTF8
    if ($report.checks.Values -contains $false) { throw 'Falló un control; revisar evidence.json.' }
} finally {
    if ($process.Id -and -not $process.HasExited) { & taskkill /PID $process.Id /T /F | Out-Null }
    $report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $run 'evidence.json') -Encoding UTF8
    $process.Dispose()
}
Write-Host "PASS backend real. Evidencia: $run"
