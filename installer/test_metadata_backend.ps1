param([Parameter(Mandatory=$true)][string]$Library,
      [string]$EvidenceRoot=(Join-Path $PSScriptRoot '../output/closure/release-037'))
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Library=(Resolve-Path -LiteralPath $Library).Path
$originalHash=(Get-FileHash -LiteralPath $Library -Algorithm SHA256).Hash
$run=Join-Path $EvidenceRoot ('metadata-qa-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $run | Out-Null
$copy=Join-Path $run 'collection-copy.xml'
Copy-Item -LiteralPath $Library -Destination $copy
$backend=Join-Path $root 'build/backend/egobits-backend.exe'
$version=(Get-Content -Raw -LiteralPath (Join-Path $root 'release.json') | ConvertFrom-Json).version
$token=[Guid]::NewGuid().ToString('N')+[Guid]::NewGuid().ToString('N')
$start=New-Object Diagnostics.ProcessStartInfo
$start.FileName=$backend;$start.Arguments='--serve --port 0';$start.UseShellExecute=$false;$start.CreateNoWindow=$true
$start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true
$start.EnvironmentVariables['LOCALAPPDATA']=$run
$start.EnvironmentVariables['EGB_SESSION_TOKEN']=$token
$start.EnvironmentVariables['EGB_LIBRARY_XML']=$copy
$start.EnvironmentVariables['EGB_RESOURCE_ROOT']=$root
$start.EnvironmentVariables['PATH']=Join-Path $env:SystemRoot 'System32'
foreach($key in @('PYTHONHOME','PYTHONPATH','EGB_ENERGIES_JSON')){$start.EnvironmentVariables.Remove($key)}
$process=New-Object Diagnostics.Process;$process.StartInfo=$start
$report=[ordered]@{backend_sha256=(Get-FileHash -LiteralPath $backend).Hash;checks=@{};real_settings_modified=$false;rekordbox_closed=$false;installer_test='NOT_TESTED'}
try {
    [void]$process.Start();$errors=$process.StandardError.ReadToEndAsync()
    $startup=[Diagnostics.Stopwatch]::StartNew();$port=$null
    while($startup.Elapsed.TotalSeconds -lt 45){
        $lineTask=$process.StandardOutput.ReadLineAsync()
        if(-not $lineTask.Wait(45000)){throw 'Timeout de inicio'}
        $line=$lineTask.Result
        if($null -eq $line){throw 'Backend cerrado antes de READY'}
        if($line -match '^EGB_READY:(\d+)$'){$port=[int]$Matches[1];break}
    }
    if(-not $port){throw 'Backend sin puerto verificado'}
    $base="http://127.0.0.1:$port";$headers=@{'X-EgoBits-Token'=$token}
    function Request($path,$body) {
        if($null -eq $body){return Invoke-RestMethod -Uri ($base+$path) -Headers $headers -TimeoutSec 60}
        $bytes=[Text.Encoding]::UTF8.GetBytes(($body|ConvertTo-Json -Depth 10))
        Invoke-RestMethod -Uri ($base+$path) -Headers $headers -Method Post -Body $bytes -ContentType 'application/json; charset=utf-8' -TimeoutSec 180
    }
    $status=Request '/api/status' $null
    $report.checks.version=$status.version -eq $version
    $report.checks.real_collection_copy=$status.snapshot_revision -eq $originalHash.ToLower() -and -not $status.demo
    $report.checks.audio_inactive_before=-not $status.audio_watch.active
    $timer=[Diagnostics.Stopwatch]::StartNew()
    $popup=Request '/api/history/start' @{}
    $report.activation_seconds=[Math]::Round($timer.Elapsed.TotalSeconds,3)
    if($status.rekordbox_state -eq 'open'){
      $report.checks.popup_has_candidates=$popup.display -and $popup.recommendations.Count -gt 0
      $report.checks.history_not_master=$popup.source -eq 'rekordbox_history' -and -not $popup.confirmed -and -not $popup.master_confirmed
    } else {$report.history_live_test='SKIPPED_REKORDBOX_NOT_OPEN';$report.checks.history_respects_closed=-not $popup.display}
    $settings=Request '/api/settings' $null
    $report.checks.one_click_enabled=$settings.notifications.enabled -and $settings.notifications.history_popup -and -not $settings.notifications.silenced
    $report.checks.three_default_criteria=$settings.recommendation.match_bpm -and $settings.recommendation.harmonic -and $settings.recommendation.same_genre
    $audio=Request '/api/audio/watch' $null
    $report.checks.no_audio_started=-not $audio.active
    $chat=Request '/api/chat' @{query='Recomendame canciones en vivo'}
    if($status.rekordbox_state -eq 'open'){$report.checks.chat_uses_metadata=$chat.live.source -eq 'rekordbox_history' -and $chat.recommendations.Count -gt 0 -and -not $chat.live.confirmed}
    else {$report.checks.chat_reports_unavailable=-not $chat.live.eligible}
    $ui=Invoke-WebRequest -UseBasicParsing -Uri ($base+'/') -Headers $headers -TimeoutSec 20
    $report.checks.packaged_metadata_ui=$ui.Content.Contains('metadata-recommend-start') -and $ui.Content.Contains('rec-match-bpm') -and -not $ui.Content.Contains('2 a 20')
    if([version]$version -ge [version]'0.3.8') {
        $report.checks.packaged_bulk_delete_ui=$ui.Content.Contains('btn-duplicate-delete') -and $ui.Content.Contains('50% hacia arriba')
        try {$null=Request '/api/duplicates/delete' @{token=('a'*32);confirmed=$true;source_revision=$status.snapshot_revision};$report.checks.unsigned_delete_rejected=$false}
        catch {$report.checks.unsigned_delete_rejected=[int]$_.Exception.Response.StatusCode -eq 400}
    }
    if([version]$version -ge [version]'0.3.9') {
        $report.checks.packaged_recovery_ui=$ui.Content.Contains('transactions-recover') -and $ui.Content.Contains('rekordbox-force-close')
        foreach($path in @('/api/transactions/apply','/api/transactions/restore/apply')){
          try {$null=Request $path @{token=('a'*32);confirmed=$true};throw 'Unsigned operation admitted'}
          catch {if([int]$_.Exception.Response.StatusCode -ne 400){throw};$report.checks[$path+'_unsigned_rejected']=$true}
        }
        $timer.Restart()
        $analysis=Request '/api/chat' @{query='cuales pistas me faltan analizar en rekordbox?'}
        $report.analysis_seconds=[Math]::Round($timer.Elapsed.TotalSeconds,3)
        $report.analysis=$analysis.analysis
        $report.checks.analysis_native=$analysis.analysis.source -eq 'native_readonly'
        $report.checks.analysis_direct=$analysis.answer_mode -eq 'collection_evidence' -and -not $analysis.applied
        $report.checks.analysis_ui=$ui.Content.Contains('opportunity-dialog')
        $detail=Request ('/api/opportunity?id=analysis&revision='+$status.snapshot_revision) $null
        $report.checks.analysis_detail=$detail.total -eq $analysis.analysis.total -and $detail.instructions.Length -gt 0
        $insights=Request '/api/insights' $null
        $report.checks.actionable_opportunities=@($insights.suggestions | Where-Object {$_.opportunity}).Count -gt 0
    }
    $report.reference=$popup.reference_track.title
    $report.rows=$popup.recommendations
    $report.checks.original_unchanged=(Get-FileHash -LiteralPath $Library).Hash -eq $originalHash
    $null=Request '/api/shutdown' @{}
    $report.checks.clean_exit=$process.WaitForExit(15000) -and $process.ExitCode -eq 0
    $errors.Result | Set-Content -LiteralPath (Join-Path $run 'stderr.log') -Encoding utf8
    if($report.checks.Values -contains $false){throw 'Falló un control de metadata; ver evidence.json'}
} finally {
    if($process.Id -and -not $process.HasExited){& taskkill /PID $process.Id /T /F | Out-Null}
    $report|ConvertTo-Json -Depth 15|Set-Content -LiteralPath (Join-Path $run 'evidence.json') -Encoding utf8
    $process.Dispose()
}
Write-Output "PASS metadata EXE: $run"
