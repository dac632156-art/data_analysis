"""
排名分析模板 —— Top/Bottom N 对比排名、占比、累计占比、集中度

V3：全面升级为 Business Template，所有业务计算委托 RankingCalculator
"""

from src.analysis_templates.base import (
    AnalysisTemplate, TemplateMeta, TemplateRuntime,
    KPIItem, TableData, ChartData,
)
from src.calculators import RankingCalculator, BusinessMetrics
from src.domain import Direction, Severity, FindingCategory


class RankingAnalysis(AnalysisTemplate):
    meta = TemplateMeta(
        analysis_type="ranking_analysis",
        display_name="排名分析",
        version="3.0",
        description="按维度对比排名，识别表现最好和最差的分类（排名/占比/累计占比）",
    )

    runtime = TemplateRuntime(
        REQUIRED_SCHEMA={
            "dimension_type": "category",
            "metric_type": "numeric",
            "min_dimension": 1,
            "min_metric": 1,
        },
        MIN_ROWS=3,
        FALLBACK="structure_analysis",
    )

    _cache: dict = {}

    def _compute(self, df, dimension, metric, n=10):
        """V3：全部委托 RankingCalculator"""
        m: BusinessMetrics = RankingCalculator.execute(df, dimension, metric, n)
        self._cache["metrics"] = m
        self._cache["dimension"] = dimension
        self._cache["dimension"] = dimension
        self._cache["metric"] = metric
        return m

    # ===== KPI =====

    def build_kpis(self, df, dimension, metric, algorithm):
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_category_columns(df)[0]
        m = self._compute(df, dimension, metric)

        if not m.top_n_labels:
            return [KPIItem(label="无数据", value="0", change="", kpi_type="sum")]

        top1_name = m.top_n_labels[0]
        top1_val = m.top_n_values[0] if m.top_n_values else 0

        cr3 = sum(m.shares[:3]) if len(m.shares) >= 3 else sum(m.shares)
        cc = m.cumulative_shares[9] if len(m.cumulative_shares) >= 10 else (
            m.cumulative_shares[-1] if m.cumulative_shares else 0)

        return [
            KPIItem(label=f"Top1: {top1_name}", value=f"{top1_val:,.2f}", change="", kpi_type="sum"),
            KPIItem(label="Top3集中度", value=f"{cr3*100:.1f}%", change="", kpi_type="rate"),
            KPIItem(label="Top10累计贡献", value=f"{cc*100:.1f}%", change="", kpi_type="rate"),
        ]

    # ===== Table =====

    def build_tables(self, df, dimension, metric, algorithm):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return []

        rows = []
        n = min(20, len(m.labels))
        for i in range(n):
            rank = m.ranks[i] if i < len(m.ranks) else (i + 1)
            share = m.shares[i] if i < len(m.shares) else 0
            cum_share = m.cumulative_shares[i] if i < len(m.cumulative_shares) else 0
            rows.append([rank, m.labels[i], round(m.values[i], 2),
                         f"{share*100:.1f}%", f"{cum_share*100:.1f}%"])

        return [TableData(
            title=f"{dimension}排名明细",
            table_type="ranking",
            columns=["排名", dimension, metric, "占比(%)", "累计占比(%)"],
            rows=rows,
        )]

    # ===== Chart =====

    def build_charts(self, df, dimension, metric, algorithm):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return []

        n = min(10, len(m.top_n_labels))
        bar_data = [{"x": m.top_n_labels[i], "y": m.top_n_values[i]} for i in range(n)]

        cum_data = [{"x": m.labels[i], "y": m.cumulative_shares[i] * 100}
                     for i in range(min(10, len(m.labels)))
                     if i < len(m.cumulative_shares)]

        return [
            ChartData(slot="ranking_bar", chart_type="bar",
                      title=f"Top{n} {dimension}排名", x=dimension, y=metric, data=bar_data),
            ChartData(slot="cumulative_share", chart_type="line",
                      title=f"累计占比（帕累托曲线）", x=dimension, y="累计占比(%)", data=cum_data),
        ]

    # ===== Insight =====

    def build_insights(self, df, dimension, metric, algorithm, kpis, chart_data):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None or not m.labels:
            return ["数据不足"]

        top1_label = m.top_n_labels[0] if m.top_n_labels else m.labels[0]
        top1_val = m.top_n_values[0] if m.top_n_values else m.values[0]
        bottom_label = m.bottom_n_labels[0] if m.bottom_n_labels else m.labels[-1]
        bottom_val = m.bottom_n_values[0] if m.bottom_n_values else m.values[-1]
        cr3 = sum(m.shares[:3]) if len(m.shares) >= 3 else sum(m.shares) if m.shares else 0

        return [
            f"「{top1_label}」的{metric}最高，达到 {top1_val:,.2f}",
            f"「{bottom_label}」的{metric}最低，仅 {bottom_val:,.2f}",
            f"Top3 分类占据了 {cr3*100:.1f}% 的{metric}",
        ]

    # ===== Conclusion =====

    def build_conclusion(self, df, dimension, metric, algorithm, insights):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return ["无法得出有效结论"]

        cr3 = sum(m.shares[:3]) if len(m.shares) >= 3 else 0
        conclusions = [f"summary: {dimension}排名分析完成，共 {len(m.labels)} 个分类"]

        if cr3 > 0.8:
            conclusions.append("risk: Top3集中度过高（>80%），头部依赖风险明显")
            conclusions.append("recommendation: 建议培育中腰部分类，分散业务风险")
        elif cr3 > 0.5:
            conclusions.append("opportunity: 头部集中度适中，中腰部有增长空间")
            conclusions.append("recommendation: 针对中腰部加大资源投放，提升整体均衡性")
        else:
            conclusions.append("opportunity: 分布较均衡，可针对各分类差异化运营")

        return conclusions


    # ===== V3：业务发现与证据 =====

    def build_findings(self, df, dimension, metric, algorithm, kpis, chart_data):
        m = self._cache.get("metrics")
        f = self.factory
        findings = []
        if m is None or not m.labels:
            return [f.summary("排名分析完成")]

        top1_label = m.top_n_labels[0] if m.top_n_labels else m.labels[0]
        top1_val = m.top_n_values[0] if m.top_n_values else m.values[0]
        findings.append(f.ranking(entity=top1_label, metric=metric, value=top1_val, rank=1, confidence=1.0))

        cr3 = sum(m.shares[:3]) if len(m.shares) >= 3 else 0
        if cr3 > 0:
            findings.append(f.concentration(
                title=f"Top3分类贡献{cr3*100:.1f}%的{metric}",
                metric=metric, value=cr3, unit="%",
                confidence=1.0, business_meaning=f"前3名占据了{cr3*100:.1f}%的份额"))

        if m.bottom_n_labels and m.bottom_n_values:
            findings.append(f.ranking(
                entity=m.bottom_n_labels[0], metric=metric, value=m.bottom_n_values[0],
                title=f"最低：{m.bottom_n_labels[0]}（{m.bottom_n_values[0]:,.2f}）",
                severity=Severity.INFO))

        if cr3 > 0.8:
            findings.append(f.risk(f"Top3集中度{cr3*100:.1f}%，头部依赖风险明显",
                                   metric=metric,
                                   recommendation="建议培育中腰部，分散业务风险"))
        elif cr3 > 0.5:
            findings.append(f.opportunity(f"中度集中（{cr3*100:.1f}%），中腰部有增长空间", metric=metric))

        return findings
    def execute(self, df, dimension, metric, algorithm=None):
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_category_columns(df)[0]
        self._cache = {}
        self._compute(df, dimension, metric)
        return super().execute(df, dimension, metric, algorithm)
