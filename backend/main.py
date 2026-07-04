"""
DataMind AI - FastAPI 后端入口
提供 RESTful API 接口供 React 前端调用
"""
import os
import sys
import traceback
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

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

# CORS 配置 - 支持本地开发和线上部署
# 环境变量 BACKEND_CORS_ORIGINS 可在 Render 上设置，格式：逗号分隔的域名列表
cors_origins = os.getenv("BACKEND_CORS_ORIGINS", "").split(",")
cors_origins = [o.strip() for o in cors_origins if o.strip()]
# 默认允许本地开发地址
default_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
]
all_origins = default_origins + cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=all_origins,
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


# 全局异常处理器：捕获所有未处理的异常，返回详细错误信息
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常捕获：避免 500 时前端只看到 Network Error"""
    tb = traceback.format_exc()
    print(f"[ERROR] {exc.__class__.__name__}: {str(exc)}")
    print(f"[TRACEBACK]\n{tb}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"{exc.__class__.__name__}: {str(exc)}",
            "traceback": tb if os.getenv("DEBUG") == "1" else None,
        }
    )


@app.get("/api/health")
async def health_check():
    """健康检查接口"""
    return {"status": "ok", "version": "1.0.0"}


# Render 健康检查需要根路径返回 200，否则会杀掉容器
@app.get("/")
async def root():
    """Root path for Render health check"""
    return {"status": "ok"}


@app.get("/api/session/new")
async def new_session():
    """创建新会话"""
    session_id = manager.create_session()
    return {"session_id": session_id, "success": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
