@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Set to your Python path, or leave as "python" if it's on PATH
set PYTHON=python
if not exist logs mkdir logs
%PYTHON% -u -X utf8 wechat_bot.py >> "logs\wechat_bot.log" 2>&1
