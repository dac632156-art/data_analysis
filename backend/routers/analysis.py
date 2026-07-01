"""
分析执行与保存 API 路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import uuid
from datetime import datetime

from backend.services.session_manager import manager
from src.planner import Planner
from src.chart_renderer import ChartRenderer
from src.analysis_templates.base import AnalysisPackage
from src.analysis_templates.growth_analysis import GrowthAnalysis
from src.analysis_templates.ranking_analysis import RankingAnalysis
from src.analysis_templates.structure_analysis import StructureAnalysis
from src.analysis_templates.concentration_analysis import ConcentrationAnalysis
from src.analysis_templates.distribution_analysis import DistributionAnalysis
from src.analysis_templates.correlation_analysis import CorrelationAnalysis
from src.analysis_templates.anomaly_analysis import AnomalyAnalysis
from src.analysis_templates.proportion_analysis import ProportionAnalysis

router = APIRouter()

# ===== 模板注册表 =====
_TEMPLATES = {
    "growth_analysis": GrowthAnalysis,
    "ranking_analysis": RankingAnalysis,
    "structure_analysis": StructureAnalysis,
    "concentration_analysis": ConcentrationAnalysis,
    "distribution_analysis": DistributionAnalysis,
    "correlation_analysis": CorrelationAnalysis,
    "anomaly_analysis": AnomalyAnalysis,
    "proportion_analysis": ProportionAnalysis,
}

_RENDERER = ChartRenderer()
_PLANNER = Planner()

# ===== 请求模型 =====

class IntentItem(BaseModel):
    business_question: str
    analysis_goal: str
    priority: str
    reason: str


class AnalysisRunRequest(BaseModel):
    session_id: str
    intents: List[IntentItem]


class AnalysisSaveRequest(BaseModel):
    session_id: str
    package_ids: List[str]


# ===== 分析执行 =====

@router.post("/analysis/run")
async def api_analysis_run(req: AnalysisRunRequest):
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="会话数据不存在")

    packages: list = []
    package_map: dict = {}

    for intent in req.intents:
        # 1. Planner 翻译
        plan = _PLANNER.plan(intent.model_dump(), df)
        method = plan["analysis_method"]
        algorithm = plan.get("algorithm")
        dim = plan.get("dimension")
        met = plan.get("metric")

        # 2. fallback 递归
        result = _execute_with_fallback(df, method, dim, met, algorithm,
                                         intent.business_question)
        pkg_id = str(uuid.uuid4())[:8]
        result.id = pkg_id
        result.business_question = intent.business_question

        packages.append(result.model_dump())
        package_map[pkg_id] = result

    # 3. 缓存到 Session（临时）
    manager.set_analysis_packages(req.session_id, package_map)

    return {"packages": packages}


def _execute_with_fallback(df, method: str, dim, met, algorithm,
                            business_question: str,
                            fallback_from=None, depth=0) -> AnalysisPackage:

    if depth > 5:
        return _unsupported(business_question, "递归深度超限")

    # 模板不存在（占位 intent）
    if method not in _TEMPLATES:
        return _fallback_or_unsupported(df, method, business_question, depth)

    template_cls = _TEMPLATES[method]
    template = template_cls()

    if template.can_run(df):
        pkg = template.execute(df, dim, met, algorithm)
        pkg.fallback_from = fallback_from
        return pkg

    # can_run 失败 → 降级
    fallback_method = template_cls.spec.FALLBACK
    if fallback_method:
        return _execute_with_fallback(df, fallback_method, dim, met, algorithm,
                                       business_question, fallback_from=method,
                                       depth=depth + 1)

    return _unsupported(business_question, f"分析 '{method}' 无法执行且无降级方案")


def _fallback_or_unsupported(df, method, question, depth):
    """占位 intent 的 fallback 处理"""
    if "comparison" in method or "decomposition" in method:
        return _execute_with_fallback(df, "ranking_analysis", None, None, None,
                                       question, fallback_from=method, depth=depth + 1)
    return _unsupported(question, f"分析方法 '{method}' 尚未实现")


def _unsupported(question: str, reason: str) -> AnalysisPackage:
    return AnalysisPackage(
        id="",
        analysis_type="unsupported",
        business_question=question,
        algorithm=None,
        dimension=None,
        metric=None,
        can_run=False,
        insights=[reason],
        conclusions=[f"原因: {reason}"],
    )


# ===== 分析保存 =====

@router.post("/analysis/save")
async def api_analysis_save(req: AnalysisSaveRequest):
    """从 session.analysis_packages 复制到 saved_packages"""
    manager.save_packages(req.session_id, req.package_ids)
    packages = manager.get_saved_packages(req.session_id)
    saved_ids = [p.get("id") for p in packages if p.get("id") in req.package_ids]
    return {"saved_count": len(saved_ids), "package_ids": saved_ids}
