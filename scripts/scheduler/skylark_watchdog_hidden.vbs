' Launch the Skylark watchdog with no visible window.
' Used by the iStock_SkylarkWatchdog scheduled task.
Set objFS = CreateObject("Scripting.FileSystemObject")
Set objShell = CreateObject("WScript.Shell")
projPath = objFS.GetParentFolderName(objFS.GetParentFolderName(objFS.GetParentFolderName(WScript.ScriptFullName)))
objShell.CurrentDirectory = projPath
objShell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\scheduler\skylark_watchdog.ps1", 0, True
