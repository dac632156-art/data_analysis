"""
仪表盘 API 路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import logging
import json
import re
from concurrent.futures import ThreadPoolExecutor

from backend.services.session_manager import manager

from src.echart_generator import create_chart as create_echart
from src.echart_generator import _to_geo_name, _PROVINCE_CENTROIDS, _GEO_PROVINCE_NAMES
from src.utils.json_serializer import sanitize_json
import pandas as pd

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


def _extract_chart_configs_from_packages(packages: list) -> list:
    """从已保存的分析包中提取图表配置列表（直接遍历 charts，原样携带已渲染 option）

    【2026-07-11 修复】旧逻辑遍历 pkg.chart_data，再按索引 i 从 pkg.charts[i] 取 option——
    一旦 chart_data 与 charts 不同序、或某图 option 为空，便回退 create_echart 重算，
    重算失败即跳过，导致「保存后看板/报告缺图」（典型为原「辅图」：bar/box/radar/heatmap/词云…）。

    新逻辑直接遍历 pkg.charts（由 ChartRenderer.render_all 生成，已含 chart_type/x/y/title/option，
    且 role 现已统一为 primary），原样携带 option；option 为空时仍回退 create_echart 重算兜底。
    每张已保存的图都进入 configs，不再因索引配对脆弱而丢失。

    返回格式与 get_default_echart_configs 兼容（额外携带 option 字段）。
    """
    configs = []
    seen_slots: Dict[str, int] = {}   # 防 slot 重复：analysis 包可能复用同一 slot
    for pkg in packages:
        if not isinstance(pkg, dict):
            continue
        analysis_type = pkg.get("analysis_type", "")
        pkg_charts = pkg.get("charts", []) or []
        # ★ 建 slot→chart_data 映射，用于把 data/color/right_col 补入 cfg
        chart_data_map = {}
        for cd in (pkg.get("chart_data") or []):
            if isinstance(cd, dict) and cd.get("slot"):
                chart_data_map[cd["slot"]] = cd
        for chart in pkg_charts:
            if not isinstance(chart, dict):
                continue
            ct = chart.get("chart_type", "bar")
            x = chart.get("x", "")
            y = chart.get("y", "")
            title = chart.get("title", f"{analysis_type} 图表")
            # 原样携带已渲染 option（空则留空，由 api_dashboard_echarts 回退 create_echart）
            option = chart.get("option", "") or ""
            chart_slot = chart.get("slot", "")
            # ★ 兜底：pkg.charts 里若没 slot，按 (analysis_type, chart_type, x, y, title) 生成稳定 id
            if not chart_slot:
                import hashlib
                seed = f"{analysis_type}|{ct}|{x}|{y}|{title}".encode("utf-8")
                chart_slot = "pkg_" + hashlib.md5(seed).hexdigest()[:10]
            # ★ 防重复：analysis 包里可能有多张图复用同一 slot（如 hbar__attr_dim_offset），
            #   导致前端 chartMap 覆盖 + React key 冲突。强制追加全局序号保证唯一。
            base_slot = chart_slot
            dup = seen_slots.get(base_slot, 0)
            seen_slots[base_slot] = dup + 1
            chart_slot = base_slot if dup == 0 else f"{base_slot}_{dup}"
            # ★ 从 chart_data 补齐 data/color/right_col（用于重渲染兜底）
            #   注意：chart_data_map 的 key 是「原始 slot」（未加 _dup 后缀），
            #   所以必须用 base_slot 而不是 chart_slot 查，否则永远查不到。
            cd = chart_data_map.get(base_slot, {})
            cfg = {
                "slot": chart_slot,                # 智能排版前端按 slot 查 chartMap 必须有
                "chart_type": ct,
                "x": x,
                "y": y,
                "title": title,
                "analysis_type": analysis_type,
                "option": option,
                "table_data": chart.get("table_data") or None,
            }
            if cd.get("data"):
                cfg["data"] = cd["data"]
            if cd.get("color"):
                cfg["color"] = cd["color"]
            if cd.get("right_col"):
                cfg["right_col"] = cd["right_col"]
            configs.append(cfg)
    return configs


def _pick_columns(df: Any, name_keywords: List[str]) -> Optional[str]:
    """根据关键字列表从 df 列名里挑一个最匹配的列（大小写不敏感、子串命中）。"""
    if df is None or not hasattr(df, "columns"):
        return None
    cols = list(getattr(df, "columns", []))
    low = {str(c).lower(): c for c in cols}
    for kw in name_keywords:
        kw_l = kw.lower()
        for c in cols:
            if kw_l in str(c).lower():
                return c
    return None


def _build_default_configs_from_df(df: Any, max_n: int = 8) -> list:
    """基于 df 列名智能生成默认 ECharts 图表配置（用于 saved/analysis 都为空时的兜底）。

    目的：让 LLM 排版引擎始终能拿到候选清单（哪怕用户没跑过 analysis），
    同时让经典网格/智能排版都至少能看到几张基础图。

    规则（按列名关键字匹配，匹配不到就跳过）：
    - 时间列（日期/时间/order_date/month）   → line（销售金额/利润金额）
    - 类别列（地区/省份/产品类别/产品名称/渠道）→ pie（销售金额）+ bar（销售金额）
    - 数值列（销售金额/利润金额/客户数量）   → hbar / ranking
    - 数量 vs 金额                              → dual_axis
    """
    configs: list = []
    if df is None or not hasattr(df, "columns") or len(getattr(df, "columns", [])) == 0:
        return configs
    try:
        cols = list(df.columns)
    except Exception:
        return configs

    time_col = _pick_columns(df, ["日期", "时间", "date", "month", "下单时间"])
    cat_col = _pick_columns(df, ["产品类别", "产品名称", "省份", "地区", "渠道"])
    revenue_col = _pick_columns(df, ["销售金额", "销售额", "GMV", "amount", "revenue"])
    profit_col = _pick_columns(df, ["利润金额", "利润", "profit", "毛利"])
    qty_col = _pick_columns(df, ["销售数量", "数量", "qty", "quantity"])
    cust_col = _pick_columns(df, ["客户数量", "客户数", "客户", "users"])
    returns_col = _pick_columns(df, ["退货数", "退货", "return"])

    # 优先级推荐表
    recommendations: List[Dict[str, Any]] = []
    if time_col and revenue_col:
        recommendations.append({"chart_type": "line", "x": time_col, "y": revenue_col, "title": f"{revenue_col}趋势（按{time_col}）"})
        recommendations.append({"chart_type": "line", "x": time_col, "y": profit_col or revenue_col, "title": f"{profit_col or revenue_col}趋势"})
    if cat_col and revenue_col:
        recommendations.append({"chart_type": "pie", "x": cat_col, "y": revenue_col, "title": f"{cat_col}销售额占比"})
        recommendations.append({"chart_type": "bar", "x": cat_col, "y": revenue_col, "title": f"{cat_col}销售额排名"})
    if revenue_col:
        recommendations.append({"chart_type": "ranking", "x": cat_col or time_col or "", "y": revenue_col, "title": f"{revenue_col}排行榜"})
    if profit_col and revenue_col:
        recommendations.append({"chart_type": "dual_axis", "x": cat_col or time_col or "", "y": revenue_col, "title": f"{revenue_col} vs {profit_col}", "right_col": profit_col})
    if returns_col and cat_col:
        recommendations.append({"chart_type": "bar", "x": cat_col, "y": returns_col, "title": f"{cat_col}{returns_col}"})
    if cust_col and cat_col:
        recommendations.append({"chart_type": "hbar", "x": cat_col, "y": cust_col, "title": f"{cat_col}客户数"})

    # 调 create_chart 渲染 option；失败则跳过
    for rec in recommendations[:max_n]:
        try:
            kwargs = {"x": rec["x"], "title": rec["title"]}
            if rec.get("y"):
                kwargs["y"] = rec["y"]
            if rec.get("right_col"):
                kwargs["right_col"] = rec["right_col"]
            option = create_echart(df, rec["chart_type"], **kwargs)
        except Exception:
            option = None
        if not option:
            continue
        cfg = {
            "chart_type": rec["chart_type"],
            "type": rec["chart_type"],
            "x": rec.get("x", ""),
            "y": rec.get("y", ""),
            "title": rec["title"],
            "option": option,
            "analysis_type": "default",
            "slot": f"default_{rec['chart_type']}_{len(configs)}",
        }
        configs.append(cfg)

    return configs


class DashboardRequest(BaseModel):
    session_id: str


class DashboardChartRequest(DashboardRequest):
    charts: Optional[List[dict]] = None  # 自定义图表配置列表


class DashboardRecommendRequest(DashboardRequest):
    api_key: Optional[str] = ""
    base_url: Optional[str] = None
    model: Optional[str] = None


class SmartLayoutRequest(DashboardRequest):
    """智能排版请求：复用 /dashboard/echarts 的数据源（已保存分析包的图表配置），
    不直接传 charts；LLM 配置由前端透传。"""
    api_key: Optional[str] = ""
    base_url: Optional[str] = None
    model: Optional[str] = None
    top_n: Optional[int] = 12
    refresh: Optional[bool] = False     # True=强制 LLM 重新排版（忽略任何缓存）



class SaveChartRequest(DashboardRequest):
    title: str
    option: dict
    chart_type: Optional[str] = ""
    table_data: Optional[dict] = None


class DeleteSavedChartRequest(DashboardRequest):
    index: Optional[int] = None


@router.post("/dashboard/kpis")
async def api_kpis(req: DashboardRequest):
    """获取 KPI 指标。

    数据源严格只来自 saved_packages（用户主动保存的分析结果）。
    未保存分析时返回空列表，让前端显示「暂无图表，请先在数据分析页生成并收藏」。
    这样彻底避免「上传新数据后仪表盘显示旧测试 KPI」和「未分析自动出现兜底 KPI」两类问题。
    """
    packages = manager.get_saved_packages_full(req.session_id) or []
    kpis = []
    for pkg in packages:
        for k in (pkg.get("rendered_kpis") or []):
            if isinstance(k, dict) and k.get("label"):
                kpis.append(k)

    return sanitize_json({"success": True, "kpis": kpis})





@router.post("/dashboard/echarts")
async def api_dashboard_echarts(req: DashboardChartRequest):
    """获取仪表盘图表（ECharts 格式）

    优先级：
    1. 请求中传入的 charts → 直接使用
    2. 已保存的分析包中的 chart_data → 从分析结果提取
    3. 默认图表配置 → 兜底（首次使用、无分析结果时）
    """
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")


    if req.charts and len(req.charts) > 0:
        configs = req.charts
    else:
        # ★ 优先使用已保存的分析结果中的图表数据
        packages = manager.get_saved_packages_full(req.session_id) or []
        configs = _extract_chart_configs_from_packages(packages)
        # ★ 不再做 df 兜底：未保存分析时返回空 configs，让前端显示空状态，
        #   彻底避免「上传新数据后仪表盘自动出现非用户主动分析的内容」。

    # ★ 地图配置预处理：自动修正 X 轴 + 去重
    configs = _normalize_map_configs(df, configs)

    result = []
    for cfg in configs:
        chart_type = cfg.get("chart_type", "bar")
        x = cfg.get("x") or ""
        y = cfg.get("y")
        title_str = cfg.get("title", f"{chart_type} 图表")

        try:
            # ★ 优先复用已保存分析包中渲染好的 option（排序/聚合已固化），
            #   不再拿原始 df 重新聚合（否则丢图、排序错）。仅 option 缺失时回退重算。
            existing_option = cfg.get("option")

            # 雷达图/热力图/箱线图、以及同期群系列图（option 自带完整坐标，x 可为空）
            no_x_ok = chart_type in ('heatmap', 'radar', 'box',
                                     'cohort_heatmap', 'cohort_stacked',
                                     'cohort_line', 'cohort_active_line',
                                     'cohort_trend', 'dual_axis')
            # ★ 修复：仅在「无 option 且缺 x」时才跳过；已渲染好的 option 直接下发，
            #   不再因 x 为空而误杀同期群图（旧逻辑在取 existing_option 之前就 continue）。
            if not existing_option and not x and not no_x_ok:
                continue

            # ★ 词云专项（2026-07-13 修复「看板词云全黑」）：已保存包里的词云 option
            #   可能由旧版代码生成，携带损坏/失效的 textStyle.color ——
            #   旧版 function(word, params){ word.charCodeAt } 会在 echarts 以 function(params)
            #   调用时抛错；或旧版 array 形式 color 不被 echarts-wordcloud 2.1.0 支持 → 整图黑/空白。
            #   词云仅是频率云、无用户定制需保留，故始终用当前 create_wordcloud 重算，
            #   保证下发给前端的 color 一定是合法 function 字符串（前端再水合为真实 function）。
            if chart_type == 'wordcloud':
                try:
                    regen = create_echart(df, 'wordcloud', x=x, title=title_str)
                    if regen:
                        existing_option = regen
                except Exception as e:
                    logger.warning(f"词云重算失败，沿用已保存 option: {e}")

            # ★ RFM 双轴图专项（2026-08-03 修复「Avg.Profit Margin 离谱」）：
            #   已保存包里的 rfm_dual option 是旧版代码生成的（左轴错填人数、
            #   y 字段错配），前端按 金额÷金额 算毛利率会产生万倍率。
            #   rfm.py 已修好 dual_rows 真值（人数/净GMV/净毛利），但 DashboardPage
            #   默认复用已保存 option 不重算 → 屏幕上仍显示旧数字。
            #   故对 dual_axis + slot==rfm_dual 始终用当前 RFMModel 重算，
            #   保证下发的 option 来自当前修正后的逻辑。
            if chart_type == 'dual_axis' and cfg.get('slot') == 'rfm_dual':
                try:
                    from src.analysis_engine.models.rfm import RFMModel
                    from src.chart_renderer import ChartRenderer
                    pkg = RFMModel().compute(df)
                    new_cd = next((c for c in pkg.chart_data if c.slot == 'rfm_dual'), None)
                    if new_cd:
                        regen = ChartRenderer().render(new_cd)
                        if regen:
                            existing_option = regen.option
                except Exception as e:
                    logger.warning(f"RFM 双轴重算失败，沿用已保存 option: {e}")

            if existing_option:
                result.append({
                    "title": title_str,
                    "option": existing_option,
                    "type": chart_type,
                    "chart_type": chart_type,
                    "table_data": cfg.get("table_data") or None,
                    "x": x,
                    "y": y or "",
                    "analysis_type": cfg.get("analysis_type", ""),
                    # ★ 方案B：同期群扁平清单随 option 一并发下，前端仙气矩阵组件直接消费，
                    #   不再依赖前端从 option.series 反推（更稳，结构不再耦合）。
                    "raw_data": cfg.get("data") if chart_type == "cohort_heatmap" else None,
                })
                continue

            kwargs = {"x": x, "title": title_str}
            if y:
                kwargs["y"] = y
            if cfg.get("color"):
                kwargs["color"] = cfg["color"]
            if cfg.get("right_col"):
                kwargs["right_col"] = cfg["right_col"]
            # ★ 若 cfg 携带 ChartData 原始数据（含 CLV 等计算列），用它构造局部 df；
            #    否则用 session 原始 df（老图/简单图的路）。
            chart_df = df
            if cfg.get("data"):
                try:
                    chart_df = pd.DataFrame(cfg["data"])
                except Exception:
                    chart_df = df
            option = create_echart(chart_df, chart_type, **kwargs)
            if option:
                result.append({
                    "title": title_str,
                    "option": option,
                    "type": chart_type,
                    "chart_type": chart_type,
                    "table_data": cfg.get("table_data") or None,
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


# ===== 智能排版（LLM 驱动的经典网格大屏） =====

@router.post("/dashboard/smart-layout")
async def api_dashboard_smart_layout(req: SmartLayoutRequest):
    """智能排版大屏：经典网格图表全量数据 → profiling 降噪 → LLM 选图+打分 → 排版 JSON。

    复用 /dashboard/echarts 的数据源（已保存分析包的图表配置），但只对
    _extract_chart_configs_from_packages 的结果做「元信息降噪」，不重复渲染 option。
    返回 SmartLayoutResponse：items[]（含融合后的 attention_weight）+ charts（原始
    渲染好的图表项，供前端按 slot 直接取 option 渲染）。

    完全不影响 /dashboard/echarts 与 /dashboard/schema。
    """
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")

    # 数据源：优先已保存分析包；若为空则聚合 analysis_packages / dataset_packages
    # （避免「经典网格能出图、智能排版却空」——两者应同源）。
    # 数据源：优先已保存分析包；若为空则聚合 analysis_packages / dataset_packages
    # （避免「经典网格能出图、智能排版却空」——两者应同源）。
    packages = manager.get_saved_packages_full(req.session_id) or []
    configs = _extract_chart_configs_from_packages(packages)
    if not configs:
        session = manager.get_session(req.session_id)
        if session:
            raw_pkgs: Dict[str, Any] = {}
            if isinstance(getattr(session, "analysis_packages", None), dict):
                raw_pkgs.update(session.analysis_packages)
            for bucket in getattr(session, "dataset_packages", {}).values():
                if isinstance(bucket, dict):
                    raw_pkgs.update(bucket)
            configs = _extract_chart_configs_from_packages(list(raw_pkgs.values()))
        # ★ 不再基于 df 生成默认图：未保存分析时返回空，让前端显示空状态。
    if not configs:
        # 仍为空：确实没有任何分析产出
        return sanitize_json({"success": True, "source": "empty", "items": [], "charts": []})

    # ① profiling 降噪 → 候选清单
    #   - to_candidate_list_full：全量候选（用于全量 items 渲染，展示与经典网格相同数量的图）
    #   - profile_full：全量 profile（携带 sbv，供融合与兜底）
    #   - top_n 仅控制「LLM 精排窗口」大小（省 token），不再截断可见图表数量
    from src.dashboard.profiling_engine import ProfilingEngine
    profiler = ProfilingEngine(top_n=req.top_n or 12)
    candidates = profiler.to_candidate_list_full(configs)   # 全量候选
    profiles = profiler.profile_full(configs)              # 全量 profile（带 sbv）

    # ② LLM 排版决策（仅 Top-N 精排，失败自动回退规则布局）
    from src.dashboard.llm_layout_engine import LLMLayoutEngine
    engine = LLMLayoutEngine(
        api_key=req.api_key or "",
        base_url=req.base_url,
        model=req.model or "gpt-3.5-turbo",
    )
    resp = engine.layout(candidates, fallback_profiles=profiles, llm_top_n=req.top_n or 12)

    # ★ 关键修复：把每个 AnalysisPackage.tables 转换成 chart_type='table' 的图，
    #   否则后端 RFM/KMeans/CLV/UserProfile 等模型产出的明细表格（region_best /
    #   summary / profile_overview / sort / cross / correlation 等 table_type）
    #   会被丢弃，前端 ECharts 大屏永远看不到表格图。
    #   转换规则：option 注入 ECharts table series（columns + rows），table_data 同步携带，
    #   让前端 EtherealTable / ChartRegistry 兜底逻辑都能渲染（之前已修）。
    table_charts: List[Dict[str, Any]] = []
    for pkg in packages:
        for tbl in (pkg.get("tables") or []):
            if not isinstance(tbl, dict):
                continue
            cols = tbl.get("columns") or []
            rows = tbl.get("rows") or []
            if not cols and not rows:
                continue
            slot_id = tbl.get("slot") or f"tbl_{abs(hash(str(tbl.get('title','')))) % (10**8):08x}"
            option = {
                "title": tbl.get("title", ""),
                "series": [{
                    "type": "table",
                    "columns": cols,
                    "rows": rows,
                    "table_type": tbl.get("table_type", ""),
                }],
            }
            table_charts.append({
                "slot": slot_id,
                "title": tbl.get("title", ""),
                "chart_type": "table",
                "option": option,
                "table_data": {
                    "columns": cols,
                    "rows": rows,
                    "table_type": tbl.get("table_type", ""),
                },
                "raw_data": rows,
                "x": "",
                "y": "",
                "analysis_type": pkg.get("analysis_type", "table"),
            })

    # ③ 组装前端可直接渲染的 charts（全量，按 slot 回查完整 option）
    chart_lookup = profiler.build_lookup(configs)
    smart_charts = []
    for c in configs:
        slot = c.get("slot") or ""
        smart_charts.append({
            "slot": slot,
            "title": c.get("title", ""),
            "chart_type": c.get("chart_type", "bar"),
            "option": c.get("option"),
            "table_data": c.get("table_data") or None,
            # ★ 修复：所有 chart_type 都携带 raw_data（不只是 cohort_heatmap）。
            #   hbar / ranking / line 等组件渲染需要原始扁平清单（如 [{维度, 维度取值, 偏移值}]），
            #   仅靠 ECharts option 反推会丢字段。让前端能直接消费 cfg.data。
            "raw_data": c.get("data"),
            "x": c.get("x") or "",
            "y": c.get("y") or "",
            "analysis_type": c.get("analysis_type", ""),
        })

    # ★ 修复：把 saved_packages 里的 rendered_kpis 合并进 charts（chart_type="metric"），
    #   解决「经典网格小卡片在智能排版大屏没有」。原本 kpis 和 charts 是两个独立列表，
    #   前端 chartMap 只看 charts，导致 KPI 槽 blank。同时也再额外返回 kpis 字段
    #   供前端兜底。
    kpis_injected = []
    for pkg in packages:
        for k in (pkg.get("rendered_kpis") or []):
            if not isinstance(k, dict):
                continue
            label = k.get("label") or k.get("title") or ""
            value = k.get("value")
            if not label or value is None:
                continue
            kpi_slot = f"kpi_{abs(hash(label)) % (10**8):08x}"
            kpis_injected.append({
                "slot": kpi_slot,
                "title": str(label),
                "chart_type": "metric",
                # ★ 业务价值透传：来自 render_kpis 的 business_value 字段，
                #   前端 SmartDashboard 按此字段降序选 hero KPI，
                #   让高业务价值 KPI（GMV/利润/客单价）优先占据 4 个 [3,3,3,3] 槽位
                "business_value": float(k.get("business_value") or 0.0),
                "attention_weight": float(k.get("business_value") or 0.0),
                "option": {
                    "title": str(label),
                    "data": [
                        {
                            "title": str(label),
                            "value": value,
                            "change": k.get("change"),
                            "change_type": k.get("change_type"),
                        },
                    ],
                    "value": value,
                    "change": k.get("change"),
                    "business_value": float(k.get("business_value") or 0.0),
                },
                "table_data": None,
                "raw_data": [
                    {
                        "title": str(label),
                        "value": value,
                        "change": k.get("change"),
                        "business_value": float(k.get("business_value") or 0.0),
                    },
                ],
                "x": "",
                "y": "",
                "analysis_type": "metric",
            })

    # ★ 关键：把 kpis 和 table_charts 都 merge 进 smart_charts，前端 chartMap 才能找到它们。
    #   同时保留 kpis 字段作为前端兜底。
    smart_charts_all = list(smart_charts) + list(kpis_injected) + list(table_charts)

    return sanitize_json({
        "success": True,
        "source": resp.source,
        "model": resp.model,
        "note": resp.note,
        "items": [
            {
                "slot": it.slot,
                "title": it.title,
                "chart_type": it.chart_type,
                "analysis_type": it.analysis_type,
                "suggested_business_value": it.suggested_business_value,
                "llm_weight": it.llm_weight,
                "attention_weight": it.attention_weight,
                "shape": it.shape,
                "slot_id": it.slot_id,
                "dims": it.dims,
                "series_count": it.series_count,
                "row_count": it.row_count,
                "metric_hint": it.metric_hint,
                "value_hint": it.value_hint,
                "is_aggregated": it.is_aggregated,
            }
            for it in resp.items
        ],
        "charts": smart_charts_all,
        "kpis": kpis_injected,
    })


# ===== V1 图表收藏（兼容旧前端） =====
@router.post("/dashboard/save-chart")
async def api_save_chart(req: SaveChartRequest):
    """保存单个图表到仪表盘（同时写入 V1 saved_charts 与 V2 saved_packages，供模式A 大屏读取）"""
    import time as _time
    import random as _random

    chart = {"title": req.title, "option": req.option,
             "type": req.chart_type, "table_data": req.table_data}
    manager.save_chart(req.session_id, chart)

    # 同步写入 V2 saved_packages，使 SmartDashboard 模式A 能读到
    session = manager.get_session(req.session_id)
    if session is not None:
        pkg_id = f"v1_{int(_time.time() * 1000)}_{_random.randint(0, 9999)}"
        pkg = {
            "id": pkg_id,
            "title": req.title or "未命名图表",
            "analysis_type": req.chart_type or "chart",
            "charts": [{
                "title": req.title or "",
                "type": req.chart_type,
                "chart_type": req.chart_type,
                "option": req.option,
                "table_data": req.table_data,
            }],
            "kpis": [],
            "tables": [],
            "saved_at": _time.strftime("%Y-%m-%d %H:%M:%S"),
            "_from": "v1_save_chart",
        }
        # 去重：避免重复保存同一标题的包
        if not any(p.get("title") == pkg["title"] and p.get("_from") == "v1_save_chart"
                   for p in session.saved_packages):
            session.saved_packages.append(pkg)

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
    """获取已保存的分析包（含渲染后的 KPI/Table/Chart/Insight/Conclusion）

    ★ 与 /dashboard/smart-layout 保持一致：把每个 pkg.tables 展开成
       chart_type='table' 的 charts，并合并到 charts 列表，否则前端 SmartDashboard
       大屏永远看不到 RFM/KMeans/CLV/UserProfile 等模型产出的明细表格。
    """
    packages = manager.get_saved_packages_full(req.session_id)
    if packages:
        for pkg in packages:
            if not isinstance(pkg, dict):
                continue
            existing_charts = list(pkg.get("charts") or [])
            existing_slots = {str(c.get("slot") or "") for c in existing_charts}
            for tbl in (pkg.get("tables") or []):
                if not isinstance(tbl, dict):
                    continue
                cols = tbl.get("columns") or []
                rows = tbl.get("rows") or []
                if not cols and not rows:
                    continue
                slot_id = tbl.get("slot") or f"tbl_{abs(hash(str(tbl.get('title','')))) % (10**8):08x}"
                if slot_id in existing_slots:
                    continue
                existing_slots.add(slot_id)
                existing_charts.append({
                    "slot": slot_id,
                    "title": tbl.get("title", ""),
                    "chart_type": "table",
                    "type": "table",
                    "x": "",
                    "y": "",
                    "option": {
                        "title": tbl.get("title", ""),
                        "series": [{
                            "type": "table",
                            "columns": cols,
                            "rows": rows,
                            "table_type": tbl.get("table_type", ""),
                        }],
                    },
                    "table_data": {
                        "columns": cols,
                        "rows": rows,
                        "table_type": tbl.get("table_type", ""),
                    },
                    "raw_data": rows,
                    "data": rows,
                    "attention_weight": float(tbl.get("attention_weight") or 0.55),
                    "business_value": float(tbl.get("attention_weight") or 0.55),
                })
            if existing_charts:
                pkg["charts"] = existing_charts
    return sanitize_json({"success": True, "packages": packages, "total": len(packages)})


# ===== V6: Dashboard Schema API =====


class DashboardSchemaRequest(BaseModel):
    session_id: str
    title: Optional[str] = ""
    layout_name: Optional[str] = None


@router.post("/dashboard/schema")
async def api_dashboard_schema(req: DashboardSchemaRequest):
    packages = manager.get_saved_packages_full(req.session_id)
    if not packages:
        raise HTTPException(status_code=400, detail="没有已保存的分析结果")

    # ★ 诊断日志：确认前端传来的 layout_name
    logger.info(f"[Dashboard Schema] 收到请求: session={req.session_id[:8]}, "
                f"layout_name={repr(req.layout_name)}, packages={len(packages)}")

    # 获取 session 的 DataFrame 用于提取分类列 distinct 值
    df = manager.get_data(req.session_id)

    # ★ 自定义标题优先：若 session 中有 persistent custom_title，覆盖请求中的 title
    custom_title = manager.get_custom_title(req.session_id)
    final_title = custom_title or req.title or "数据分析驾驶舱"

    try:
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            result = await loop.run_in_executor(
                executor, _build_schema_sync, packages, final_title, req.layout_name, df,
            )
        # ★ 诊断：确认布局引擎实际使用的布局
        layout_used = result.get("schema", {}).get("metadata", {}).get("layout_selected", "?")
        logger.info(f"[Dashboard Schema] 实际使用布局: {layout_used}, widgets={len(result.get('schema', {}).get('widgets', []))}")
        return sanitize_json(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Schema 生成失败: {str(e)}")


def _build_schema_sync(packages, title, layout_name, df=None):
    from src.dashboard import WidgetGenerator, LayoutEngine
    from src.dashboard.interaction_engine import generate_interactions
    gen = WidgetGenerator()
    widgets = gen.generate_from_dicts(packages)
    widget_dicts = [w.to_dict() for w in widgets]
    engine = LayoutEngine()
    schema = engine.build(widget_dicts, title=title, layout_name=layout_name)
    schema.merge_interactions(generate_interactions(widget_dicts, schema))

    result = {"success": True, "schema": schema.to_dict()}

    # ★ 注入分类筛选器可选项（从 session DataFrame 直接取 distinct 值）
    if df is not None and not df.empty:
        filter_options = _extract_filter_options(df)
        if filter_options:
            result["schema"]["filter_options"] = filter_options

    return result


def _extract_filter_options(df):
    """从 DataFrame 提取分类列的 distinct 值，按 region/product/channel/category/time 分类"""
    rules = {
        "region":  ["省", "市", "区", "地区", "城市", "city", "region", "province", "国家", "省份"],
        "product": ["产品", "商品", "品类", "品牌", "product", "sku", "item"],
        "channel": ["渠道", "来源", "平台", "channel", "source"],
        "category": ["类别", "分类", "类型", "category", "type"],
        "time":    ["日期", "时间", "月份", "date", "month", "year", "year_month"],
    }

    def match_field(col: str) -> str:
        lower = str(col).lower()
        for fld, kws in rules.items():
            for kw in kws:
                if kw.lower() in lower:
                    return fld
        return ""

    result = {"region": [], "product": [], "channel": [], "category": [], "time": []}
    for col in df.columns:
        fld = match_field(col)
        if fld and fld != "time":
            try:
                vals = df[col].dropna().unique().tolist()
                result[fld] = [str(v) for v in vals if v not in (None, "")][:50]
            except Exception:
                pass

    return {k: v for k, v in result.items() if v}


# ===== V7: Dashboard 标题 AI 命名 + 持久化 =====

class DashboardNamingRequest(BaseModel):
    session_id: str
    api_key: Optional[str] = ""
    base_url: Optional[str] = None
    model: Optional[str] = None


class DashboardTitleRequest(BaseModel):
    session_id: str
    title: Optional[str] = ""
    action: str = "get"  # "get" | "set"


# 列名关键词匹配列表（与前端 inferIndustryTitle 同源）
_INDUSTRY_KEYWORDS = [
    (["营业额", "销售额", "售价", "sku", "库存", "订单量", "退货数", "退货率", "销量", "品类", "门店", "渠道", "零售", "商品名称"], "零售业务数据驾驶舱"),
    (["病人", "患者", "诊断", "处方", "药物", "医院", "科室", "手术", "门诊", "体检"], "医疗业务数据驾驶舱"),
    (["金额", "利率", "贷款", "存款", "投资", "收益", "基金", "股票", "债券", "收盘价", "开盘价", "账户"], "金融数据驾驶舱"),
    (["学生", "成绩", "科目", "班级", "教师", "课程", "学分", "考试", "毕业", "院系"], "教育数据驾驶舱"),
    (["员工", "部门", "薪资", "绩效", "考勤", "离职", "入职", "职称", "工龄", "人事"], "人力资源数据驾驶舱"),
    (["面积", "房价", "户型", "楼盘", "成交价", "均价", "租赁", "租金", "物业"], "房地产数据驾驶舱"),
    (["物流", "快递", "配送", "仓库", "运输", "运费", "发货", "签收", "包裹"], "物流数据驾驶舱"),
    (["产量", "良品率", "次品", "机器", "流水线", "产能", "质检", "原材料", "生产"], "生产制造数据驾驶舱"),
    (["菜品", "翻台率", "外卖", "堂食", "客单", "食材", "菜系", "配餐"], "餐饮数据驾驶舱"),
    (["省份", "城市", "地区", "区域", "地图", "省份名"], "地区数据驾驶舱"),
    (["广告", "曝光", "点击", "转化", "cpc", "cpm", "roi", "流量", "渠道"], "广告投放数据驾驶舱"),
    (["产品", "客户", "用户", "交易", "支付", "购物", "浏览", "点击", "商品", "品类"], "电商数据驾驶舱"),
]


def _infer_title_by_keywords(columns: list) -> str:
    """兜底：按列名关键词匹配标题"""
    col_str = " ".join(str(c) for c in columns).lower()
    for kws, title in _INDUSTRY_KEYWORDS:
        if any(kw.lower() in col_str for kw in kws):
            return title

    # 二级兜底：根据字段特征
    has_date = bool(re.search(r"日期|时间|月份|季度|年份|date|time|month|year", col_str))
    has_amount = bool(re.search(r"金额|价格|收入|支出|成本|利润|费用|value|amount|price", col_str))
    has_category = bool(re.search(r"类别|类型|分类|部门|地区|城市|省份", col_str))

    if has_date and has_amount and has_category:
        return "多维度业务数据驾驶舱"
    if has_date and has_amount:
        return "财务趋势数据驾驶舱"
    if has_date:
        return "时序数据驾驶舱"
    if has_amount:
        return "核心指标数据分析驾驶舱"
    return "数据智能驾驶舱"


def _build_naming_summary(packages: list, df_columns: list) -> str:
    """构建 LLM 命名的数据上下文摘要"""
    lines = []

    # 列名摘要
    lines.append(f"数据列（{len(df_columns)} 个）：{', '.join(str(c) for c in df_columns[:30])}")

    # 图表摘要
    chart_types = {}
    for pkg in packages:
        for chart in (pkg.get("charts") or pkg.get("rendered_charts") or []):
            ct = chart.get("type") or chart.get("chart_type") or "未知"
            chart_types[ct] = chart_types.get(ct, 0) + 1
    if chart_types:
        parts = [f"{n}个{c}" for c, n in chart_types.items()]
        lines.append(f"图表：{', '.join(parts)}")

    # KPI 摘要
    total_kpis = 0
    for pkg in packages:
        kpis = pkg.get("kpis") or pkg.get("rendered_kpis") or []
        total_kpis += len(kpis)
    if total_kpis:
        lines.append(f"KPI 指标：{total_kpis} 个")

    lines.append(f"分析包数：{len(packages)} 个")
    lines.append("请基于以上信息，为该数据驾驶舱生成一个不超过 24 字的中文标题，直接输出标题文本，不要加引号或解释。")

    return "\n".join(lines)


@router.post("/dashboard/schema/naming")
async def api_dashboard_naming(req: DashboardNamingRequest):
    """AI 智能命名：根据 saved_packages 生成仪表盘标题"""
    packages = manager.get_saved_packages_full(req.session_id)
    df = manager.get_data(req.session_id)
    df_columns = list(df.columns) if df is not None else []

    # 无 API Key → 关键词兜底
    if not req.api_key:
        title = _infer_title_by_keywords(df_columns)
        return sanitize_json({"success": True, "title": title, "source": "fallback"})

    summary = _build_naming_summary(packages, df_columns)

    try:
        import openai
        client = openai.OpenAI(
            api_key=req.api_key,
            base_url=req.base_url,
            timeout=30.0,
        )
        model = (req.model or "gpt-3.5-turbo").lower()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "你是一位数据分析专家，擅长为数据驾驶舱提炼精准简洁的中文标题。标题需体现代分析主题和数据特点，不超过 24 个字。只输出标题文本，不要加引号或多余解释。",
                },
                {"role": "user", "content": summary},
            ],
            temperature=0.5,
            max_tokens=64,
            timeout=25,
        )
        ai_title = response.choices[0].message.content.strip()
        # 清理引号、换行和过长内容
        ai_title = ai_title.strip('\"\'\n\r 。，,.')
        if len(ai_title) > 30:
            ai_title = ai_title[:30]
        if not ai_title or len(ai_title) < 2:
            ai_title = _infer_title_by_keywords(df_columns)
            return sanitize_json({"success": True, "title": ai_title, "source": "fallback"})
        return sanitize_json({"success": True, "title": ai_title, "source": "ai"})
    except Exception as e:
        logger.warning(f"AI 标题命名失败: {e}")
        title = _infer_title_by_keywords(df_columns)
        return sanitize_json({"success": True, "title": title, "source": "fallback"})


@router.post("/dashboard/schema/title")
async def api_dashboard_title(req: DashboardTitleRequest):
    """仪表盘标题持久化：get 读取 / set 写入"""
    if req.action == "set":
        manager.set_custom_title(req.session_id, req.title or "")
        return sanitize_json({"success": True, "title": req.title, "has_custom": True})
    else:
        # action == "get"
        custom = manager.get_custom_title(req.session_id)
        return sanitize_json({"success": True, "title": custom, "has_custom": bool(custom)})










# ===== V5: Card Generator API =====
class CardsGenerateRequest(BaseModel):
    session_id: str



@router.post('/dashboard/cards')
async def api_generate_cards(req: CardsGenerateRequest):
    """V5: Card Generator - 将 AnalysisPackage 转换为 CardPackage"""
    import traceback
    from backend.services.session_manager import manager
    from src.card_generator import CardGenerator

    try:
        packages = manager.get_saved_packages_full(req.session_id) or []

        # B 修复：把 V1 手工收藏图表（saved_charts）并入 medical 大屏卡片生成。
        # 仅在本路由内合并，不改动 get_saved_packages_full / CardGenerator / 前端。
        v1_charts = manager.get_saved_charts(req.session_id) or []
        if v1_charts:
            manual_pkg: Dict[str, Any] = {"analysis_type": "manual_chart", "charts": [], "tables": []}
            for c in v1_charts:
                ctype = c.get('type', '') or ''
                if ctype == 'table':
                    # 表格型手工图：转换为 table 卡片格式
                    td = c.get('table_data') or {}
                    tb_rows = td.get('rows') or []
                    if tb_rows:
                        cols = list(tb_rows[0].keys())
                        manual_pkg["tables"].append({
                            "title": c.get('title', '同环比表'),
                            "table_type": "detail",
                            "columns": cols,
                            "rows": [list(r.values()) for r in tb_rows],
                        })
                else:
                    # 普通图表：V1 用 type 字段，归一化为 chart_type；option 直接作为卡片数据
                    manual_pkg["charts"].append({
                        "title": c.get("title", ""),
                        "chart_type": ctype,
                        "option": c.get("option") or {},
                    })
            if manual_pkg["charts"] or manual_pkg["tables"]:
                packages.append(manual_pkg)

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
    except Exception as e:
        traceback.print_exc()
        return {'success': False, 'cards': [], 'error': str(e)}

