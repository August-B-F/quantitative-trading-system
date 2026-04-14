# Remove the QTS-Web Scheduled Task.
#   powershell -ExecutionPolicy Bypass -File scripts\uninstall_web_service.ps1

$ErrorActionPreference = "Stop"
$TaskName = "QTS-Web"

schtasks /Query /TN $TaskName 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Task '$TaskName' is not registered. Nothing to do."
    exit 0
}

Write-Host "Stopping task '$TaskName' (if running) ..."
Stop-ScheduledTask -TaskName $TaskName 2>$null

Write-Host "Removing task '$TaskName' ..."
schtasks /Delete /TN $TaskName /F | Out-Null

Write-Host "Done."
