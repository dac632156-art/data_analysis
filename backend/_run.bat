@echo off
cd /d d:\数据分析项目\backend
py -u -m uvicorn main:app --host 127.0.0.1 --port 8001
