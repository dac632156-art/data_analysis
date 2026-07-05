"""
仪表盘 API 路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from backend.services.session_manager import manager
from src.dashboard_builder import calculate_kpis
from src.echart_generator import create_chart as create_echart
from src.echart_generator import _to_geo_name, _PROVINCE_CENTROIDS, _GEO_PROVINCE_NAMES
from src.utils.json_serializer import sanitize_json

router = APIRouter()
logger = logging.getLogger(__name__)


def _normalize_map_configs(df, configs: list) -> list:
    """地图图表配置预处理：去重

    地区→省份展开已由 create_gl_map 内部处理，这里只做去重。
    去重：如果多个 map_3d 图表的有效 (X, Y) 相同，只保留第一个
    """
    import pandas as pd

    if df is None or not configs:
        return configs

    fixed_configs = []
    seen_map_keys = set()

    for cfg in configs:
        if not isinstance(cfg, dict):
            fixed_configs.append(cfg)
            continue

        chart_type = cfg.get("chart_type", "")
        if chart_type not in ("map_3d", "gl_map"):
            fixed_configs.append(cfg)
            continue

        x = cfg.get("x", "")
        if not x or x not in df.columns:
            fixed_configs.append(cfg)
            continue

        # 去重：按有效 (X, Y) 键
        y = cfg.get("y", "")
        map_key = (x, y or "")
        if map_key in seen_map_keys:
            logger.info(f"跳过重复地图图表：X={x}, Y={y}")
            continue
        seen_map_keys.add(map_key)
        fixed_configs.append(cfg)

    return fixed_configs


# ====== Tab 分类规则 ======
_CHART_TAB_MAP: dict = {
    "line": "趋势洞察", "area": "趋势洞察", "candlestick": "趋势洞察",
    "bar": "分类分析", "horizontal_bar": "分类分析", "stacked_bar": "分类分析",
    "grouped_bar": "分类分析", "pie": "分类分析", "treemap": "分类分析",
    "radar": "分类分析", "sankey": "分类分析", "funnel": "分类分析",
    "map": "分类分析", "map_3d": "分类分析", "wordcloud": "分类分析",
    "sunburst": "分类分析", "waterfall": "分类分析", "box": "分类分析",
    "polar": "分类分析", "parallel": "分类分析",
    "table": "明细查询", "gauge": "数据总览",
}
_TREND_TYPES = {"scatter", "bubble", "heatmap"}
_TAB_MAX_CHARTS: dict = {"趋势洞察": 4, "分类分析": 6}

_ANALYSIS_TAB_MAP: dict = {
    "overview": "数据总览", "growth_analysis": "趋势洞察",
    "comparison_analysis": "分类分析", "structure_analysis": "分类分析",
    "ranking_analysis": "分类分析", "distribution_analysis": "分类分析",
    "correlation_analysis": "分类分析", "concentration_analysis": "分类分析",
    "proportion_analysis": "分类分析", "anomaly_analysis": "明细查询",
    "detail": "明细查询",
}


def _classify_chart_to_tab(chart: dict, time_dimension: str = "") -> str:
    """将图表分配到对应的 Tab"""
    at = chart.get("analysis_type", "")
    ct = chart.get("type", "")
    if at in _ANALYSIS_TAB_MAP:
        return _ANALYSIS_TAB_MAP[at]
    if ct in _TREND_TYPES:
        x = chart.get("x", "")
        return "趋势洞察" if (x and time_dimension and x.lower() == time_dimension.lower()) else "分类分析"
    return _CHART_TAB_MAP.get(ct, "分类分析")


def classify_charts_by_tab(charts: list, time_dimension: str = "") -> dict:
    """将图表列表按 Tab 分类并限制数量"""
    tabs: dict = {"数据总览": [], "趋势洞察": [], "分类分析": [], "明细查询": []}
    for chart in charts:
        if chart.get("type") == "table":
            continue
        tab = _classify_chart_to_tab(chart, time_dimension)
        if tab in tabs:
            tabs[tab].append(chart)
    for tab_name, limit in _TAB_MAX_CHARTS.items():
        if len(tabs[tab_name]) > limit:
            tabs[tab_name] = tabs[tab_name][:limit]
    return tabs


class DashboardRequest(BaseModel):
    session_id: str


class DashboardChartRequest(DashboardRequest):
    charts: Optional[List[dict]] = None  # 自定义图表配置列表


class DashboardRecommendRequest(DashboardRequest):
    api_key: Optional[str] = ""
    base_url: Optional[str] = None
    model: Optional[str] = None


class SaveChartRequest(DashboardRequest):
    title: str
    option: dict
    chart_type: Optional[str] = ""
    table_data: Optional[dict] = None


class DeleteSavedChartRequest(DashboardRequest):
    index: Optional[int] = None


@router.post("/dashboard/kpis")
async def api_kpis(req: DashboardRequest):
    """获取 KPI 指标"""
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")
    kpis = calculate_kpis(df)
    return sanitize_json({"success": True, "kpis": kpis})


@router.post("/dashboard/echarts")
async def api_dashboard_echarts(req: DashboardChartRequest):
    """获取仪表盘图表（ECharts 格式）"""
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")

    from src.dashboard_builder import get_default_echart_configs
    if req.charts and len(req.charts) > 0:
        configs = req.charts
    else:
        configs = get_default_echart_configs(df)

    # ★ 地图配置预处理：自动修正 X 轴 + 去重
    configs = _normalize_map_configs(df, configs)

    result = []
    for cfg in configs:
        chart_type = cfg.get("chart_type", "bar")
        x = cfg.get("x") or ""
        y = cfg.get("y")
        title_str = cfg.get("title", f"{chart_type} 图表")

        # 雷达图/热力图/箱线图（仅数值列时 x 可为空）
        no_x_ok = chart_type in ('heatmap', 'radar', 'box')
        if not x and not no_x_ok:
            continue

        try:
            kwargs = {"x": x, "title": title_str}
            if y:
                kwargs["y"] = y
            if cfg.get("color"):
                kwargs["color"] = cfg["color"]
            option = create_echart(df, chart_type, **kwargs)
            if option:
                result.append({
                    "title": title_str,
                    "option": option,
                    "type": chart_type,
                    "x": x,
                    "y": y or "",
                    "analysis_type": cfg.get("analysis_type", ""),
                })
        except Exception as e:
            logger.warning(f"ECharts 图表生成失败 [{chart_type}] x={x}: {e}")
            continue

    # 识别时间维度列
    time_col = ""
    for c in df.columns:
        if any(kw in str(c).lower() for kw in ['日期', '时间', '月份', '年份', 'date', 'month', 'year']):
            time_col = c
            break

    tabs = classify_charts_by_tab(result, time_col)
    return sanitize_json({"success": True, "tabs": tabs, "charts": result})


# ===== V1 图表收藏（兼容旧前端） =====
@router.post("/dashboard/save-chart")
async def api_save_chart(req: SaveChartRequest):
    """保存单个图表到仪表盘"""
    chart = {"title": req.title, "option": req.option,
             "type": req.chart_type, "table_data": req.table_data}
    manager.save_chart(req.session_id, chart)
    total = len(manager.get_saved_charts(req.session_id))
    return sanitize_json({"success": True, "saved": chart, "total": total, "message": f"已保存「{req.title}」"})


@router.post("/dashboard/saved-charts")
async def api_saved_charts(req: DashboardRequest):
    """获取已保存的图表列表"""
    charts = manager.get_saved_charts(req.session_id)
    return sanitize_json({"success": True, "charts": charts, "total": len(charts)})


@router.post("/dashboard/delete-saved-chart")
async def api_delete_saved_chart(req: DeleteSavedChartRequest):
    """删除已保存的图表"""
    if req.index is not None:
        success = manager.delete_saved_chart(req.session_id, req.index)
    else:
        manager.clear_saved_charts(req.session_id)
        success = True
    return sanitize_json({"success": success})


# ===== V2 分析包读取 =====
@router.post("/dashboard/saved-packages")
async def api_saved_packages(req: DashboardRequest):
    """获取已保存的分析包（含渲染后的 KPI/Table/Chart/Insight/Conclusion）"""
    packages = manager.get_saved_packages_full(req.session_id)
    return sanitize_json({"success": True, "packages": packages, "total": len(packages)})





# ===== V5: Card Generator API =====
class CardsGenerateRequest(BaseModel):
    session_id: str



@router.post('/dashboard/cards')
async def api_generate_cards(req: CardsGenerateRequest):
    """V5: Card Generator - 将 AnalysisPackage 转换为 CardPackage"""
    from backend.services.session_manager import manager
    from src.card_generator import CardGenerator

    packages = manager.get_saved_packages_full(req.session_id)
    if not packages:
        return {
            'success': True,
            'cards': [],
            'meta': {'total_cards': 0, 'insight_strength': 0, 'data_quality': 0},
        }

    generator = CardGenerator()
    all_cards = []
    all_meta = []

    for pkg in packages:
        result = generator.generate(pkg)
        all_cards.extend(result['cards'])
        all_meta.append(result['meta'])

    # Sort all cards by score globally
    all_cards.sort(key=lambda x: x.get('score', 0), reverse=True)

    # Global meta
    avg_strength = sum(m.get('insight_strength', 0) for m in all_meta) / max(len(all_meta), 1)
    avg_quality = sum(m.get('data_quality', 0) for m in all_meta) / max(len(all_meta), 1)

    return {
        'success': True,
        'cards': all_cards,
        'meta': {
            'total_cards': len(all_cards),
            'insight_strength': round(avg_strength, 2),
            'data_quality': round(avg_quality, 2),
        },
    }

