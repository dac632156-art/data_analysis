"""
报告生成 API 路由（V3 — 基于 AnalysisPackage，异步无状态模式）

对外端点：
- POST /report/ai-analyze                  — 提交报告生成任务，立即返回 task_id
- GET  /report/ai-analyze/status/{task_id} — 轮询任务状态/结果

【异步化】规避 Render 免费实例约 50s 的 HTTP 请求超时（ERR_CONNECTION_CLOSED）：
  提交请求毫秒级返回 task_id，LLM 生成在后台线程执行，前端轮询获取结果。

【无状态】报告生成优先使用请求体携带的 packages（前端 localStorage 副本），
  后端不强依赖 session.saved_packages；Render 进程重启/休眠也不影响报告生成。
  未携带 packages 时回退到 session.saved_packages（向后兼容）。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import threading
import time
import uuid

from backend.services.session_manager import manager
from backend.utils.ai_error import enhance_ai_error
from src.ai_agent.agent import DataAnalysisAgent
from src.utils.json_serializer import sanitize_json

router = APIRouter()


# ============================================================
# 内存任务表（task_id -> {status, result?, error?, ts}）
# status: 'running' | 'done' | 'error'
# 说明：仅暂存报告生成结果。进程重启会丢失，但无状态设计使重试可安全重来
#       （前端持有 packages 副本，重新提交即可）。
# ============================================================
_report_tasks: Dict[str, Dict[str, Any]] = {}
_report_tasks_lock = threading.Lock()
_TASK_TTL = 900  # 任务结果保留 15 分钟后清理，防止内存泄漏

# P1（内存画像结论四）：限制同时调 LLM 的报告线程数。
# 报告线程本身几乎不占内存（<0.1MB），瓶颈在 LLM 网络 I/O 速率/API 并发上限，
# 故信号量按 LLM 速率设（而非内存）。超额提交的任务在线程入口排队，端点仍毫秒返回 task_id，前端轮询无感。
# 用 threading.Semaphore：报告任务实际跑在后台线程中，而非协程。
_REPORT_SEMAPHORE = threading.Semaphore(5)


def _cleanup_tasks_locked():
    """清理过期任务（需在持锁状态下调用）"""
    now = time.time()
    expired = [tid for tid, t in _report_tasks.items() if now - t.get("ts", now) > _TASK_TTL]
    for tid in expired:
        _report_tasks.pop(tid, None)


class AIReportRequest(BaseModel):
    session_id: str
    api_key: Optional[str] = ""
    base_url: Optional[str] = None
    model: Optional[str] = None
    # ★ 无状态：前端可直接携带已保存的分析包副本（来自 localStorage），
    #   不再强依赖后端 session.saved_packages
    packages: Optional[List[Dict[str, Any]]] = None


def _run_report_task(
    task_id: str,
    packages: List[Dict[str, Any]],
    data_profile: Optional[Dict[str, Any]],
    kwargs: Dict[str, Any],
    model: str,
    base_url: str,
):
    """后台线程：执行报告生成，结果写入 _report_tasks"""
    try:
        # 仅 LLM 生成阶段受信号量约束（按 LLM 速率限流，避免无脑堆线程/触发 API 限流）
        with _REPORT_SEMAPHORE:
            agent = DataAnalysisAgent(**kwargs)
            result = agent.generate_report_from_packages(packages, data_profile)

        if result.get("success"):
            # 从 packages 中提取图表 option 供前端报告渲染。
            # 优先使用已渲染好的 pkg["charts"]；若不存在则回退到 pkg["chart_data"]。
            # 按 title 去重，避免同一图被多包/多字段重复加入。
            chart_options = []
            seen_titles = set()
            for pkg in packages:
                charts = pkg.get("charts") or pkg.get("chart_data") or []
                for chart in charts:
                    if not isinstance(chart, dict) or not chart.get("option"):
                        continue
                    title = chart.get("title", "")
                    if title in seen_titles:
                        continue
                    seen_titles.add(title)
                    chart_options.append({
                        "title": title,
                        "option": chart["option"],
                        "chart_type": chart.get("chart_type", ""),
                        "role": chart.get("role", ""),
                        "slot": chart.get("slot", ""),
                        "raw_data": chart.get("raw_data"),
                    })
            payload = sanitize_json({
                "success": True,
                "sections": result.get("sections", []),
                "report_title": result.get("report_title", ""),
                "packages_used": result.get("packages_used", 0),
                "charts": chart_options,
                "warning": result.get("warning"),
                "degradation": result.get("degradation"),
            })
            with _report_tasks_lock:
                _report_tasks[task_id] = {"status": "done", "result": payload, "ts": time.time()}
        else:
            with _report_tasks_lock:
                _report_tasks[task_id] = {
                    "status": "error",
                    "error": str(result.get("warning", "报告生成失败")),
                    "ts": time.time(),
                }
    except Exception as e:
        err = enhance_ai_error(e, model=model or "", base_url=base_url or "")
        with _report_tasks_lock:
            _report_tasks[task_id] = {"status": "error", "error": err, "ts": time.time()}


@router.post("/report/ai-analyze")
async def api_ai_report_submit(req: AIReportRequest):
    """提交 AI 分析报告生成任务（异步无状态）

    立即返回 task_id，后台线程执行 LLM 生成，前端轮询 status 获取结果。
    数据来源：优先请求体 packages（无状态副本），回退 session.saved_packages。
    """
    # 1. 取 packages：优先请求体（无状态），回退 session（兼容）
    packages = req.packages if req.packages else manager.get_saved_packages(req.session_id)
    if not packages:
        raise HTTPException(
            status_code=400,
            detail="没有已保存的分析结果。请先在分析页面执行分析并保存（点击「保存到仪表盘」），再生成报告。"
        )

    # 2. api_key：优先请求体，回退 session
    api_key = req.api_key or manager.get_api_key(req.session_id)
    if not api_key:
        raise HTTPException(status_code=400, detail="需要 AI API Key")

    # 3. data_profile：session 有原始数据则计算，无则为 None（无状态下不强依赖）
    df = manager.get_data(req.session_id)
    data_profile = None
    if df is not None:
        from src.column_classifier import ColumnClassifier
        try:
            cc = ColumnClassifier()
            data_profile = cc.classify_all(df)
        except Exception:
            pass

    kwargs: Dict[str, Any] = {"api_key": api_key}
    if req.base_url:
        kwargs["base_url"] = req.base_url
    if req.model:
        kwargs["model"] = req.model

    # 4. 建任务 + 起后台线程（提交请求立即返回，规避平台 HTTP 超时）
    task_id = str(uuid.uuid4())
    with _report_tasks_lock:
        _cleanup_tasks_locked()
        _report_tasks[task_id] = {"status": "running", "ts": time.time()}

    threading.Thread(
        target=_run_report_task,
        args=(task_id, packages, data_profile, kwargs, req.model or "", req.base_url or ""),
        daemon=True,
    ).start()

    return {"success": True, "task_id": task_id, "status": "running"}


@router.get("/report/ai-analyze/status/{task_id}")
async def api_ai_report_status(task_id: str):
    """查询报告生成任务状态/结果

    - running：仍在生成中
    - done：返回完整报告数据（sections/charts/warning 等）
    - error：返回错误信息（HTTP 200，避免前端全局重试拦截器误介入）
    - 404：任务不存在或已过期（进程重启/超 TTL），前端应提示重新生成
    """
    with _report_tasks_lock:
        task = _report_tasks.get(task_id)

    if task is None:
        raise HTTPException(status_code=404, detail="报告任务不存在或已过期，请重新生成。")

    status = task.get("status")
    if status == "running":
        return {"success": True, "status": "running"}
    if status == "error":
        return {"success": False, "status": "error", "detail": task.get("error", "报告生成失败")}
    # done
    result = task.get("result", {})
    return {"status": "done", **result}
