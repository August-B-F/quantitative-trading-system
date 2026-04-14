# Register the Skylark Scheduled Task: starts the FastAPI server at user
# logon, restarts on failure, runs hidden, no time limit.
#
#   powershell -ExecutionPolicy Bypass -File scripts\install_skylark_service.ps1
#
# Uninstall: scripts\uninstall_skylark_service.ps1

$ErrorActionPreference = "Stop"

$TaskName    = "Skylark"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python      = "py"

Write-Host "Installing scheduled task '$TaskName'"
Write-Host "  project root : $ProjectRoot"
Write-Host "  command      : $Python scripts\skylark_server.py"

# Also remove the legacy QTS-Web task if present (superseded by Skylark).
foreach ($stale in @("QTS-Web", $TaskName)) {
    if (Get-ScheduledTask -TaskName $stale -ErrorAction SilentlyContinue) {
        Write-Host "  removing existing task '$stale' ..."
        Stop-ScheduledTask  -TaskName $stale -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $stale -Confirm:$false
    }
}

$Action    = New-ScheduledTaskAction `
                -Execute $Python `
                -Argument "scripts\skylark_server.py" `
                -WorkingDirectory $ProjectRoot

$Trigger   = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

$Settings  = New-ScheduledTaskSettingsSet `
                -AllowStartIfOnBatteries `
                -DontStopIfGoingOnBatteries `
                -StartWhenAvailable `
                -RestartCount 999 `
                -RestartInterval (New-TimeSpan -Minutes 1) `
                -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
                -Hidden

$Principal = New-ScheduledTaskPrincipal `
                -UserId $env:USERNAME `
                -LogonType Interactive `
                -RunLevel Limited

Register-ScheduledTask `
    -TaskName    $TaskName `
    -Action      $Action `
    -Trigger     $Trigger `
    -Settings    $Settings `
    -Principal   $Principal `
    -Description "Skylark - 9-strategy horse race UI (port 8765, ZeroTier-bound)" | Out-Null

Write-Host "Starting task immediately ..."
Start-ScheduledTask -TaskName $TaskName

Write-Host ""
Write-Host "Done. Useful commands:"
Write-Host "  Stop    :  Stop-ScheduledTask -TaskName $TaskName"
Write-Host "  Start   :  Start-ScheduledTask -TaskName $TaskName"
Write-Host "  Status  :  Get-ScheduledTask  -TaskName $TaskName | Get-ScheduledTaskInfo"
