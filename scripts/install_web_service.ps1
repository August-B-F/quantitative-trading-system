# Register the QTS-Web Scheduled Task: starts the FastAPI web server
# at user logon, restarts on failure, runs hidden, no time limit.
#
# Run from a normal PowerShell (no elevation needed for a per-user task):
#   powershell -ExecutionPolicy Bypass -File scripts\install_web_service.ps1
#
# Uninstall: scripts\uninstall_web_service.ps1

$ErrorActionPreference = "Stop"

$TaskName = "QTS-Web"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = "py"

Write-Host "Installing scheduled task '$TaskName'"
Write-Host "  project root : $ProjectRoot"
Write-Host "  command      : $Python scripts\web_server.py"

# Idempotent: remove existing task if present.
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Write-Host "  removing existing task ..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$Action    = New-ScheduledTaskAction `
                -Execute $Python `
                -Argument "scripts\web_server.py" `
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
    -TaskName  $TaskName `
    -Action    $Action `
    -Trigger   $Trigger `
    -Settings  $Settings `
    -Principal $Principal `
    -Description "QTS FastAPI web server (iStock UI, port 8000, WireGuard-bound)" | Out-Null

Write-Host "Starting task immediately ..."
Start-ScheduledTask -TaskName $TaskName

Write-Host ""
Write-Host "Done. Useful commands:"
Write-Host "  Stop    :  Stop-ScheduledTask -TaskName $TaskName"
Write-Host "  Start   :  Start-ScheduledTask -TaskName $TaskName"
Write-Host "  Status  :  Get-ScheduledTask  -TaskName $TaskName | Get-ScheduledTaskInfo"
Write-Host "  Logs    :  Get-WinEvent -LogName 'Microsoft-Windows-TaskScheduler/Operational' | Where-Object {`$_.Message -like '*$TaskName*'} | Select-Object -First 20"
Write-Host ""
Write-Host "The server binds to the WireGuard interface (auto-detected via ipconfig)."
Write-Host "If a firewall rule is needed:"
Write-Host '  netsh advfirewall firewall add rule name="QTS-Web 8000 (WG)" `'
Write-Host '         dir=in action=allow protocol=TCP localport=8000 profile=private'
