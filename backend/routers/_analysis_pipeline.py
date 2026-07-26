"""
后台分析流水线（共享模块）。

供 /analysis/run 与 /analysis/process-datasets 共用同一套「新引擎（列名匹配）」。
只依赖 src.*，不 import backend.routers.analysis，避免循环导入。
"""
from typing import Any, Dict, List, Tuple

from src.analysis_engine import run_analysis
from src.chart_renderer import ChartRenderer
from src.utils.json_serializer import sanitize_json

# 通用出图层（chart_data → ECharts option），保留复用，不参与"计算逻辑"
_RENDERER = ChartRenderer()


def run_df_to_packages(df, intents=None) -> Tuple[List[dict], Dict[str, Any]]:
    """对单个 df 跑新引擎，返回 (packages 列表, package_map 字典)。

    packages：已 sanitize 的 dict 列表（供接口响应）。
    package_map：{pkg_id: AnalysisPackage 对象}（供会话存储 / 看板 / 报告直接消费）。

    intents 作为可选过滤（兼容前端选中意图交互），为空则运行全部匹配模型。
    """
    packages_obj = run_analysis(df, intents=intents)

    packages: list = []
    package_map: dict = {}
    for pkg in packages_obj:
        # 图表渲染：chart_data → charts（复用通用出图层）
        if getattr(pkg, "chart_data", None) and not getattr(pkg, "charts", None):
            try:
                pkg.charts = _RENDERER.render_all(pkg.chart_data)
            except Exception:
                pkg.charts = []

        d = pkg.to_api_dict()
        # to_api_dict 白名单未含 charts：补回已渲染图表（前端 VisualizationRenderer 依赖 pkg.charts）
        # 注意：ChartItem 是 __init__ 类（非 @dataclass），不能用 dataclasses.asdict
        if getattr(pkg, "charts", None):
            try:
                d["charts"] = [
                    {
                        "slot": getattr(c, "slot", None),
                        "chart_type": getattr(c, "chart_type", None),
                        "title": getattr(c, "title", None),
                        "role": getattr(c, "role", None),
                        "option": getattr(c, "option", None),
                    }
                    for c in pkg.charts
                ]
            except Exception:
                d["charts"] = []
        sd = sanitize_json(d)
        pid = sd.get("id") or getattr(pkg, "id", "")
        packages.append(sd)
        package_map[pid] = pkg

    return packages, package_map
