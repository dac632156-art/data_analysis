@echo off
cd /d d:\数据分析项目
py -m uvicorn backend.main:app --host 0.0.0.0 --port 8001 >> %TEMP%\be.log 2>&1
