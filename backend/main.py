"""
DataMind AI - FastAPI 后端入口
提供 RESTful API 接口供 React 前端调用
"""
import os
import sys
import traceback

# 添加项目根目录到 sys.path，以便导入现有模块
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 加载 .env 环境变量（优先于 config 导入，本地开发可覆盖默认值，生产环境无 .env 文件自动用默认值）
from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, ".env"))

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, Response

# 导入路由
from backend.routers import upload, data, clean, chart, dashboard, insights, report, analysis
from backend.services.session_manager import manager

# ===== 强制 UTF-8 编码，避免 Windows 环境下 print() 中文报错 =====
import sys as _sys
if hasattr(_sys.stdout, 'reconfigure'):
    try:
        _sys.stdout.reconfigure(encoding='utf-8')
        _sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

app = FastAPI(
    title="DataMind AI",
    description="数据分析智能体 API",
    version="1.0.0",
)

# CORS 配置 - 演示阶段允许所有来源（生产环境应限制）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,   # allow_origins=["*"] 时必须为 False
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(upload.router, prefix="/api", tags=["数据上传"])
app.include_router(data.router, prefix="/api", tags=["数据操作"])
app.include_router(clean.router, prefix="/api", tags=["数据清洗"])
app.include_router(chart.router, prefix="/api", tags=["图表生成"])
app.include_router(dashboard.router, prefix="/api", tags=["仪表盘"])
app.include_router(insights.router, prefix="/api", tags=["AI 洞察"])
app.include_router(report.router, prefix="/api", tags=["报告生成"])
app.include_router(analysis.router, prefix="/api", tags=["分析执行"])


# 全局异常处理器：捕获所有未处理的异常，返回详细错误信息
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常捕获：避免 500 时前端只看到 Network Error"""
    tb = traceback.format_exc()
    import logging as _logging; _logging.getLogger("uvicorn.error").error(f"{exc.__class__.__name__}: {exc}", exc_info=True)
    # traceback logged via logging above
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



@app.get("/api/session/new")
async def new_session():
    """创建新会话"""
    session_id = manager.create_session()
    return {"session_id": session_id, "success": True}


# 前端构建产物目录（Render 部署时随仓库提交 frontend/dist，由后端直接托管）
# 兼容不同部署目录结构：在多个候选路径中查找 frontend/dist
def _resolve_frontend_dist():
    """在多个候选路径中寻找 frontend/dist，兼容不同部署目录结构"""
    candidates = [
        os.path.join(project_root, "frontend", "dist"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist"),
        os.path.join(os.getcwd(), "frontend", "dist"),
        os.path.join(os.path.dirname(os.getcwd()), "frontend", "dist"),
    ]
    for c in candidates:
        if os.path.isdir(c):
            return os.path.abspath(c)
    # 兜底：返回标准路径（即使不存在，main.py 会回退到 JSON）
    return os.path.join(project_root, "frontend", "dist")

FRONTEND_DIST = _resolve_frontend_dist()


@app.get("/")
async def root():
    """根路径：部署时返回前端 SPA 页面，本地未构建时返回健康检查 JSON"""
    index_html = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.isfile(index_html):
        # index.html 禁止 CDN 缓存，确保用户总能拿到最新版本
        return FileResponse(index_html, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    return {"status": "ok", "version": "1.0.0"}


# SPA fallback：非 /api 的 GET 请求先尝试返回对应静态资源，找不到则回退到 index.html
# 仅在构建产物存在时注册（本地开发走 Vite dev server，无需此后端托管）
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if not os.path.isdir(FRONTEND_DIST):
        return {"status": "ok", "version": "1.0.0"}
    if full_path.startswith("api/"):
        # 真实 API 路由已在上面注册；此处兜底返回 JSON，避免 SPA 回退吞掉 /api 请求
        return {"status": "ok", "version": "1.0.0"}
    file_path = os.path.join(FRONTEND_DIST, full_path)
    if os.path.isfile(file_path):
        # 带 hash 的静态资源（JS/CSS/图片）缓存 1 年；其他文件不缓存
        ext = os.path.splitext(full_path)[1].lower()
        if ext in ('.js', '.css', '.woff', '.woff2', '.ttf', '.svg', '.png', '.jpg', '.ico'):
            return FileResponse(file_path, headers={"Cache-Control": "public, max-age=31536000, immutable"})
        return FileResponse(file_path, headers={"Cache-Control": "no-cache"})
    return FileResponse(os.path.join(FRONTEND_DIST, "index.html"), headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
