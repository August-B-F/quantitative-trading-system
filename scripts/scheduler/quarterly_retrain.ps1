param(
    [string]$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..\.."))
)

$ErrorActionPreference = "Continue"

# Gate: only run on the 1st of Jan/Apr/Jul/Oct.
# Task Scheduler fires this daily; we exit fast on non-retrain days.
$month = (Get-Date).Month
$day = (Get-Date).Day
if ($month -notin @(1,4,7,10) -or $day -ne 1) {
    exit 0
}

Set-Location $ProjectDir
New-Item -ItemType Directory -Force -Path "logs" | Out-Null

if (Test-Path .env) {
    Get-Content .env | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), "Process")
        }
    }
}

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"$timestamp Quarterly retrain start" | Out-File -Append -Encoding utf8 logs/retrain.log
py -3 scripts/run_retrain.py *>&1 | Out-File -Append -Encoding utf8 logs/retrain.log
$exitCode = $LASTEXITCODE
"$timestamp Quarterly retrain end (exit $exitCode)" | Out-File -Append -Encoding utf8 logs/retrain.log
exit $exitCode
