"""
结构分析模板 —— 各部分在整体中的构成结构

V3：全面升级为 Business Template，使用 RankingCalculator 计算份额和排名
"""

from src.analysis_templates.base import (
    AnalysisTemplate, TemplateMeta, TemplateRuntime,
    KPIItem, TableData, ChartData,
)
from src.calculators import RankingCalculator, BusinessMetrics
from src.domain import Direction, Severity, FindingCategory


class StructureAnalysis(AnalysisTemplate):
    meta = TemplateMeta(
        analysis_type="structure_analysis",
        display_name="结构分析",
        version="3.0",
        description="分析各分类在整体中的结构占比与构成",
    )

    runtime = TemplateRuntime(
        REQUIRED_SCHEMA={
            "dimension_type": "category",
            "metric_type": "numeric",
            "min_dimension": 1,
            "min_metric": 1,
        },
        MIN_ROWS=2,
        FALLBACK="proportion_analysis",
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
            KPIItem(label="Top3结构占比", value=f"{cr3*100:.1f}%", change="", kpi_type="rate"),
            KPIItem(label="分类数量", value=str(len(m.labels)), change="", kpi_type="count"),
        ]

    def build_tables(self, df, dimension, metric, algorithm):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return []

        rows = [[m.labels[i], round(m.values[i], 2),
                 f"{m.shares[i]*100:.1f}%" if i < len(m.shares) else "—"]
                for i in range(len(m.labels))]

        return [TableData(
            title=f"{dimension}结构明细",
            table_type="summary",
            columns=[dimension, metric, "结构占比(%)"],
            rows=rows,
        )]

    def build_charts(self, df, dimension, metric, algorithm):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return []

        n = min(10, len(m.labels))
        data = [{"x": m.labels[i], "y": m.values[i]} for i in range(n)]
        return [ChartData(slot="structure", chart_type="pie",
                          title=f"{dimension}{metric}结构", x=dimension, y=metric, data=data)]

    def build_insights(self, df, dimension, metric, algorithm, kpis, chart_data):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return []

        cr3 = sum(m.shares[:3]) if len(m.shares) >= 3 else 0
        insights = [f"{dimension}共 {len(m.labels)} 个分类"]
        insights.append(f"Top3 分类合计占比 {cr3*100:.1f}%")
        if cr3 > 0.7:
            insights.append("头部集中明显，结构不均衡")
        return insights

    def build_conclusion(self, df, dimension, metric, algorithm, insights):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return ["无法得出结论"]
        cr3 = sum(m.shares[:3]) if len(m.shares) >= 3 else 0
        conclusions = [f"summary: {len(m.labels)} 个分类，Top3占比 {cr3*100:.1f}%"]
        if cr3 > 0.7:
            conclusions.append("recommendation: 注意结构均衡性，避免过度依赖头部")
        return conclusions




    def build_findings(self, df, dimension, metric, algorithm, kpis, chart_data):
        m = self._cache.get("metrics")
        f = self.factory
        findings = []
        if m is None:
            return [f.summary("结构分析完成")]
        cr3 = sum(m.shares[:3]) if len(m.shares) >= 3 else 0
        findings.append(f.structure(
            title=f"共{len(m.labels)}个分类，Top3占比{cr3*100:.1f}%",
            metric=metric, confidence=1.0,
            business_meaning="头部集中明显，结构不均衡" if cr3 > 0.7 else "结构相对均衡"))
        if cr3 > 0.7:
            findings.append(f.risk(f"Top3集中度{cr3*100:.1f}%，结构不均衡",
                                   recommendation="注意结构均衡性，避免过度依赖头部"))
        return findings

    def execute(self, df, dimension, metric, algorithm=None):
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_category_columns(df)[0]
        self._cache = {}
        self._compute(df, dimension, metric)
        return super().execute(df, dimension, metric, algorithm)