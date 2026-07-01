"""
DataMind AI - FastAPI 后端入口
提供 RESTful API 接口供 React 前端调用
"""
import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# 添加项目根目录到 sys.path，以便导入现有模块
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 导入路由
from backend.routers import upload, data, clean, stats, chart, dashboard, insights, chat, report, analysis
from backend.services.session_manager import manager

app = FastAPI(
    title="DataMind AI",
    description="数据分析智能体 API",
    version="1.0.0",
)

# CORS 配置 - 允许前端开发服务器访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite 开发服务器
        "http://localhost:3000",  # 备用
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(upload.router, prefix="/api", tags=["数据上传"])
app.include_router(data.router, prefix="/api", tags=["数据操作"])
app.include_router(clean.router, prefix="/api", tags=["数据清洗"])
app.include_router(stats.router, prefix="/api", tags=["统计分析"])
app.include_router(chart.router, prefix="/api", tags=["图表生成"])
app.include_router(dashboard.router, prefix="/api", tags=["仪表盘"])
app.include_router(insights.router, prefix="/api", tags=["AI 洞察"])
app.include_router(chat.router, prefix="/api", tags=["AI 对话"])
app.include_router(report.router, prefix="/api", tags=["报告生成"])
app.include_router(analysis.router, prefix="/api", tags=["分析执行"])


@app.get("/api/health")
async def health_check():
    """健康检查接口"""
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/session/new")
async def new_session():
    """创建新会话"""
    session_id = manager.create_session()
    return {"session_id": session_id, "success": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
