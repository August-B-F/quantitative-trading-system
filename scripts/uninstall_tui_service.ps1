# Remove the QTS-TUI scheduled task.
#   powershell -ExecutionPolicy Bypass -File scripts\uninstall_tui_service.ps1

$TaskName = "QTS-TUI"

schtasks /Query /TN $TaskName 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Task '$TaskName' is not registered. Nothing to do."
    exit 0
}

schtasks /End    /TN $TaskName 2>$null | Out-Null
schtasks /Delete /TN $TaskName /F
Write-Host "Removed scheduled task '$TaskName'."
