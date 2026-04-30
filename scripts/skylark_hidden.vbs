' Launch Skylark FastAPI server with no console window.
' Used by the 'Skylark' scheduled task — keeps the server running in the
' background without popping any visible window. Closing your terminal
' has no effect on the server.
Set objFS = CreateObject("Scripting.FileSystemObject")
Set objShell = CreateObject("WScript.Shell")
projPath = objFS.GetParentFolderName(objFS.GetParentFolderName(WScript.ScriptFullName))
objShell.CurrentDirectory = projPath
' Run(cmd, windowStyle=0 hidden, waitOnReturn=False)
objShell.Run "py scripts\skylark_server.py", 0, False
