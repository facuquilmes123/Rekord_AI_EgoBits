param([Parameter(Mandatory=$true)][string]$AppPath)
$ErrorActionPreference = 'Stop'
$appFile = (Resolve-Path -LiteralPath $AppPath).Path
if ([IO.Path]::GetExtension($appFile) -ne '.exe') { throw 'Aplicación inválida.' }
$watchMutex = New-Object System.Threading.Mutex($false, 'Local\RekordAIEgoBitsWatcher')
if (-not $watchMutex.WaitOne(0)) { exit 0 }
try {
    $previousOpen = $false
    while (Test-Path -LiteralPath $appFile) {
        $isOpen = @(Get-Process -Name rekordbox -ErrorAction SilentlyContinue).Count -gt 0
        $setupRunning = $false
        try {
            $setupMutex = [Threading.Mutex]::OpenExisting('Local\RekordAISetup')
            $setupRunning = $true
            $setupMutex.Dispose()
        } catch [Threading.WaitHandleCannotBeOpenedException] { }
        if ($setupRunning) { Start-Sleep -Seconds 3; continue }
        if ($isOpen -and -not $previousOpen) {
            $name = [IO.Path]::GetFileNameWithoutExtension($appFile)
            if (@(Get-Process -Name $name -ErrorAction SilentlyContinue).Count -eq 0) {
                Start-Process -FilePath $appFile -WindowStyle Hidden
            }
        }
        $previousOpen = $isOpen
        Start-Sleep -Seconds 3
    }
} finally { $watchMutex.ReleaseMutex(); $watchMutex.Dispose() }
