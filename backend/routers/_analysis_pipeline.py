"""
后台分析流水线（共享模块）。

供 `/analysis/run` 与 `/analysis/process-datasets` 共用同一套「Planner 翻译 → 模板执行 → 图表渲染 → 装包」。
只依赖 src.*，不 import backend.routers.analysis，避免循环导入。
"""
from typing import Any, Dict, List, Tuple
import uuid
import dataclasses

from src.analysis_library import AnalysisLibrary
from src.chart_renderer import ChartRenderer
from src.analysis_templates.base import AnalysisPackage
from src.planner import Planner
from src.utils.json_serializer import sanitize_json

# ===== 模板懒加载缓存 =====
_TEMPLATES: dict = {}

_LIBRARY = AnalysisLibrary()
_RENDERER = ChartRenderer()
_PLANNER = Planner()


def _get_template_class(template_name: str):
    """通过 AnalysisLibrary 动态导入模板类（带缓存）"""
    if template_name in _TEMPLATES:
        return _TEMPLATES[template_name]

    for intent_obj in _LIBRARY.get_all():
        if intent_obj.template == template_name:
            cls = _LIBRARY.load_template_class(intent_obj.intent)
            if cls:
                _TEMPLATES[template_name] = cls
            return cls

    return None


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

    template_cls = _get_template_class(method)
    if template_cls is None:
        return _fallback_via_library(df, method, business_question, depth, dim, met)

    template = template_cls()

    if template.can_run(df):
        pkg = template.execute(df, dim, met, algorithm)
        pkg.fallback_from = fallback_from
        return pkg

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
    for intent_obj in _LIBRARY.get_all():
        if intent_obj.template == method:
            if intent_obj.fallback:
                return _try_fallback_chain(df, intent_obj.fallback, dim, met, question,
                                           f"分析方法「{method}」尚未实现")
            break

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


def _unsupported(question: str, reason: str, suggestion: str = "") -> AnalysisPackage:
    return AnalysisPackage(
        id="",
        analysis_type="unsupported",
        business_question=question,
        algorithm=None,
        dimension=None,
        metric=None,
        can_run=False,
        insights=[reason] if reason else [],
        conclusions=[f"原因: {reason}"] if reason else [],
        suggestion=suggestion,
    )


def run_intents_to_packages(df, intents: List[Dict[str, Any]]) -> Tuple[List[dict], Dict[str, Any]]:
    """对每个 intent 跑完整流水线，返回 (packages 列表, package_map 字典)。

    packages：已 sanitize 的 dict 列表（供接口响应）。
    package_map：{pkg_id: AnalysisPackage 对象}（供会话存储 / 看板 / 报告直接消费）。

    与 /analysis/run 的循环体逻辑完全一致；intents 为 dict 列表（来自 Planner.generate_default_intents）。
    """
    packages: list = []
    package_map: dict = {}

    for intent in intents:
        plan = _PLANNER.plan(intent, df)
        method = plan["analysis_method"]

        if method == "unsupported":
            fallback_intents = plan.get("fallback_intents", [])
            dim = plan.get("dimension")
            met = plan.get("metric")

            if fallback_intents:
                result = _try_fallback_chain(df, fallback_intents, dim, met,
                                             intent.get("business_question", ""),
                                             plan.get("unsupported_reason", ""))
            else:
                result = _unsupported(
                    intent.get("business_question", ""),
                    plan.get("unsupported_reason", "Planner 判定该问题无法在当前数据上执行"),
                    plan.get("suggestion", ""),
                )

            pkg_id = str(uuid.uuid4())[:8]
            result.id = pkg_id
            result.business_question = intent.get("business_question", "")
            packages.append(dataclasses.asdict(result))
            package_map[pkg_id] = result
            continue

        algorithm = plan.get("algorithm")
        dim = plan.get("dimension")
        met = plan.get("metric")

        exec_df = plan.get("derived_df") if plan.get("derived_df") is not None else df
        result = _execute_with_fallback(exec_df, method, dim, met, algorithm,
                                         intent.get("business_question", ""))

        result.charts = _RENDERER.render_all(result.chart_data) if result.chart_data else []

        pkg_id = str(uuid.uuid4())[:8]
        result.id = pkg_id
        result.business_question = intent.get("business_question", "")

        packages.append(dataclasses.asdict(result))
        package_map[pkg_id] = result

    return packages, package_map
