@echo off
set PYTHONHTTPSVERIFY=0
"C:\Users\26540\.workbuddy\binaries\python\versions\3.14.3\python.exe" -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r "d:\数据分析项目\backend\requirements.txt" --log "d:\数据分析项目\backend\_pip_install2.log"
echo DONE_PIP > "d:\数据分析项目\backend\_pip_done.flag"
