"""
报告生成 API 路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor

from backend.services.session_manager import manager
from src.report_generator import generate_html_report
from src.ai_agent.agent import DataAnalysisAgent

router = APIRouter()


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


@router.post("/report/ai-analyze")
async def api_ai_report(req: AIReportRequest):
    """生成 AI 数据分析报告（五阶段流水线）

    阶段1-3：Python pandas 精确计算（字段识别/图表规划/统计分析）
    阶段4-5：LLM 生成洞察和报告内容

    返回结构化 sections 列表，前端可直接渲染为报告
    """
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")

    # 获取 API Key
    api_key = req.api_key or manager.get_api_key(req.session_id)
    if not api_key:
        raise HTTPException(status_code=400, detail="需要 AI API Key")

    # 获取已保存的图表（含同环比表格数据）
    saved_charts = manager.get_saved_charts(req.session_id)

    try:
        kwargs: Dict[str, Any] = {"api_key": api_key}
        if req.base_url:
            kwargs["base_url"] = req.base_url
        if req.model:
            kwargs["model"] = req.model
        agent = DataAnalysisAgent(**kwargs)

        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            result = await loop.run_in_executor(
                executor,
                agent.generate_report,
                df,
                saved_charts if saved_charts else None,
            )

        return {
            "success": True,
            "sections": result.get("sections", []),
            "warning": result.get("warning"),
        }
    except Exception as e:
        import traceback
        print(f"[Report API Error] {e}")
        traceback.print_exc()
        # 直接返回 JSON 错误响应，确保前端能读取到 detail
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={"detail": f"AI 报告生成失败: {str(e)}"},
        )
