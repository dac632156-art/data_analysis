"""
分析执行与保存 API 路由

V2：模板通过 AnalysisLibrary + 动态导入管理，_TEMPLATES 仅做懒加载缓存。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import uuid
import dataclasses
import importlib
from datetime import datetime

from backend.services.session_manager import manager
from src.planner import Planner
from src.chart_renderer import ChartRenderer
from src.analysis_templates.base import AnalysisPackage
from src.utils.json_serializer import sanitize_json
from src.analysis_library import AnalysisLibrary

router = APIRouter()

# ===== 模板懒加载缓存 =====
_TEMPLATES: dict = {}

_LIBRARY = AnalysisLibrary()
_RENDERER = ChartRenderer()
_PLANNER = Planner()

def _get_template_class(template_name: str):
    """通过 AnalysisLibrary 动态导入模板类（带缓存）

    V3：Planner.TEMPLATE_MODULES 已移除，改为通过 AnalysisLibrary 查询。
    template_name 是模板名（如 growth_analysis），需先查找对应的 intent。
    """
    if template_name in _TEMPLATES:
        return _TEMPLATES[template_name]

    # V3：遍历 Library 中所有 intent，找到 template 匹配的
    for intent_obj in _LIBRARY.get_all():
        if intent_obj.template == template_name:
            cls = _LIBRARY.load_template_class(intent_obj.intent)
            if cls:
                _TEMPLATES[template_name] = cls
            return cls

    return None
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

        # Planner 返回 unsupported → 尝试 YAML fallback_intents 链
        if method == "unsupported":
            fallback_intents = plan.get("fallback_intents", [])
            dim = plan.get("dimension")
            met = plan.get("metric")

            if fallback_intents:
                # 按 YAML 配置的 fallback 顺序逐一尝试
                result = _try_fallback_chain(df, fallback_intents, dim, met,
                                              intent.business_question,
                                              plan.get("unsupported_reason", ""))
            else:
                result = _unsupported(
                    intent.business_question,
                    plan.get("unsupported_reason", "Planner 判定该问题无法在当前数据上执行")
                )

            pkg_id = str(uuid.uuid4())[:8]
            result.id = pkg_id
            result.business_question = intent.business_question
            packages.append(dataclasses.asdict(result))
            package_map[pkg_id] = result
            continue

        algorithm = plan.get("algorithm")
        dim = plan.get("dimension")
        met = plan.get("metric")

        # 2. fallback 递归
        result = _execute_with_fallback(df, method, dim, met, algorithm,
                                         intent.business_question)

        # 3. 图表渲染：chart_data → charts（ChartItem + ECharts option）
        result.charts = _RENDERER.render_all(result.chart_data) if result.chart_data else []

        pkg_id = str(uuid.uuid4())[:8]
        result.id = pkg_id
        result.business_question = intent.business_question

        packages.append(dataclasses.asdict(result))
        package_map[pkg_id] = result

    # 3. 缓存到 Session（临时）
    manager.set_analysis_packages(req.session_id, package_map)

    return {"packages": sanitize_json(packages)}


def _try_fallback_chain(df, fallback_intents: list, dim, met,
                         business_question: str, original_reason: str) -> AnalysisPackage:
    """按 YAML 配置的 fallback 顺序逐一尝试，第一个 can_run 成功即返回"""
    for fb_intent in fallback_intents:
        fb_entry = _LIBRARY.get_by_intent(fb_intent)
        if fb_entry is None:
            continue
        template_name = fb_entry.template
        template_cls = _get_template_class(template_name)
        if template_cls is None:
            continue

        template = template_cls()
        if template.can_run(df):
            pkg = template.execute(df, dim, met, fb_entry.default_algorithm)
            pkg.fallback_from = fb_intent
            pkg.fallback_reason = f"当前数据不支持原始分析，已自动降级为「{fb_entry.display_name}」。" \
                                  f"原因：{original_reason}"
            return pkg

    return _unsupported(business_question, original_reason)


def _execute_with_fallback(df, method: str, dim, met, algorithm,
                            business_question: str,
                            fallback_from=None, depth=0) -> AnalysisPackage:

    if depth > 5:
        return _unsupported(business_question, "递归深度超限")

    # 模板不存在 → 用 Library fallback
    template_cls = _get_template_class(method)
    if template_cls is None:
        return _fallback_via_library(df, method, business_question, depth, dim, met)

    template = template_cls()

    if template.can_run(df):
        pkg = template.execute(df, dim, met, algorithm)
        pkg.fallback_from = fallback_from
        return pkg

    # can_run 失败 → 降级（用 TemplateRuntime 的 FALLBACK）
    fallback_method = template_cls.runtime.FALLBACK
    if fallback_method:
        pkg = _execute_with_fallback(df, fallback_method, dim, met, algorithm,
                                       business_question, fallback_from=method,
                                       depth=depth + 1)
        pkg.fallback_reason = f"当前数据不满足「{method}」的运行条件，已自动降级为「{fallback_method}」"
        return pkg

    return _unsupported(business_question, f"分析 '{method}' 无法执行且无降级方案")


def _fallback_via_library(df, method, question, depth, dim=None, met=None):
    """模板不存在时，从 Library 的 YAML fallback 列表中查找降级方案"""
    # 查找该 method 对应的 Library intent，获取其 fallback 列表
    for intent_obj in _LIBRARY.get_all():
        if intent_obj.template == method:
            if intent_obj.fallback:
                return _try_fallback_chain(df, intent_obj.fallback, dim, met, question,
                                           f"分析方法「{method}」尚未实现")
            break

    # 兜底：尝试 ranking
    fb_entry = _LIBRARY.get_by_intent("ranking")
    if fb_entry:
        template_cls = _get_template_class(fb_entry.template)
        if template_cls:
            template = template_cls()
            if template.can_run(df):
                pkg = template.execute(df, dim, met, None)
                pkg.fallback_from = method
                pkg.fallback_reason = f"分析方法「{method}」尚未实现，已自动使用排名分析替代"
                return pkg

    return _unsupported(question, f"分析方法 '{method}' 尚未实现且无可用降级方案")


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
    try:
        manager.save_packages(req.session_id, req.package_ids)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")
    packages = manager.get_saved_packages(req.session_id)
    saved_ids = [p.get("id") for p in packages if p.get("id") in req.package_ids]
    return sanitize_json({"saved_count": len(saved_ids), "package_ids": saved_ids})
