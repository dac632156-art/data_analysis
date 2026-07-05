"""DataMind AI - Render 启动脚本（Python 版本）"""
import os
import subprocess
import sys

# 找到仓库根目录：这个文件在根目录下
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
os.environ["PYTHONPATH"] = ROOT

print(f"[Start] Working directory: {ROOT}")
print(f"[Start] PYTHONPATH: {os.environ['PYTHONPATH']}")
sys.path.insert(0, ROOT)

# 启动 uvicorn
subprocess.run([
    sys.executable, "-m", "uvicorn",
    "backend.main:app",
    "--host", "0.0.0.0",
    "--port", os.environ.get("PORT", "8000")
])
