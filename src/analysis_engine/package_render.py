"""package_render —— 将 AnalysisPackage 原始字段渲染为前端可消费的 rendered_* 结构。

替代已删除的 kpi_renderer / table_renderer / insight_renderer / conclusion_renderer，
逻辑与原四文件保持一致，仅合并到单一模块，避免功能丢失、也避免散落四个文件。
"""
from dataclasses import dataclass, field, asdict
from typing import Any, List, Optional

from src.analysis_templates.base import KPIItem, TableData
from src.echart_generator import GALAXY


@dataclass
class RenderedKPI:
    label: str
    value: str
    change: str
    trend: str
    kpi_type: str


@dataclass
class RenderedCell:
    value: Any
    highlight: bool = False
    color: Optional[str] = None
    rank: float = 0.0              # 该群在全部群中的相对排名(0~1)，用于进度条宽度
    direction: str = "neutral"     # good(绿)/equal(黄)/bad(红)/neutral(不染色)
    cell_type: str = "text"        # number/percentage/category/neutral


@dataclass
class RenderedTable:
    slot: str = ""  # 与图表一致的定位标识，如 "rfm_segment_summary_table"（排第一，保证 JSON 中 slot 在 title 之前）
    title: str = ""
    table_type: str = ""
    columns: List[str] = field(default_factory=list)
    rows: List[List[RenderedCell]] = field(default_factory=list)
    sortable: bool = True
    highlight_col: Optional[int] = None
    chart_config: dict = field(default_factory=dict)  # 高级表格元数据（区块/颜色编码）


@dataclass
class RenderedInsight:
    text: str
    priority: str = "normal"   # "high" | "normal" | "low"
    label: str = ""             # "趋势洞察" | "结构洞察" | "异常洞察"


@dataclass
class RenderedConclusion:
    summary: str
    details: List[str]
    confidence: str = "medium"  # "high" | "medium" | "low"


# ===== KPI =====
def render_kpis(kpis_raw) -> List[dict]:
    out = []
    for k in (kpis_raw or []):
        if isinstance(k, KPIItem):
            item = k
        elif isinstance(k, dict) and "label" in k:
            item = KPIItem(**{kk: k[kk] for kk in ("label", "value", "change", "kpi_type") if kk in k})
        else:
            continue
        trend = _infer_trend(item.change) if item.change else ""
        out.append(asdict(RenderedKPI(
            label=item.label,
            value=item.value,
            change=item.change or "",
            trend=trend,
            kpi_type=item.kpi_type,
        )))
    return out


# ===== Table =====
def render_tables(tables_raw) -> List[dict]:
    out = []
    for t in (tables_raw or []):
        if isinstance(t, TableData):
            td = t
        elif isinstance(t, dict) and "title" in t:
            td = TableData(**{kk: t[kk] for kk in ("title", "table_type", "columns", "rows", "chart_config", "slot") if kk in t})
        else:
            continue
        out.append(asdict(_render_table(td)))
    return out


# ===== Insight =====
def render_insights(insights_raw) -> List[dict]:
    if not isinstance(insights_raw, list):
        return []
    rendered = [_render_insight(text, i) for i, text in enumerate(insights_raw)]
    seen = set()
    unique = []
    for r in rendered:
        if r.text not in seen:
            seen.add(r.text)
            unique.append(r)
    order = {"high": 0, "normal": 1, "low": 2}
    unique.sort(key=lambda x: order.get(x.priority, 1))
    return [asdict(r) for r in unique]


# ===== Conclusion =====
def render_conclusion(conclusions_raw) -> dict:
    conclusions = conclusions_raw if isinstance(conclusions_raw, list) else []
    if not conclusions:
        return asdict(RenderedConclusion(summary="暂无分析结论", details=[], confidence="low"))
    summary = conclusions[0]
    details = conclusions[1:] if len(conclusions) > 1 else []
    confidence = "high" if len(conclusions) >= 3 else "medium"
    return asdict(RenderedConclusion(summary=summary, details=details, confidence=confidence))


# ===== 便捷：对一个已 asdict 的分析包补全 rendered_* 字段 =====
def render_package(pkg: dict) -> dict:
    full = dict(pkg)
    full["rendered_kpis"] = render_kpis(pkg.get("kpis", []))
    full["rendered_tables"] = render_tables(pkg.get("tables", []))
    full["rendered_charts"] = pkg.get("charts", [])
    full["rendered_insights"] = render_insights(pkg.get("insights", []))
    full["rendered_conclusion"] = render_conclusion(pkg.get("conclusions", []))
    # 迁移：保证 tables 里每个 dict 都有 slot 键
    # 旧包 asdict 时 slot 字段尚不存在 → 补 ""；新包已有真值不动
    tables_raw = full.get("tables")
    if isinstance(tables_raw, list):
        for t in tables_raw:
            if isinstance(t, dict) and "slot" not in t:
                t["slot"] = ""
    return full


# ===== 内部辅助 =====
def _infer_trend(change_str):
    if not change_str:
        return ""
    cleaned = str(change_str).strip().replace("%", "").replace("+", "")
    try:
        val = float(cleaned)
        if val > 0:
            return "up"
        if val < 0:
            return "down"
        return "flat"
    except ValueError:
        return ""


_PRIORITY_KEYWORDS = {
    "异常": ("high", "异常洞察"),
    "风险": ("high", "风险洞察"),
    "最高": ("high", "集中度洞察"),
    "最低": ("high", "集中度洞察"),
    "趋势": ("normal", "趋势洞察"),
    "占比": ("normal", "结构洞察"),
    "增长": ("normal", "趋势洞察"),
    "下降": ("normal", "趋势洞察"),
}


def _classify(text):
    for kw, (p, l) in _PRIORITY_KEYWORDS.items():
        if kw in text:
            return p, l
    return "normal", ""


def _render_insight(text, index):
    priority, label = _classify(text)
    if index == 0 and priority == "normal":
        priority = "high"
    return RenderedInsight(text=text, priority=priority, label=label)


def _render_table(td):
    tt = td.table_type
    if tt == "growth":
        rt = _render_growth(td)
    elif tt == "ranking":
        rt = _render_ranking(td)
    elif tt == "correlation":
        rt = _render_correlation(td)
    elif tt == "exception":
        rt = _render_exception(td)
    elif tt == "profile_overview":
        rt = _render_profile_overview(td)
    else:
        rt = _render_generic(td)
    rt.slot = td.slot
    return rt


def _row_to_values(row, columns):
    """dict 行 → 按 columns 顺序提取值；list/其他行 → 原样返回（兼容两种格式）。

    K-means/RFM 等模型的 _build_tables 产出 List[Dict]，若直接 `for v in row`
    会遍历 dict 的 key（列名）而非 value，导致仪表盘把列名当数据渲染。
    """
    if isinstance(row, dict):
        return [row.get(col) for col in columns]
    return row


def _render_generic(td):
    """通用表（summary 等）：rows 为 List[Dict]，cell 可为字符串或结构化 dict。

    结构化 cell（如 RFM 消费力(M) 的 {value, type, direction, rank}）在看板通用表中
    不显示颜色条，故仅透传其数值，保证 rendered_tables 的 JSON 也带该列且能正常显示
    （否则嵌套 dict 会被前端当成 [object Object]）。"""
    rows = []
    for row in (td.rows or []):
        cells = []
        for v in _row_to_values(row, td.columns):
            if isinstance(v, dict) and "value" in v:
                cells.append(RenderedCell(value=v.get("value")))
            else:
                cells.append(RenderedCell(value=v))
        rows.append(cells)
    return RenderedTable(title=td.title, table_type=td.table_type, columns=td.columns, rows=rows)


def _render_profile_overview(td):
    """群画像总览表：rows 为 List[Dict]，每个 cell = {value, type, direction?, rank?}。
    直接把后端算好的颜色元数据透传给前端 TableWidget。"""
    rows = []
    for row in (td.rows or []):
        if not isinstance(row, dict):
            # 兼容普通行：退化为纯文本
            rows.append([RenderedCell(value=v) for v in _row_to_values(row, td.columns)])
            continue
        cells = []
        for col in td.columns:
            meta = row.get(col, {}) or {}
            if not isinstance(meta, dict):
                cells.append(RenderedCell(value=meta))
                continue
            cells.append(RenderedCell(
                value=meta.get("value"),
                rank=float(meta.get("rank", 0.0) or 0.0),
                direction=str(meta.get("direction", "neutral")),
                cell_type=str(meta.get("type", "text")),
            ))
        rows.append(cells)
    return RenderedTable(
        title=td.title,
        table_type=td.table_type,
        columns=td.columns,
        rows=rows,
        sortable=False,
        chart_config=td.chart_config or {},
    )


def _render_growth(td):
    rows = []
    for row in (td.rows or []):
        cells = []
        for i, val in enumerate(_row_to_values(row, td.columns)):
            cell = RenderedCell(value=val)
            if i >= 2 and isinstance(val, (int, float)):
                if val > 0:
                    cell.color = GALAXY["success"]
                elif val < 0:
                    cell.color = GALAXY["danger"]
            cells.append(cell)
        rows.append(cells)
    return RenderedTable(title=td.title, table_type=td.table_type, columns=td.columns, rows=rows, highlight_col=2)


def _render_ranking(td):
    rows = []
    for idx, row in enumerate(td.rows or []):
        cells = [RenderedCell(value=v, highlight=(idx == 0)) for v in _row_to_values(row, td.columns)]
        rows.append(cells)
    return RenderedTable(title=td.title, table_type=td.table_type, columns=td.columns, rows=rows)


def _render_correlation(td):
    rows = []
    for row in (td.rows or []):
        cells = []
        for j, val in enumerate(_row_to_values(row, td.columns)):
            highlight = False
            if j > 0 and isinstance(val, (int, float)):
                highlight = abs(val) > 0.7
            cells.append(RenderedCell(value=val, highlight=highlight))
        rows.append(cells)
    return RenderedTable(title=td.title, table_type=td.table_type, columns=td.columns, rows=rows, sortable=False)


def _render_exception(td):
    rows = [[RenderedCell(value=v, highlight=True) for v in _row_to_values(row, td.columns)] for row in (td.rows or [])]
    return RenderedTable(title=td.title, table_type=td.table_type, columns=td.columns, rows=rows)
