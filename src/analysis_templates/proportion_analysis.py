"""
占比分析模板 —— 各部分在整体中的百分比份额

V3：全面升级为 Business Template，使用 RankingCalculator 计算份额
"""

from src.analysis_templates.base import (
    AnalysisTemplate, TemplateMeta, TemplateRuntime,
    KPIItem, TableData, ChartData,
)
from src.calculators import RankingCalculator, BusinessMetrics
from src.domain import Direction, Severity, FindingCategory


class ProportionAnalysis(AnalysisTemplate):
    meta = TemplateMeta(
        analysis_type="proportion_analysis",
        display_name="占比分析",
        version="3.0",
        description="计算各部分在整体中的百分比份额与集中度",
    )

    runtime = TemplateRuntime(
        REQUIRED_SCHEMA={
            "dimension_type": "category",
            "metric_type": "numeric",
            "min_dimension": 1,
            "min_metric": 1,
        },
        MIN_ROWS=2,
        FALLBACK="structure_analysis",
    )

    _cache: dict = {}

    def _compute(self, df, dimension, metric):
        """V3：委托 RankingCalculator"""
        m: BusinessMetrics = RankingCalculator.execute(df, dimension, metric, 20)
        self._cache["metrics"] = m
        self._cache["dimension"] = dimension
        self._cache["metric"] = metric
        self._cache["_calculator_used"] = "RankingCalculator"
        return m

    def build_kpis(self, df, dimension, metric, algorithm):
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_category_columns(df)[0]
        m = self._compute(df, dimension, metric)

        total = sum(m.values)
        cr3 = sum(m.shares[:3]) if len(m.shares) >= 3 else sum(m.shares) if m.shares else 0

        return [
            KPIItem(label=f"总{metric}", value=f"{total:,.0f}", change="", kpi_type="sum"),
            KPIItem(label="Top3合计占比", value=f"{cr3*100:.1f}%", change="", kpi_type="rate"),
        ]

    def build_tables(self, df, dimension, metric, algorithm):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return []

        rows = [[m.labels[i], round(m.values[i], 2),
                 f"{m.shares[i]*100:.1f}%" if i < len(m.shares) else "—"]
                for i in range(len(m.labels))]

        return [TableData(
            title=f"{dimension}占比明细",
            table_type="summary",
            columns=[dimension, metric, "占比(%)"],
            rows=rows,
        )]

    def build_charts(self, df, dimension, metric, algorithm):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return []

        n = min(10, len(m.labels))
        data = [{"x": m.labels[i], "y": m.values[i]} for i in range(n)]
        return [ChartData(slot="proportion", chart_type="pie",
                          title=f"{dimension}{metric}占比", x=dimension, y=metric, data=data)]

    def build_insights(self, df, dimension, metric, algorithm, kpis, chart_data):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return []

        top1_label = m.labels[0] if m.labels else "—"
        top1_share = (m.shares[0] * 100) if m.shares else 0
        cr3 = sum(m.shares[:3]) if len(m.shares) >= 3 else 0

        insights = [f"「{top1_label}」占比最高，达 {top1_share:.1f}%"]
        if cr3 > 0.8:
            insights.append(f"Top3合计占比 {cr3*100:.1f}%，集中度较高")
        return insights

    def build_conclusion(self, df, dimension, metric, algorithm, insights):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return ["无法得出结论"]
        cr3 = sum(m.shares[:3]) if len(m.shares) >= 3 else 0
        conclusions = [f"summary: Top3占比 {cr3*100:.1f}%"]
        if cr3 > 0.8:
            conclusions.append("risk: 集中度过高")
        return conclusions




    def build_findings(self, df, dimension, metric, algorithm, kpis, chart_data):
        m = self._cache.get("metrics")
        f = self.factory
        findings = []
        if m is None:
            return [f.summary("占比分析完成")]
        top1_label = m.labels[0] if m.labels else "?"; top1_share = (m.shares[0] * 100) if m.shares else 0
        cr3 = sum(m.shares[:3]) if len(m.shares) >= 3 else 0
        findings.append(f.structure(
            title=f"「{top1_label}」占比最高，达{top1_share:.1f}%",
            metric=metric, entity=top1_label, value=top1_share, unit="%", confidence=1.0))
        findings.append(f.concentration(
            title=f"Top3合计占比{cr3*100:.1f}%",
            metric=metric, value=cr3, unit="%", confidence=1.0))
        if cr3 > 0.8:
            findings.append(f.risk(f"集中度较高（{cr3*100:.1f}%）", metric=metric))
        return findings

    def execute(self, df, dimension, metric, algorithm=None):
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_category_columns(df)[0]
        self._cache = {}
        self._compute(df, dimension, metric)
        return super().execute(df, dimension, metric, algorithm)