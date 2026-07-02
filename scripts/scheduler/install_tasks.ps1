param(
    [string]$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
)

$ErrorActionPreference = "Stop"

$schedDir = Join-Path $ProjectDir "scripts\scheduler"

function New-IStockTask {
    param(
        [Parameter(Mandatory)] [string]$Name,
        [Parameter(Mandatory)] [string]$Script,
        [Parameter(Mandatory)] $Trigger,
        [string]$Description
    )

    $action = New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$schedDir\$Script`"" `
        -WorkingDirectory $ProjectDir

    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -WakeToRun `
        -ExecutionTimeLimit (New-TimeSpan -Seconds 0)

    Register-ScheduledTask `
        -TaskName "iStock_$Name" `
        -Action $action `
        -Trigger $Trigger `
        -Settings $settings `
        -Description "iStock trading system: $Description" `
        -Force | Out-Null

    Write-Host "Created task: iStock_$Name"
}

# NIGHTLY DATA DOWNLOAD — 22:00 Stockholm Mon-Fri (≈ 16:00 ET, after market close)
$trigger = New-ScheduledTaskTrigger `
    -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At "22:00"
New-IStockTask -Name "DailyDownload" -Script "daily_download.ps1" `
    -Trigger $trigger -Description "nightly data download (Mon-Fri 22:00)"

# DAILY HEALTH CHECK — 23:30 Stockholm Mon-Fri (≈ 17:30 ET)
$trigger = New-ScheduledTaskTrigger `
    -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At "23:30"
New-IStockTask -Name "DailyHealth" -Script "daily_health.ps1" `
    -Trigger $trigger -Description "daily health check (Mon-Fri 23:30)"

# MONTHLY REBALANCE — 04:15 Stockholm Mon-Sat (≈ 22:15 ET previous day)
# Monday included so a Monday month-end (e.g. 2026-08-31) is not silently
# skipped; the script gates on trading day + month-end internally, so the
# extra weekday runs are no-ops.
$trigger = New-ScheduledTaskTrigger `
    -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday,Saturday -At "04:15"
New-IStockTask -Name "MonthlyRebalance" -Script "monthly_rebalance.ps1" `
    -Trigger $trigger -Description "monthly rebalance (Mon-Sat 04:15, month-end gate internal)"

# QUARTERLY RETRAIN — 06:00 daily; script exits fast unless 1st of Jan/Apr/Jul/Oct.
# Task Scheduler has no native "1st of specific months" trigger.
$trigger = New-ScheduledTaskTrigger -Daily -At "06:00"
New-IStockTask -Name "QuarterlyRetrain" -Script "quarterly_retrain.ps1" `
    -Trigger $trigger -Description "quarterly retrain (daily 06:00, quarter-boundary gate internal)"

Write-Host ""
Write-Host "All tasks installed. Verify with:"
Write-Host "  Get-ScheduledTask | Where-Object TaskName -like 'iStock_*'"
