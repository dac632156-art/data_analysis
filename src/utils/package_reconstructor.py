"""
Package Reconstructor —— dict → AnalysisPackage 重构工具

session_manager 存储的 AnalysisPackage 经过 dataclasses.asdict() 序列化后
丢失了类型信息。本模块将其还原为完整的 dataclass 对象，供 ReasoningPipeline
和 ReportPipeline 消费。

使用：
    from src.utils.package_reconstructor import reconstruct_packages
    packages = reconstruct_packages(dicts)
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from src.analysis_templates.base import AnalysisPackage, KPIItem, ChartData, TableData, ChartItem
from src.domain.business_finding import (
    BusinessFinding as DomainBusinessFinding,
    EvidenceRef,
    FindingCategory,
    Direction,
    Severity,
)


# ============================================================
# 枚举解析
# ============================================================

def _parse_enum(raw: Any, enum_cls, default):
    """安全解析枚举值，兼容 str 和 _value_ dict 两种格式"""
    if isinstance(raw, enum_cls):
        return raw
    if isinstance(raw, dict):
        # dataclasses.asdict(Enum) → {'_value_': 'growth'}
        raw = raw.get("_value_", raw.get("value", ""))
    if isinstance(raw, str) and raw:
        try:
            return enum_cls(raw)
        except ValueError:
            pass
    return default


# ============================================================
# EvidenceRef 重构
# ============================================================

def _reconstruct_evidence(ev_dict: Optional[Dict[str, Any]]) -> EvidenceRef:
    """dict → EvidenceRef"""
    if not ev_dict or not isinstance(ev_dict, dict):
        return EvidenceRef()
    chart_slots = tuple(ev_dict.get("chart_slots", []) or [])
    table_titles = tuple(ev_dict.get("table_titles", []) or [])
    kpi_labels = tuple(ev_dict.get("kpi_labels", []) or [])
    return EvidenceRef(
        chart_slots=chart_slots,
        table_titles=table_titles,
        kpi_labels=kpi_labels,
    )


# ============================================================
# BusinessFinding 重构
# ============================================================

def _reconstruct_finding(f_dict: Dict[str, Any]) -> DomainBusinessFinding:
    """dict → DomainBusinessFinding

    兼容两种输入：
    - BusinessFinding 对象（直接返回）
    - dataclasses.asdict() 序列化后的 dict
    """
    if isinstance(f_dict, DomainBusinessFinding):
        return f_dict

    try:
        category = _parse_enum(f_dict.get("category"), FindingCategory, FindingCategory.UNKNOWN)
        direction = _parse_enum(f_dict.get("direction"), Direction, Direction.UNKNOWN)
        severity = _parse_enum(f_dict.get("severity"), Severity, Severity.INFO)

        evidence = _reconstruct_evidence(f_dict.get("evidence"))

        tags_raw = f_dict.get("tags", [])
        if isinstance(tags_raw, list):
            tags = tuple(tags_raw)
        else:
            tags = ()

        return DomainBusinessFinding(
            id=str(f_dict.get("id", "")),
            analysis_type=str(f_dict.get("analysis_type", "")),
            category=category,
            title=str(f_dict.get("title", "")),
            description=str(f_dict.get("description", "")),
            metric=str(f_dict.get("metric", "")),
            dimension=str(f_dict.get("dimension", "")),
            entity=str(f_dict.get("entity", "")),
            value=_safe_float(f_dict.get("value")),
            unit=str(f_dict.get("unit", "")),
            direction=direction,
            change_pct=_safe_float(f_dict.get("change_pct")),
            severity=severity,
            confidence=_safe_float(f_dict.get("confidence"), 1.0),
            business_meaning=str(f_dict.get("business_meaning", "")),
            business_impact=str(f_dict.get("business_impact", "")),
            recommendation=str(f_dict.get("recommendation", "")),
            evidence=evidence,
            tags=tags,
            metadata=f_dict.get("metadata", {}) if isinstance(f_dict.get("metadata"), dict) else {},
        )
    except Exception:
        # 损坏的 finding 跳过（返回空壳，让上游过滤）
        return DomainBusinessFinding(
            id=f_dict.get("id", ""),
            analysis_type="",
            category=FindingCategory.UNKNOWN,
            title=f_dict.get("title", "（数据损坏）"),
            confidence=0.0,
        )


# ============================================================
# AnalysisPackage 重构
# ============================================================

def _reconstruct_kpi(k_dict: Dict[str, Any]) -> KPIItem:
    """dict → KPIItem"""
    if isinstance(k_dict, KPIItem):
        return k_dict
    return KPIItem(
        label=str(k_dict.get("label", "")),
        value=str(k_dict.get("value", "")),
        change=str(k_dict.get("change", "")),
        kpi_type=str(k_dict.get("kpi_type", "")),
    )


def _reconstruct_chart_data(c_dict: Dict[str, Any]) -> ChartData:
    """dict → ChartData"""
    if isinstance(c_dict, ChartData):
        return c_dict
    return ChartData(
        slot=str(c_dict.get("slot", "")),
        chart_type=str(c_dict.get("chart_type", "")),
        title=str(c_dict.get("title", "")),
        x=str(c_dict.get("x", "")),
        y=str(c_dict.get("y", "")),
        data=list(c_dict.get("data", []) if isinstance(c_dict.get("data"), list) else []),
    )


def _reconstruct_table(t_dict: Dict[str, Any]) -> TableData:
    """dict → TableData"""
    if isinstance(t_dict, TableData):
        return t_dict
    return TableData(
        title=str(t_dict.get("title", "")),
        table_type=str(t_dict.get("table_type", "")),
        columns=list(t_dict.get("columns", []) if isinstance(t_dict.get("columns"), list) else []),
        rows=list(t_dict.get("rows", []) if isinstance(t_dict.get("rows"), list) else []),
    )


def reconstruct_packages(package_dicts: List[Dict[str, Any]]) -> List[AnalysisPackage]:
    """将 dict 列表重构为 AnalysisPackage 对象列表

    Args:
        package_dicts: List[Dict] — session_manager 保存的分析包

    Returns:
        List[AnalysisPackage] — 完整的 dataclass 对象，可直接传给 ReasoningPipeline
    """
    if not package_dicts:
        return []

    packages = []
    for p_dict in package_dicts:
        try:
            # 已经是 AnalysisPackage 对象直接保留
            if isinstance(p_dict, AnalysisPackage):
                packages.append(p_dict)
                continue

            # 重构 findings
            raw_findings = p_dict.get("findings", [])
            findings = [
                _reconstruct_finding(f) for f in raw_findings
                if isinstance(f, (dict, DomainBusinessFinding))
            ]

            # 重构 KPIs / Charts / Tables
            kpis = [_reconstruct_kpi(k) for k in (p_dict.get("kpis", []) or [])]
            chart_data = [_reconstruct_chart_data(c) for c in (p_dict.get("chart_data", []) or [])]
            tables = [_reconstruct_table(t) for t in (p_dict.get("tables", []) or [])]

            package = AnalysisPackage(
                id=str(p_dict.get("id", "")),
                analysis_type=str(p_dict.get("analysis_type", "")),
                business_question=str(p_dict.get("business_question", "")),
                algorithm=p_dict.get("algorithm"),
                dimension=p_dict.get("dimension"),
                metric=p_dict.get("metric"),
                business_metrics=p_dict.get("business_metrics", {}) or {},
                derived_metrics=p_dict.get("derived_metrics", {}) or {},
                findings=findings,
                kpis=kpis,
                chart_data=chart_data,
                charts=[],  # ChartItem 由消费方按需重建
                tables=tables,
                insights=list(p_dict.get("insights", []) or []),
                conclusions=list(p_dict.get("conclusions", []) or []),
                recommendations=list(p_dict.get("recommendations", []) or []),
                metadata=p_dict.get("metadata", {}) or {},
                confidence=_safe_float(p_dict.get("confidence"), 0.5),
                calculator_used=str(p_dict.get("calculator_used", "")),
                template_used=str(p_dict.get("template_used", "")),
                execution_time=_safe_float(p_dict.get("execution_time"), 0.0),
                can_run=bool(p_dict.get("can_run", True)),
                fallback_from=p_dict.get("fallback_from"),
                fallback_reason=p_dict.get("fallback_reason"),
                saved_at=str(p_dict.get("saved_at", "")),
                data_profile=p_dict.get("data_profile", {}) or {},
            )
            packages.append(package)
        except Exception:
            # 单包重构失败不影响其他包
            continue

    return packages


# ============================================================
# 工具函数
# ============================================================

def _safe_float(val: Any, default: Optional[float] = None) -> Optional[float]:
    """安全转换为 float，处理 None / NaN / inf / str"""
    if val is None:
        return default
    try:
        v = float(val)
        import math
        if math.isnan(v) or math.isinf(v):
            return default
        return v
    except (TypeError, ValueError):
        return default
