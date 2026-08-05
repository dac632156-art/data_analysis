"""report_audit.py — LLM 报告「事实溯源」审计器

#2 目标：检测 LLM 生成的报告（executive_summary / management_suggestions /
各 insight.analysis）中的数值是否能在源 AnalysisPackage（findings / kpis /
tables / insights / conclusions）中溯源，标记**疑似幻觉**的数字。

方法（启发式，非语义级）：
1. 从源 ``sections_data``（ReportBuilder.build_input 的产物）构建「地面真值数字集合」
   ``ground_numbers``（把 万/亿 量纲归一化后的浮点值）。
2. 从报告 prose 抽取数值声明 ``claims``（含 万/亿/% 量纲）。
3. 每个 claim 与 ``ground_numbers`` 比对（相对容差 5% + 绝对容差 1.0）：
   - 精确/容差内命中 → TRACED
   - 接近但未精确命中 → APPROX（建议人工复核量级表述）
   - 无近似命中     → UNTRACEABLE（疑似幻觉，必须人工复核）
4. 附加检查：报告 ``insight.chart_title`` 引用的图表标题是否都存在于源 ``chart_data``
   （标题做归一化比对：NFKC 全角→半角、去空白、转小写，并兼容 LLM 省略括号注/微小改写）。

注意：这是**数值级**审计，不能捕捉「数字对但归因错」的语义幻觉；它主要拦截
「凭空编造的数字」。UNTRACEABLE 列表应作为人工复核清单，而非自动定罪。

纯标准库实现，无第三方依赖。
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 数值抽取
# ---------------------------------------------------------------------------

# 匹配：整数(支持千分位) / 小数，可选 万|亿 量纲，可选 %
_TOKEN_RE = re.compile(
    r"(?P<num>\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)"  # 数字
    r"(?P<scale>\s*[万亿])?"  # 量纲
    r"(?P<pct>\s*%)?"  # 百分号
)

_SCALE_MULT = {"万": 1e4, "亿": 1e8}

# 结构性数字（非业务量）的白名单前缀/上下文，用于降低误报
_STRUCTURAL_HINTS = (
    "年", "经验", "段", "条", "个建议", "建议", "步", "篇", "章", "节",
    "第", "序号", "编号", "页", "版本", "v", "号",
)


@dataclass
class NumberClaim:
    """从报告 prose 中抽取的一个数值声明。"""

    raw: str
    value: float
    has_percent: bool
    has_scale: bool
    context: str  # 前后若干字符，便于人工复核
    source_section: str = ""


@dataclass
class TraceResult:
    claim: NumberClaim
    status: str  # TRACED | APPROX | UNTRACEABLE
    nearest_ground: Optional[float] = None
    nearest_diff: Optional[float] = None


@dataclass
class AuditReport:
    claim_results: List[TraceResult] = field(default_factory=list)
    missing_chart_titles: List[str] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)

    @property
    def untraceable(self) -> List[TraceResult]:
        return [r for r in self.claim_results if r.status == "UNTRACEABLE"]

    @property
    def approx(self) -> List[TraceResult]:
        return [r for r in self.claim_results if r.status == "APPROX"]


def _normalize_number(num_str: str, scale: Optional[str], pct: Optional[str]) -> float:
    """把抽取到的数字归一化为可比对的浮点值（展开 万/亿 量纲）。"""
    val = float(num_str.replace(",", ""))
    if scale:
        val *= _SCALE_MULT.get(scale.strip(), 1.0)
    # 百分号不改变量级（70.9% 与 70.9 视为同一数值用于比对）
    return val


def extract_numbers(text: str) -> List[Tuple[float, str, bool, bool]]:
    """从一段文本抽取 (value, raw, has_percent, has_scale)。"""
    out: List[Tuple[float, str, bool, bool]] = []
    if not text:
        return out
    for m in _TOKEN_RE.finditer(text):
        num = m.group("num")
        scale = m.group("scale")
        pct = m.group("pct")
        value = _normalize_number(num, scale, pct)
        raw = m.group(0).strip()
        out.append((value, raw, bool(pct), bool(scale)))
    return out


def _is_structural(claim: NumberClaim) -> bool:
    """粗略判断是否为结构性数字（年/经验/段/条等非业务量），降低误报。"""
    ctx = claim.context
    for hint in _STRUCTURAL_HINTS:
        if hint in ctx:
            return True
    # 纯序数/编号：数字紧邻「第」「#」等
    if re.search(r"第\s*\d|#\s*\d|\bNo\.?\s*\d", ctx):
        return True
    return False


# ---------------------------------------------------------------------------
# 源真值集合构建
# ---------------------------------------------------------------------------

def build_ground_numbers(sections_data: Dict[str, List[Dict[str, Any]]]) -> List[float]:
    """从 ReportBuilder 的 sections_data 汇总所有地面真值数字。"""
    ground: List[float] = []
    if not sections_data:
        return ground

    text_sources: List[Any] = []

    for _section_name, pkgs in sections_data.items():
        for pkg in pkgs:
            # kpis
            for k in pkg.get("kpis", []) or []:
                if isinstance(k, dict):
                    text_sources.extend([k.get("label", ""), k.get("value", ""), k.get("change", "")])
            # tables（含行内所有单元格）
            for t in pkg.get("tables", []) or []:
                if isinstance(t, dict):
                    text_sources.append(t.get("title", ""))
                    for row in t.get("rows", []) or []:
                        if isinstance(row, (list, tuple)):
                            text_sources.extend([str(c) for c in row])
                        else:
                            text_sources.append(str(row))
            # findings（业务级结论，最关键）
            for f in pkg.get("findings", []) or []:
                if isinstance(f, dict):
                    text_sources.extend([
                        f.get("title", ""), f.get("description", ""),
                        f.get("metric", ""), f.get("entity", ""),
                        f.get("business_meaning", ""), f.get("business_impact", ""),
                        f.get("recommendation", ""),
                    ])
                    ev = f.get("evidence", {}) or {}
                    for ev_val in ev.values():
                        text_sources.append(str(ev_val))
            # insights / conclusions / recommendations
            text_sources.extend(pkg.get("insights", []) or [])
            text_sources.extend(pkg.get("conclusions", []) or [])
            text_sources.extend(pkg.get("recommendations", []) or [])

    for src in text_sources:
        s = str(src)
        if not s:
            continue
        for value, _raw, _pct, _scale in extract_numbers(s):
            ground.append(value)

    return ground


def build_source_chart_titles(sections_data: Dict[str, List[Dict[str, Any]]]) -> set:
    titles = set()
    for _section_name, pkgs in sections_data.items():
        for pkg in pkgs:
            for c in pkg.get("chart_data", []) or []:
                if isinstance(c, dict) and c.get("title"):
                    titles.add(str(c.get("title")))
    return titles


def _norm_title(s: str) -> str:
    """归一化图表标题用于比对：NFKC 全角→半角、去所有空白、转小写。"""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    s = re.sub(r"\s+", "", s)
    return s.lower()


def _title_present(ct: str, source_norm: set) -> bool:
    """判断报告引用的图表标题是否能在源标题中找到。

    兼容三类 LLM 改写：
    1. 规范化精确命中（去全半角差异 + 去空白，解决「RFM 8大群体占比」vs「RFM 8 大群体占比」）；
    2. 包含关系（一方包含另一方，解决省略「（等宽分箱）」之类括号注）；
    3. 模糊匹配（difflib 相似度 ≥ 0.85，解决「八」vs「8」等微小改写）。
    """
    n = _norm_title(ct)
    if not n:
        return True  # 空标题不判缺失
    if n in source_norm:
        return True
    for st in source_norm:
        if n in st or st in n:
            return True
    for st in source_norm:
        if st and difflib.SequenceMatcher(None, n, st).ratio() >= 0.85:
            return True
    return False


# ---------------------------------------------------------------------------
# 报告数值抽取 + 比对
# ---------------------------------------------------------------------------

def _report_text_blocks(report_sections: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """返回 [(section_type, text), ...]，覆盖 prose 与 insight.analysis。"""
    blocks: List[Tuple[str, str]] = []
    for sec in report_sections or []:
        if not isinstance(sec, dict):
            continue
        stype = str(sec.get("type", ""))
        content = sec.get("content")
        if content:
            blocks.append((stype, str(content)))
        for ins in sec.get("insights", []) or []:
            if isinstance(ins, dict):
                analysis = ins.get("analysis")
                if analysis:
                    blocks.append((stype, str(analysis)))
    return blocks


def _match_ground(value: float, ground: List[float], tol_rel: float = 0.05, tol_abs: float = 1.0):
    """返回 (nearest_value, diff) 或 (None, None)。"""
    best_val = None
    best_diff = None
    for g in ground:
        d = abs(value - g)
        if best_diff is None or d < best_diff:
            best_diff = d
            best_val = g
    if best_val is None:
        return None, None
    # 容忍度随量级放大：取相对与绝对较大者
    threshold = max(tol_abs, tol_rel * max(abs(value), abs(best_val)))
    if best_diff <= threshold:
        return best_val, best_diff
    return best_val, best_diff


def audit_report(
    report_sections: List[Dict[str, Any]],
    sections_data: Dict[str, List[Dict[str, Any]]],
    tol_rel: float = 0.05,
    tol_abs: float = 1.0,
) -> AuditReport:
    """对一份 LLM 报告做事实溯源审计。"""
    ground = build_ground_numbers(sections_data)
    source_titles = build_source_chart_titles(sections_data)

    results: List[TraceResult] = []
    for stype, text in _report_text_blocks(report_sections):
        # 上下文窗口：每个数字前后 12 字符
        for m in _TOKEN_RE.finditer(text):
            start = max(0, m.start() - 12)
            end = min(len(text), m.end() + 12)
            ctx = text[start:end]
            value = _normalize_number(
                m.group("num"), m.group("scale"), m.group("pct")
            )
            claim = NumberClaim(
                raw=m.group(0).strip(),
                value=value,
                has_percent=bool(m.group("pct")),
                has_scale=bool(m.group("scale")),
                context=ctx,
                source_section=stype,
            )
            if _is_structural(claim):
                continue
            nearest, diff = _match_ground(value, ground, tol_rel, tol_abs)
            if diff is None:
                status = "UNTRACEABLE"
            else:
                # 百分比（百分点）量纲紧凑，误匹配风险高，使用更严格的绝对容差；
                # 非百分比按量级缩放容差。三层带：TRACED / APPROX(复核) / UNTRACEABLE(疑似幻觉)
                if claim.has_percent:
                    t_traced = 1.0    # 1 个百分点
                    t_approx = 3.0    # 3 个百分点
                else:
                    scale = max(abs(value), abs(nearest)) if nearest is not None else abs(value)
                    t_traced = max(tol_abs, tol_rel * scale)
                    t_approx = max(2.0 * tol_abs, 2.0 * tol_rel * scale)
                if diff <= t_traced:
                    status = "TRACED"
                elif diff <= t_approx:
                    status = "APPROX"
                else:
                    status = "UNTRACEABLE"
            results.append(TraceResult(claim, status, nearest, diff))

    # 图表标题溯源（归一化比对，兼容 LLM 改写/省略空格与括号注，避免误报缺失）
    source_norm = {_norm_title(t) for t in source_titles}
    missing: List[str] = []
    for sec in report_sections or []:
        if not isinstance(sec, dict):
            continue
        for ins in sec.get("insights", []) or []:
            if isinstance(ins, dict):
                ct = ins.get("chart_title")
                if ct and str(ct).lower() not in ("null", "none", ""):
                    if not _title_present(str(ct), source_norm):
                        missing.append(str(ct))

    traced = sum(1 for r in results if r.status == "TRACED")
    approx = sum(1 for r in results if r.status == "APPROX")
    untraceable = sum(1 for r in results if r.status == "UNTRACEABLE")

    audit = AuditReport(
        claim_results=results,
        missing_chart_titles=missing,
        stats={
            "total_claims": len(results),
            "traced": traced,
            "approx": approx,
            "untraceable": untraceable,
            "missing_chart_titles": len(missing),
            "ground_numbers": len(ground),
            "source_chart_titles": len(source_titles),
        },
    )
    return audit


def format_audit(audit: AuditReport) -> str:
    """把审计结果格式化为可读文本（用于 CLI / 报告）。"""
    s = audit.stats
    lines = []
    lines.append("=" * 60)
    lines.append("LLM 报告事实溯源审计")
    lines.append("=" * 60)
    lines.append(
        f"数值声明总数={s['total_claims']}  可溯源(TRACED)={s['traced']}  "
        f"近似(APPROX)={s['approx']}  疑似幻觉(UNTRACEABLE)={s['untraceable']}"
    )
    lines.append(
        f"地面真值数字={s['ground_numbers']}  源图表标题={s['source_chart_titles']}  "
        f"报告引用缺失图表={s['missing_chart_titles']}"
    )
    lines.append("")

    if audit.untraceable:
        lines.append("⚠ 疑似幻觉（UNTRACEABLE）—— 必须人工复核：")
        for r in audit.untraceable:
            near = f" (最近真值≈{r.nearest_ground:g}, 差={r.nearest_diff:g})" if r.nearest_ground is not None else ""
            lines.append(
                f"  - [{r.claim.source_section}] 「{r.claim.raw}」"
                f" @ …{r.claim.context.strip()}…{near}"
            )
        lines.append("")

    if audit.approx:
        lines.append("≈ 近似(APPROX)—— 建议复核量级表述：")
        for r in audit.approx:
            lines.append(
                f"  - [{r.claim.source_section}] 「{r.claim.raw}」"
                f" 最近真值≈{r.nearest_ground:g}"
            )
        lines.append("")

    if audit.missing_chart_titles:
        lines.append("⚠ 报告引用了源中不存在的图表标题：")
        for t in audit.missing_chart_titles:
            lines.append(f"  - {t}")
        lines.append("")

    if not audit.untraceable and not audit.missing_chart_titles:
        lines.append("✓ 未发现数值级幻觉迹象；所有抽样数字均可在源 AnalysisPackage 溯源。")
    lines.append("=" * 60)
    return "\n".join(lines)
