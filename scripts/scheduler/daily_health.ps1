param(
    [string]$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..\.."))
)

$ErrorActionPreference = "Continue"
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

# run_health_check.py appends to logs/health_check.log itself — do NOT
# also pipe its output through Out-File (Windows file-lock conflict).
py -3 scripts/run_health_check.py --probe-sources | Out-Null
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    exit 0
}

"$timestamp ALERT: health check exit=$exitCode" |
    Out-File -Append -Encoding utf8 logs/alerts.log
py -3 -c "from src.risk.notify import send_alert; send_alert('Health check ALERT', 'ALERT')" *>&1 |
    Out-File -Append -Encoding utf8 logs/alerts.log
exit $exitCode
