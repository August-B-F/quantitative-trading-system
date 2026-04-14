#Requires -RunAsAdministrator
$ErrorActionPreference = "Stop"

$tasks = Get-ScheduledTask | Where-Object TaskName -like "iStock_*"
if (-not $tasks) {
    Write-Host "No iStock tasks found."
    exit 0
}

$tasks | Unregister-ScheduledTask -Confirm:$false
Write-Host "All iStock tasks removed."
