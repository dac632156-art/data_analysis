"""
报告生成 API 路由（V3 — 基于 AnalysisPackage）

唯一对外端点：
- POST /report/ai-analyze — AI 驱动的分析报告（DataMind 五阶段流水线）

说明：旧版 HTML 模板报告（/report/generate）与 V3 规则版报告
（/report/professional、/report/professional-advanced）及其前端调用均未被使用，
仅移除死端点。其底层的 src.report.* 引擎包经排查无任何活跃引用，已一并删除；
本端点实际只复用 report_builder.build_input() 与 src.report_analyzer。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor

from backend.services.session_manager import manager
from backend.utils.ai_error import enhance_ai_error
from src.ai_agent.agent import DataAnalysisAgent

router = APIRouter()


class AIReportRequest(BaseModel):
    session_id: str
    api_key: Optional[str] = ""
    base_url: Optional[str] = None
    model: Optional[str] = None


@router.post("/report/ai-analyze")
async def api_ai_report_submit(req: AIReportRequest):
    """生成 AI 分析报告（V3 — 基于 AnalysisPackage，同步模式）

    数据来源：session 中的 saved_packages（AnalysisPackage）。
    不再调用 run_full_analysis() 重新分析数据。
    报告 AI 的唯一职责是读取 AnalysisPackage 并组织语言生成专业报告。
    """
    saved_packages = manager.get_saved_packages(req.session_id)

    if not saved_packages:
        raise HTTPException(
            status_code=400,
            detail="没有已保存的分析结果。请先在分析页面执行分析并保存（点击「保存到仪表盘」），再生成报告。"
        )

    api_key = req.api_key or manager.get_api_key(req.session_id)
    if not api_key:
        raise HTTPException(status_code=400, detail="需要 AI API Key")

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

    try:
        agent = DataAnalysisAgent(**kwargs)

        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            result = await loop.run_in_executor(
                executor,
                agent.generate_report_from_packages,
                saved_packages,
                data_profile,
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=enhance_ai_error(e, model=req.model or "", base_url=req.base_url or ""))

    if result.get("success"):
        # 从 saved_packages 中提取图表 option 数据供前端报告渲染
        chart_options = []
        for pkg in saved_packages:
            charts = pkg.get("charts", [])
            for chart in charts:
                if isinstance(chart, dict) and chart.get("option"):
                    chart_options.append({
                        "title": chart.get("title", ""),
                        "option": chart["option"],
                        "chart_type": chart.get("chart_type", ""),
                        "role": chart.get("role", ""),
                    })

        return {
            "success": True,
            "sections": result.get("sections", []),
            "packages_used": result.get("packages_used", 0),
            "charts": chart_options,
            "warning": result.get("warning"),
        }
    else:
        raise HTTPException(status_code=500, detail=str(result.get("warning", "报告生成失败")))
