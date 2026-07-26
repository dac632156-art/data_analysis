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


@dataclass
class RenderedTable:
    title: str
    table_type: str
    columns: List[str] = field(default_factory=list)
    rows: List[List[RenderedCell]] = field(default_factory=list)
    sortable: bool = True
    highlight_col: Optional[int] = None


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
            td = TableData(**{kk: t[kk] for kk in ("title", "table_type", "columns", "rows") if kk in t})
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
        return _render_growth(td)
    if tt == "ranking":
        return _render_ranking(td)
    if tt == "correlation":
        return _render_correlation(td)
    if tt == "exception":
        return _render_exception(td)
    return _render_generic(td)


def _render_generic(td):
    rows = [[RenderedCell(value=v) for v in row] for row in (td.rows or [])]
    return RenderedTable(title=td.title, table_type=td.table_type, columns=td.columns, rows=rows)


def _render_growth(td):
    rows = []
    for row in (td.rows or []):
        cells = []
        for i, val in enumerate(row):
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
        cells = [RenderedCell(value=v, highlight=(idx == 0)) for v in row]
        rows.append(cells)
    return RenderedTable(title=td.title, table_type=td.table_type, columns=td.columns, rows=rows)


def _render_correlation(td):
    rows = []
    for row in (td.rows or []):
        cells = []
        for j, val in enumerate(row):
            highlight = False
            if j > 0 and isinstance(val, (int, float)):
                highlight = abs(val) > 0.7
            cells.append(RenderedCell(value=val, highlight=highlight))
        rows.append(cells)
    return RenderedTable(title=td.title, table_type=td.table_type, columns=td.columns, rows=rows, sortable=False)


def _render_exception(td):
    rows = [[RenderedCell(value=v, highlight=True) for v in row] for row in (td.rows or [])]
    return RenderedTable(title=td.title, table_type=td.table_type, columns=td.columns, rows=rows)
