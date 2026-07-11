"""
仪表盘 API 路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import asyncio
import logging
import json
import re
from concurrent.futures import ThreadPoolExecutor

from backend.services.session_manager import manager
from src.dashboard_builder import calculate_kpis
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
    for pkg in packages:
        if not isinstance(pkg, dict):
            continue
        analysis_type = pkg.get("analysis_type", "")
        pkg_charts = pkg.get("charts", []) or []
        for chart in pkg_charts:
            if not isinstance(chart, dict):
                continue
            ct = chart.get("chart_type", "bar")
            x = chart.get("x", "")
            y = chart.get("y", "")
            title = chart.get("title", f"{analysis_type} 图表")
            # 原样携带已渲染 option（空则留空，由 api_dashboard_echarts 回退 create_echart）
            option = chart.get("option", "") or ""
            cfg = {
                "chart_type": ct,
                "x": x,
                "y": y,
                "title": title,
                "analysis_type": analysis_type,
                "option": option,
                "table_data": chart.get("table_data") or None,
            }
            # 去重：同类型同 X 同 Y 的只保留一个
            key = (ct, x, y)
            if not any((c.get("chart_type"), c.get("x"), c.get("y")) == key for c in configs):
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
    """获取仪表盘图表（ECharts 格式）

    优先级：
    1. 请求中传入的 charts → 直接使用
    2. 已保存的分析包中的 chart_data → 从分析结果提取
    3. 默认图表配置 → 兜底（首次使用、无分析结果时）
    """
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")

    from src.dashboard_builder import get_default_echart_configs
    if req.charts and len(req.charts) > 0:
        configs = req.charts
    else:
        # ★ 优先使用已保存的分析结果中的图表数据
        packages = manager.get_saved_packages_full(req.session_id) or []
        configs = _extract_chart_configs_from_packages(packages)
        # 没有分析结果时，才使用默认图表（但只生成核心的几种，而非 12 种）
        if not configs:
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
            # ★ 优先复用已保存分析包中渲染好的 option（帕累托线/数值降序已固化），
            #   不再拿原始 df 重新聚合（否则丢图、排序错）。仅 option 缺失时回退重算。
            existing_option = cfg.get("option")
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
                })
                continue

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
    except Exception as e:
        traceback.print_exc()
        return {'success': False, 'cards': [], 'error': str(e)}

