"""
报告生成 API 路由
"""
import uuid
import threading
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor

from backend.services.session_manager import manager
from src.report_generator import generate_html_report
from src.ai_agent.agent import DataAnalysisAgent

router = APIRouter()

# ===== 异步任务存储（Render 实例存活期间有效） =====
TASK_STORE: Dict[str, Dict[str, Any]] = {}
TASK_STORE_LOCK = threading.Lock()
TASK_TTL_SECONDS = 600  # 任务结果保留 10 分钟


def _cleanup_expired_tasks():
    """清理过期任务"""
    with TASK_STORE_LOCK:
        now = time.time()
        expired = [tid for tid, t in TASK_STORE.items() if now - t.get("created_at", 0) > TASK_TTL_SECONDS]
        for tid in expired:
            del TASK_STORE[tid]


class ReportRequest(BaseModel):
    session_id: str
    title: Optional[str] = "数据分析报告"


class AIReportRequest(BaseModel):
    session_id: str
    api_key: Optional[str] = ""
    base_url: Optional[str] = None
    model: Optional[str] = None


@router.post("/report/generate")
async def api_generate_report(req: ReportRequest):
    """生成 HTML 分析报告"""
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")
    
    cleaning_history = manager.get_cleaning_history(req.session_id)
    
    try:
        html = generate_html_report(
            df=df,
            title=req.title,
            insights=None,
            cleaning_history=cleaning_history if cleaning_history else None
        )
        return {"success": True, "html": html}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"报告生成失败: {str(e)}")


def _run_ai_report_task(task_id: str, api_key: str, base_url: Optional[str],
                         model: Optional[str], df, saved_charts):
    """后台线程：执行 AI 报告生成"""
    try:
        with TASK_STORE_LOCK:
            TASK_STORE[task_id]["status"] = "processing"
            TASK_STORE[task_id]["progress"] = 10
            TASK_STORE[task_id]["message"] = "🔍 阶段1-2：字段识别与图表规划..."

        kwargs: Dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        if model:
            kwargs["model"] = model
        agent = DataAnalysisAgent(**kwargs)

        with TASK_STORE_LOCK:
            TASK_STORE[task_id]["progress"] = 30
            TASK_STORE[task_id]["message"] = "📊 阶段3：pandas 统计分析..."

        result = agent.generate_report(df, saved_charts)

        with TASK_STORE_LOCK:
            TASK_STORE[task_id]["progress"] = 80
            TASK_STORE[task_id]["message"] = "🤖 阶段4-5：LLM 生成洞察与报告内容..."

        with TASK_STORE_LOCK:
            TASK_STORE[task_id]["status"] = "done"
            TASK_STORE[task_id]["progress"] = 100
            TASK_STORE[task_id]["message"] = "✅ 报告生成完成"
            TASK_STORE[task_id]["result"] = {
                "success": True,
                "sections": result.get("sections", []),
                "warning": result.get("warning"),
            }

    except Exception as e:
        import traceback
        print(f"[Task {task_id}] 报告生成失败: {e}")
        traceback.print_exc()
        with TASK_STORE_LOCK:
            TASK_STORE[task_id]["status"] = "failed"
            TASK_STORE[task_id]["error"] = str(e)
            TASK_STORE[task_id]["message"] = f"❌ 失败: {e}"


@router.post("/report/ai-analyze")
async def api_ai_report_submit(req: AIReportRequest):
    """提交 AI 报告生成任务（异步模式）

    立即返回 task_id，前端轮询 /report/ai-analyze/status/{task_id}
    """
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")

    api_key = req.api_key or manager.get_api_key(req.session_id)
    if not api_key:
        raise HTTPException(status_code=400, detail="需要 AI API Key")

    saved_charts = manager.get_saved_charts(req.session_id)

    # 清理过期任务
    _cleanup_expired_tasks()

    # 创建任务
    task_id = uuid.uuid4().hex[:12]
    with TASK_STORE_LOCK:
        TASK_STORE[task_id] = {
            "status": "pending",
            "progress": 0,
            "message": "📝 任务已提交，等待处理...",
            "created_at": time.time(),
            "result": None,
            "error": None,
        }

    # 后台线程执行
    thread = threading.Thread(
        target=_run_ai_report_task,
        args=(task_id, api_key, req.base_url, req.model, df, saved_charts if saved_charts else None),
        daemon=True,
    )
    thread.start()

    return {"task_id": task_id, "status": "pending"}


@router.get("/report/ai-analyze/status/{task_id}")
def api_ai_report_status(task_id: str):
    """查询任务状态（前端每 3 秒轮询一次）"""
    with TASK_STORE_LOCK:
        task = TASK_STORE.get(task_id)

    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")

    return {
        "task_id": task_id,
        "status": task["status"],       # pending | processing | done | failed
        "progress": task.get("progress", 0),
        "message": task.get("message", ""),
        "error": task.get("error"),
    }


@router.get("/report/ai-analyze/result/{task_id}")
def api_ai_report_result(task_id: str):
    """获取任务结果（任务完成后调用）"""
    with TASK_STORE_LOCK:
        task = TASK_STORE.get(task_id)

    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")

    if task["status"] == "failed":
        return {
            "success": False,
            "detail": task.get("error", "未知错误"),
        }

    if task["status"] != "done":
        raise HTTPException(status_code=400, detail="任务尚未完成，请继续等待")

    return task["result"]
