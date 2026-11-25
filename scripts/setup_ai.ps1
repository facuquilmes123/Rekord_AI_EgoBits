param(
    [ValidateSet('lite', 'compact', 'balanced', 'pro', 'none', '')]
    [string]$Profile = '',
    [ValidateSet('cpu', 'vulkan', 'cuda')]
    [string]$Engine = 'cpu',
    [switch]$List
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    throw 'Python 3.12+ is required. Install Python from https://www.python.org/downloads/ and retry.'
}

$argsList = @((Join-Path $RepoRoot 'scripts\setup_ai.py'))
if ($List) { $argsList += '--list' }
if ($Profile) { $argsList += @('--profile', $Profile, '--engine', $Engine) }

& $Python.Source @argsList
exit $LASTEXITCODE
