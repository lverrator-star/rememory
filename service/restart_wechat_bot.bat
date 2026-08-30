@echo off
chcp 65001 >nul
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'wechat_bot' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
timeout /t 2 /nobreak >nul
wscript.exe "%~dp0start_wechat_bot.vbs"
echo WeChat bot restarted.
