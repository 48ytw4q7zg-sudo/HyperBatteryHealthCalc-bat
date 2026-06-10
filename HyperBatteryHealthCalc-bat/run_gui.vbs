Set ws = CreateObject("Wscript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
script_dir = fso.GetParentFolderName(WScript.ScriptFullName)

On Error Resume Next
ws.Run "pythonw """ & script_dir & "\battery_gui.py""", 0, False
If Err.Number <> 0 Then
    ws.Run "python """ & script_dir & "\battery_gui.py""", 1, False
    If Err.Number <> 0 Then
        MsgBox "Python/tkinter not found. Please install Python 3.7+", 48, "Error"
    End If
End If
On Error GoTo 0
