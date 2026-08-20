@echo off
cd /d d:\数据分析项目\backend
start "" /min cmd /c "py -u -m uvicorn main:app --host 127.0.0.1 --port 8001 > %TEMP%\be_restart.log 2>&1"
