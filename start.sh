#!/bin/bash
# DataMind AI - Render 启动脚本
# 解决工作目录不确定的问题：自动找到仓库根目录然后启动服务

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1
export PYTHONPATH="$SCRIPT_DIR"
exec python -m uvicorn backend.main:app --host 0.0.0.0 --port "$PORT"
