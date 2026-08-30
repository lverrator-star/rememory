Set fso = CreateObject("Scripting.FileSystemObject")
Set ws = CreateObject("WScript.Shell")
bat = fso.GetParentFolderName(WScript.ScriptFullName) & "\start_wechat_bot.bat"
ws.Run """" & bat & """", 0, False
