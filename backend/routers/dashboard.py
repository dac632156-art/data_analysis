"""
仪表盘 API 路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import json
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from backend.services.session_manager import manager
from src.dashboard_builder import calculate_kpis, get_default_charts, create_chart_configs
from src.echart_generator import create_chart as create_echart
from src.echart_generator import _to_geo_name, _PROVINCE_CENTROIDS, _GEO_PROVINCE_NAMES

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
    "overview": "数据总览", "trend": "趋势洞察",
    "comparison": "分类分析", "composition": "分类分析",
    "ranking": "分类分析", "distribution": "分类分析",
    "correlation": "分类分析", "geography": "分类分析",
    "anomaly": "明细查询", "detail": "明细查询",
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


@router.post("/dashboard/kpis")
async def api_kpis(req: DashboardRequest):
    """获取 KPI 指标"""
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")
    kpis = calculate_kpis(df)
    return {"success": True, "kpis": kpis}


@router.post("/dashboard/charts")
async def api_dashboard_charts(req: DashboardChartRequest):
    """获取仪表盘图表（支持自定义配置）"""
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")
    
    if req.charts and len(req.charts) > 0:
        charts = create_chart_configs(df, req.charts)
    else:
        charts = get_default_charts(df)
    
    result = []
    for chart in charts:
        fig_json = json.loads(chart["figure"].to_json()) if hasattr(chart["figure"], 'to_json') else None
        result.append({
            "title": chart["title"],
            "figure": fig_json,
        })
    return {"success": True, "charts": result}


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
    return {"success": True, "tabs": tabs, "charts": result}


@router.post("/dashboard/recommend")
async def api_dashboard_recommend(req: DashboardRecommendRequest):
    """AI 推荐仪表盘图表"""
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")
    
    api_key = req.api_key or manager.get_api_key(req.session_id)
    if not api_key:
        raise HTTPException(status_code=400, detail="需要 AI API Key")
    
    try:
        from src.ai_agent.agent import DataAnalysisAgent
        import pandas as pd
        
        kwargs = {"api_key": api_key}
        if req.base_url:
            kwargs["base_url"] = req.base_url
        if req.model:
            kwargs["model"] = req.model
        agent = DataAnalysisAgent(**kwargs)
        
        # 构造推荐 prompt
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
        
        data_info = f"""数据概况：
- 行数: {len(df)}
- 列名: {list(df.columns)}
- 数值列: {numeric_cols}
- 文本/分类列: {cat_cols}
- 各列前5行样本:
{df.head(5).to_string()}"""

        prompt = f"""请根据以下数据，推荐 6-8 个适合放在仪表盘上的图表。返回严格的 JSON 数组格式。

{data_info}

每个图表对象格式：
{{"chart_type": "bar/line/scatter/pie/histogram/box/heatmap/stacked_bar/map_3d", "x": "列名", "y": "列名或空", "title": "图表中文标题", "table_type": "null/sort/summary/cross/correlation"}}

请严格遵循以下图表和表格推荐规则：

1. 趋势/走势类 → 折线图（看整体走向），table_type=null
2. 同比/环比类 → 折线图 + 排序表格（图看趋势，表看具体增减%），table_type=sort
3. 对比/排名类 → 柱状图 + 排序表格（图看高低，表看精确数值），table_type=sort
4. 占比/比例类 → 饼图 + 汇总表格（图看比例，表看各分类具体值），table_type=summary
5. 地区分布类 → 3D 地图 + 汇总表格（图看全国分布，表看各省数据），table_type=summary，chart_type=map_3d
   ★ 重要：如果数据同时有「省份」和「地区」两列，地图 X 轴必须用「省份」列！因为「地区」值是华东/华北等大区名，不能匹配中国地图
6. 交叉分析类 → 堆叠柱状图 + 交叉表格（图看大致，表看交叉明细），table_type=cross，chart_type=stacked_bar
7. 相关性类 → 散点图 + 相关系数表格，table_type=correlation，chart_type=scatter
8. 分布类 → 直方图（纯图即可），table_type=null，chart_type=histogram

要求：
- 图表类型要多样，严格按上述规则匹配
- 标题用中文，简洁直观
- y 对于饼图/直方图可留空字符串
- table_type 必须填写，可选值：null/sort/summary/cross/correlation
- 只返回 JSON 数组，不要其他文字"""

        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            response = await loop.run_in_executor(
                executor,
                lambda: agent.client.chat.completions.create(
                model=agent.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1024,
            )
        )
        
        text = response.choices[0].message.content.strip()
        # 提取 JSON
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        recommendations = json.loads(text)
        
        return {"success": True, "recommendations": recommendations}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 推荐失败: {str(e)}")


@router.post("/dashboard/ai-layout")
async def api_ai_layout(req: DashboardRecommendRequest):
    """AI 推荐大屏布局和图表配置"""
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")
    
    api_key = req.api_key or manager.get_api_key(req.session_id)
    if not api_key:
        raise HTTPException(status_code=400, detail="需要 AI API Key")
    
    try:
        from src.ai_agent.agent import DataAnalysisAgent
        
        kwargs = {"api_key": api_key}
        if req.base_url: kwargs["base_url"] = req.base_url
        if req.model: kwargs["model"] = req.model
        agent = DataAnalysisAgent(**kwargs)
        
        # 数据概况
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
        
        data_info = f"""
数据列：{list(df.columns)}
行数：{len(df)}
数值列：{numeric_cols}
分类列：{cat_cols}
前3行：{df.head(3).to_string()}"""
        
        prompt = f"""你是 BI 大屏专家。请根据数据推荐最佳大屏布局和图表配置。

数据概况：
{data_info}

可用模板（仅以下 2 个，前端真实支持，不要返回其他值）：
1. command（指挥中心）- 中国地图 + 左右数据面板 + 排行榜 + 飞线大屏，适合含地区/省份列的数据
2. medical（数据看板）- 顶部KPI数字卡 + 4个Tab导航 + 环形图 + 同环比表格，适合多维度综合分析

选择指导：
- 数据含「地区」「省份」「城市」等地理列 → command
- 其他情况（普通数值/分类/时间列）→ medical

请严格遵循以下图表和表格推荐规则分配图表类型：
1. 趋势/走势类 → 折线图（table_type=null）
2. 同比/环比类 → 折线图 + 排序表格（table_type=sort）
3. 对比/排名类 → 柱状图 + 排序表格（table_type=sort）
4. 占比/比例类 → 饼图 + 汇总表格（table_type=summary）
5. 地区分布类 → 3D地图 + 汇总表格（table_type=summary），chart_type=map_3d
   ★ 如果数据有「省份」列，地图 X 轴必须用「省份」而非「地区」（因为「地区」值是大区名，无法匹配地图）
6. 交叉分析类 → 堆叠柱状图 + 交叉表格（table_type=cross）
7. 相关性类 → 散点图 + 相关系数表格（table_type=correlation）
8. 分布类 → 直方图（table_type=null）

请返回严格 JSON：
{{
  "recommended_template": "command/medical",
  "reason": "推荐理由（中文，一句话）",
  "block_title": "大屏标题",
  "charts": [
    {{"chart_type": "bar/line/pie...", "x": "列名", "y": "列名或空", "title": "图名", "position": "main/left/right/top/bottom", "table_type": "null/sort/summary/cross/correlation"}}
  ]
}}

要求：推荐5-8个图表，覆盖不同角度，严格按规则匹配。position用main（主图区）、top（顶部小图）、left/right（左右列）、bottom（底部）。table_type必填。"""

        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as exec2:
            response = await loop.run_in_executor(
                exec2,
                lambda: agent.client.chat.completions.create(
                model=agent.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3, max_tokens=1024,
            )
        )
        
        text = response.choices[0].message.content.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"): text = text[4:]
        layout = json.loads(text)
        
        # 根据推荐模板生成实际图表
        chart_configs = layout.get("charts", [])
        charts_result = create_chart_configs(df, chart_configs)
        result_list = []
        for chart in charts_result:
            fig_json = json.loads(chart["figure"].to_json()) if hasattr(chart["figure"], 'to_json') else None
            result_list.append({
                "title": chart["title"],
                "figure": fig_json,
            })
        
        return {
            "success": True,
            "recommended_template": layout.get("recommended_template", "medical"),
            "reason": layout.get("reason", "AI 推荐"),
            "block_title": layout.get("block_title", "数据分析看板"),
            "charts": result_list,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 布局推荐失败: {str(e)}")


# ====== 图表收藏 API（分析页 → 仪表盘） ======

class SaveChartRequest(BaseModel):
    session_id: str
    title: str
    option: dict  # ECharts option 对象
    chart_type: str = ''  # 图表类型：'' / 'table'（同环比）
    table_data: dict | None = None  # 同环比表格数据 {rows, value_column, current_year, previous_year, has_yoy}

class SessionRequest(BaseModel):
    session_id: str


@router.post("/dashboard/save-chart")
async def api_save_chart(req: SaveChartRequest):
    """将分析页生成的图表保存到仪表盘收藏"""
    chart: dict = {"title": req.title, "option": req.option}
    if req.chart_type:
        chart["chart_type"] = req.chart_type
    if req.table_data:
        chart["table_data"] = req.table_data
    manager.save_chart(req.session_id, chart)
    total = len(manager.get_saved_charts(req.session_id))
    return {"success": True, "message": f"已保存（共 {total} 个图表）", "total": total}


@router.post("/dashboard/saved-charts")
async def api_get_saved_charts(req: SessionRequest):
    """获取所有已保存的图表"""
    charts = manager.get_saved_charts(req.session_id)
    return {"success": True, "charts": charts, "total": len(charts)}


@router.post("/dashboard/delete-saved-chart")
async def api_delete_saved_chart(req: SessionRequest):
    """清空所有已保存图表"""
    manager.clear_saved_charts(req.session_id)
    return {"success": True, "message": "已清空所有保存的图表"}
