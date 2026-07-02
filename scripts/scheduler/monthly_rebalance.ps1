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

# 1. Skip non-trading days (weekends / NYSE holidays).
$marketDay = py -3 -c "from src.data.utils import get_trading_calendar; import datetime; t=datetime.date.today(); print('yes' if len(get_trading_calendar(str(t),str(t)))>0 else 'no')"
if ($marketDay -ne "yes") {
    "$timestamp Not a trading day, skipping" | Out-File -Append -Encoding utf8 logs/rebalance.log
    exit 0
}

# 2. Pick up any FOMC-deferred rebalance scheduled for today.
$deferred = py -3 -c @"
import json, os, datetime
out = 'no'
p = 'logs/rebalance_log.json'
if os.path.exists(p):
    try:
        with open(p) as f: log = json.load(f)
    except Exception:
        log = None
    if isinstance(log, list) and log:
        last = log[-1]
        d = last.get('fomc_deferred_to')
        if d:
            try:
                if datetime.date.fromisoformat(d) == datetime.date.today():
                    out = 'yes'
            except ValueError:
                pass
print(out)
"@

if ($deferred -eq "yes") {
    "$timestamp Running deferred FOMC rebalance" | Out-File -Append -Encoding utf8 logs/rebalance.log
    py -3 scripts/run_rebalance.py --force --execute *>&1 |
        Out-File -Append -Encoding utf8 logs/rebalance.log
    $exitCode = $LASTEXITCODE
} else {
    py -3 scripts/run_rebalance.py --execute *>&1 |
        Out-File -Append -Encoding utf8 logs/rebalance.log
    $exitCode = $LASTEXITCODE
}

if ($exitCode -eq 2) {
    "$timestamp Data unavailable, will retry tomorrow" | Out-File -Append -Encoding utf8 logs/alerts.log
    try {
        py -3 -c "from src.risk.notify import send_alert; send_alert('Rebalance deferred: data unavailable', 'WARNING')" *>&1 |
            Out-File -Append -Encoding utf8 logs/alerts.log
    } catch { }
} elseif ($exitCode -eq 3) {
    "$timestamp Rebalance blocked: another instance running (exit 3)" | Out-File -Append -Encoding utf8 logs/alerts.log
    try {
        py -3 -c "from src.risk.notify import send_alert; send_alert('Rebalance blocked: another instance running', 'ALERT')" *>&1 |
            Out-File -Append -Encoding utf8 logs/alerts.log
    } catch { }
} elseif ($exitCode -ne 0) {
    "$timestamp Rebalance FAILED (exit $exitCode)" | Out-File -Append -Encoding utf8 logs/alerts.log
    try {
        py -3 -c "from src.risk.notify import send_alert; send_alert('Rebalance FAILED', 'ALERT')" *>&1 |
            Out-File -Append -Encoding utf8 logs/alerts.log
    } catch { }
}

exit $exitCode
