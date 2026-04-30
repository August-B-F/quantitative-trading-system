# Register the QTS-TUI Scheduled Task: starts the TUI web server
# at user logon, restarts on failure, runs hidden, no time limit.
#
# Run from an elevated PowerShell:
#   powershell -ExecutionPolicy Bypass -File scripts\install_tui_service.ps1
#
# Uninstall: scripts\uninstall_tui_service.ps1

$ErrorActionPreference = "Stop"

$TaskName = "QTS-TUI"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = "py"
$Script = "scripts\tui.py"
$Args = "$Script --serve --host 0.0.0.0 --port 8765"

Write-Host "Installing scheduled task '$TaskName'"
Write-Host "  project root : $ProjectRoot"
Write-Host "  command      : $Python $Args"

# Remove any existing copy so this script is idempotent.
schtasks /Query /TN $TaskName 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  removing existing task ..."
    schtasks /Delete /TN $TaskName /F | Out-Null
}

$Action    = New-ScheduledTaskAction `
                -Execute $Python `
                -Argument $Args `
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
    -Description "QTS read-only TUI web server (textual-serve, port 8765)" | Out-Null

Write-Host "Starting task immediately ..."
Start-ScheduledTask -TaskName $TaskName

Write-Host ""
Write-Host "Done. Verify with:"
Write-Host "  schtasks /Query /TN $TaskName /V /FO LIST"
Write-Host ""
Write-Host "Firewall rule (run elevated, restricts to WireGuard interface):"
Write-Host '  netsh advfirewall firewall add rule name="QTS-TUI 8765 (WG)" `'
Write-Host '         dir=in action=allow protocol=TCP localport=8765 `'
Write-Host '         interfacetype=lan profile=private'
Write-Host ""
Write-Host "Set an auth token (per-user env var, persists across reboots):"
Write-Host '  setx TUI_TOKEN "<random-string>"'
