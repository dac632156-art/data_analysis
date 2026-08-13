@echo off
cd /d d:\数据分析项目\backend
echo STARTED > _started.txt
py -u -m uvicorn main:app --host 127.0.0.1 --port 8001 >> _restart_out.txt 2>&1
echo DONE_EXIT >> _restart_out.txt
