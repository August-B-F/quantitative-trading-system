# Skylark watchdog — ensures the FastAPI dashboard stays running.
# Runs every 5 minutes via iStock_SkylarkWatchdog scheduled task.
# If Skylark is already alive, exits immediately (< 1 second).

$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $ProjectDir

New-Item -ItemType Directory -Force -Path "logs" | Out-Null

$running = Get-CimInstance Win32_Process -Filter "Name='py.exe' OR Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*skylark_server*' }

if ($running) {
    exit 0
}

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"$timestamp Skylark not running - restarting via watchdog" |
    Out-File -Append -Encoding utf8 logs/skylark.log

& wscript.exe "scripts\skylark_hidden.vbs"

Start-Sleep -Seconds 5

$check = Get-CimInstance Win32_Process -Filter "Name='py.exe' OR Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*skylark_server*' }

if ($check) {
    "$timestamp Skylark restarted successfully (PID $($check[0].ProcessId))" |
        Out-File -Append -Encoding utf8 logs/skylark.log
} else {
    "$timestamp WARN: Skylark failed to start - check port conflicts" |
        Out-File -Append -Encoding utf8 logs/skylark.log
}
