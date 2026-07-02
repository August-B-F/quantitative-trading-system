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

# Skip weekends — no new market data.
$dow = (Get-Date).DayOfWeek
if ($dow -eq "Saturday" -or $dow -eq "Sunday") {
    "$timestamp Weekend, skipping data download" | Out-File -Append -Encoding utf8 logs/download.log
    exit 0
}

"$timestamp Starting nightly data download" | Out-File -Append -Encoding utf8 logs/download.log

# 1. Yahoo prices
py -3 scripts/phase1_download.py *>&1 |
    Out-File -Append -Encoding utf8 logs/download.log
$priceExit = $LASTEXITCODE

# 2. FRED macro
py -3 scripts/phase1_fred.py *>&1 |
    Out-File -Append -Encoding utf8 logs/download.log
$fredExit = $LASTEXITCODE

# 3. Feature integration + health
py -3 scripts/phase3_integrate_and_health.py *>&1 |
    Out-File -Append -Encoding utf8 logs/download.log
$intExit = $LASTEXITCODE

# 4. Freshness assert - returns_63d.parquet is what live signals consume;
#    if it did not advance, the pipeline "succeeded" without new signal data.
$fresh = py -3 -c "import datetime; import pandas as pd; from src.data.utils import get_trading_calendar; last = pd.Timestamp(pd.read_parquet('data/features/price/returns_63d.parquet').index.max()).normalize(); today = pd.Timestamp(datetime.date.today()); cal = get_trading_calendar(str(last.date()), str(today.date())); gap = int((cal > last).sum()); print(('stale' if gap > 3 else 'fresh') + ' ' + str(gap) + 'td, last ' + str(last.date()))"
$freshExit = $LASTEXITCODE

$timestamp2 = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

if ($priceExit -ne 0 -or $fredExit -ne 0 -or $intExit -ne 0) {
    "$timestamp2 Download pipeline partial failure: prices=$priceExit fred=$fredExit integrate=$intExit" |
        Out-File -Append -Encoding utf8 logs/download.log
    "$timestamp2 ALERT: data download exit prices=$priceExit fred=$fredExit integrate=$intExit" |
        Out-File -Append -Encoding utf8 logs/alerts.log
    exit 1
}

if ($freshExit -ne 0 -or "$fresh" -like "stale*" -or [string]::IsNullOrWhiteSpace("$fresh")) {
    "$timestamp2 Freshness assert FAILED: returns_63d $fresh (exit $freshExit)" |
        Out-File -Append -Encoding utf8 logs/download.log
    "$timestamp2 ALERT: returns_63d.parquet stale ($fresh) - live signals not advancing" |
        Out-File -Append -Encoding utf8 logs/alerts.log
    exit 1
}

"$timestamp2 Download pipeline completed successfully (returns_63d $fresh)" |
    Out-File -Append -Encoding utf8 logs/download.log
exit 0
