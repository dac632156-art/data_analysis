@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -u -m uvicorn main:app --host 127.0.0.1 --port 8001
