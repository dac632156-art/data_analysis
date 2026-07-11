"""
FindingFactory —— BusinessFinding 工厂（统一创建入口）

所有 Template 必须通过此工厂创建 BusinessFinding，禁止直接 new。

保证：
- 字段完整性
- 数据一致性
- 默认值合理填充
"""

from __future__ import annotations
from typing import List, Optional, Dict, Any
import uuid

from src.domain.business_finding import (
    BusinessFinding,
    EvidenceRef,
    FindingCategory,
    Direction,
    Severity,
)


class FindingFactory:
    """BusinessFinding 工厂

    使用方式（Template 中）：
        factory = FindingFactory("growth_analysis")
        finding = factory.growth(
            entity="华东", metric="销售额", value=-12.0, unit="%",
            direction=Direction.DOWN,
            business_meaning="华东市场正在萎缩",
        )
        finding = finding.link_evidence(chart_slots=["trend"], kpi_labels=["平均同比增长率"])
    """

    def __init__(self, analysis_type: str):
        self.analysis_type = analysis_type

    # ================================================================
    # 通用创建方法
    # ================================================================

    def create(
        self,
        category: FindingCategory,
        title: str,
        *,
        description: str = "",
        metric: str = "",
        dimension: str = "",
        entity: str = "",
        value: Optional[float] = None,
        unit: str = "",
        direction: Direction = Direction.UNKNOWN,
        change_pct: Optional[float] = None,
        severity: Severity = Severity.INFO,
        confidence: float = 1.0,
        business_meaning: str = "",
        business_impact: str = "",
        recommendation: str = "",
        chart_slots: Optional[List[str]] = None,
        table_titles: Optional[List[str]] = None,
        kpi_labels: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BusinessFinding:
        """通用创建方法——所有特殊方法最终调用此方法"""
        evidence = EvidenceRef(
            chart_slots=tuple(chart_slots or []),
            table_titles=tuple(table_titles or []),
            kpi_labels=tuple(kpi_labels or []),
        )
        return BusinessFinding(
            id=str(uuid.uuid4()),
            analysis_type=self.analysis_type,
            category=category,
            title=title,
            description=description,
            metric=metric,
            dimension=dimension,
            entity=entity,
            value=value,
            unit=unit,
            direction=direction,
            change_pct=change_pct,
            severity=severity,
            confidence=confidence,
            business_meaning=business_meaning,
            business_impact=business_impact,
            recommendation=recommendation,
            evidence=evidence,
            tags=tuple(tags or []),
            metadata=metadata or {},
        )

    # ================================================================
    # 语义化创建方法（推荐使用）
    # ================================================================

    def growth(
        self,
        entity: str = "",
        metric: str = "",
        value: Optional[float] = None,
        unit: str = "%",
        direction: Direction = Direction.UNKNOWN,
        change_pct: Optional[float] = None,
        **kwargs,
    ) -> BusinessFinding:
        """增长发现"""
        title = kwargs.pop("title", "")
        if not title and entity and metric and value is not None:
            dir_word = {"up": "增长", "down": "下降", "flat": "持平"}.get(direction.value, "变化")
            title = f"{entity}{metric}{dir_word}{abs(value)}{unit}"
        return self.create(
            category=FindingCategory.GROWTH,
            title=title,
            entity=entity, metric=metric, value=value, unit=unit,
            direction=direction, change_pct=change_pct,
            **kwargs,
        )

    def ranking(
        self,
        entity: str = "",
        metric: str = "",
        value: Optional[float] = None,
        rank: Optional[int] = None,
        **kwargs,
    ) -> BusinessFinding:
        """排名发现"""
        title = kwargs.pop("title", "")
        if not title and entity and metric:
            rank_str = f"（#{rank}）" if rank else ""
            title = f"「{entity}」{metric}排名第一{rank_str}"
        return self.create(
            category=FindingCategory.RANKING,
            title=title,
            entity=entity, metric=metric, value=value,
            tags=kwargs.pop("tags", ()) + (("top1",) if rank == 1 else ("ranking",)),
            **kwargs,
        )

    def concentration(
        self,
        metric: str = "",
        value: Optional[float] = None,
        unit: str = "%",
        **kwargs,
    ) -> BusinessFinding:
        """集中度发现"""
        return self.create(
            category=FindingCategory.CONCENTRATION,
            metric=metric, value=value, unit=unit,
            **kwargs,
        )

    def anomaly(
        self,
        entity: str = "",
        metric: str = "",
        value: Optional[float] = None,
        z_score: Optional[float] = None,
        **kwargs,
    ) -> BusinessFinding:
        """异常发现"""
        severity = kwargs.pop("severity", Severity.HIGH)
        title = kwargs.pop("title", "")
        if not title and entity:
            z_str = f"（Z={z_score:.2f}）" if z_score is not None else ""
            title = f"「{entity}」检测到异常{z_str}"
        return self.create(
            category=FindingCategory.ANOMALY,
            title=title,
            entity=entity, metric=metric, value=value,
            severity=severity, confidence=0.85,
            tags=kwargs.pop("tags", ()) + ("anomaly",),
            **kwargs,
        )

    def retention(
        self,
        metric: str = "复购率",
        value: Optional[float] = None,
        unit: str = "%",
        **kwargs,
    ) -> BusinessFinding:
        """复购发现"""
        return self.create(
            category=FindingCategory.RETENTION,
            metric=metric, value=value, unit=unit,
            **kwargs,
        )

    def comparison(
        self,
        entity: str = "",
        metric: str = "",
        value: Optional[float] = None,
        **kwargs,
    ) -> BusinessFinding:
        """对比发现"""
        return self.create(
            category=FindingCategory.COMPARISON,
            entity=entity, metric=metric, value=value,
            **kwargs,
        )

    def correlation(
        self,
        metric: str = "",
        value: Optional[float] = None,
        **kwargs,
    ) -> BusinessFinding:
        """相关发现"""
        return self.create(
            category=FindingCategory.CORRELATION,
            metric=metric, value=value,
            **kwargs,
        )

    def distribution(
        self,
        metric: str = "",
        **kwargs,
    ) -> BusinessFinding:
        """分布发现"""
        return self.create(
            category=FindingCategory.DISTRIBUTION,
            metric=metric,
            **kwargs,
        )

    def structure(
        self,
        metric: str = "",
        **kwargs,
    ) -> BusinessFinding:
        """结构发现"""
        return self.create(
            category=FindingCategory.STRUCTURE,
            metric=metric,
            **kwargs,
        )

    def risk(
        self,
        title: str,
        severity: Severity = Severity.HIGH,
        **kwargs,
    ) -> BusinessFinding:
        """风险发现"""
        return self.create(
            category=FindingCategory.RISK,
            title=title,
            severity=severity,
            confidence=kwargs.pop("confidence", 0.85),
            **kwargs,
        )

    def opportunity(
        self,
        title: str,
        **kwargs,
    ) -> BusinessFinding:
        """机会发现"""
        return self.create(
            category=FindingCategory.OPPORTUNITY,
            title=title,
            severity=Severity.MEDIUM,
            confidence=kwargs.pop("confidence", 0.80),
            **kwargs,
        )

    def summary(
        self,
        title: str,
        **kwargs,
    ) -> BusinessFinding:
        """摘要发现"""
        return self.create(
            category=FindingCategory.SUMMARY,
            title=title,
            severity=Severity.INFO,
            **kwargs,
        )

    # ================================================================
    # 批量链接证据
    # ================================================================

    @staticmethod
    def link_all_evidence(
        findings: List[BusinessFinding],
        chart_slots: Optional[List[str]] = None,
        table_titles: Optional[List[str]] = None,
        kpi_labels: Optional[List[str]] = None,
    ) -> List[BusinessFinding]:
        """为所有 finding 批量链接证据

        每个 finding 继承传入的全部引用（在模板中调用时，通常是全部 chart/table/kpi）。
        """
        return [
            f.link_evidence(chart_slots, table_titles, kpi_labels)
            for f in findings
        ]