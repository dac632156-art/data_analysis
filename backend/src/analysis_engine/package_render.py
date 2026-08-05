"""将 AnalysisPackage（dict）渲染为前端 SmartDashboard 可消费的结构。

SmartDashboard.extractChartsFromSavedPackages 优先读取 pkg.rendered_charts，
兜底读取 pkg.charts；每个 chart 取 title/option/table_data/chart_type。
因此 render_package 只需把原始 pkg 透传并补上 rendered_charts 即可。
"""


def render_package(pkg: dict) -> dict:
    """渲染单个分析包为前端可消费格式。

    - pkg 可能是 dataclass 经 asdict 得到的 dict，也可能是直接构造的 dict；
    - 统一补 rendered_charts（优先 pkg.charts，兼容既有结构）；
    - 其余字段原样透传。
    """
    if not isinstance(pkg, dict):
        # 兜底：尝试转 dict（dataclass 等）
        try:
            import dataclasses

            pkg = dataclasses.asdict(pkg)
        except Exception:
            return {"rendered_charts": [], "charts": []}

    charts = pkg.get("charts") or pkg.get("rendered_charts") or []
    out = dict(pkg)
    out["rendered_charts"] = charts
    return out
