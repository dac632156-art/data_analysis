"""
集中度分析模板 —— 帕累托效应、CR3、CR5、HHI指数

V3：全面升级为 Business Template，所有业务计算委托 ConcentrationCalculator
"""

from src.analysis_templates.base import (
    AnalysisTemplate, TemplateMeta, TemplateRuntime,
    KPIItem, TableData, ChartData,
)
from src.calculators import ConcentrationCalculator, BusinessMetrics
from src.domain import Direction, Severity, FindingCategory


class ConcentrationAnalysis(AnalysisTemplate):
    meta = TemplateMeta(
        analysis_type="concentration_analysis",
        display_name="集中度分析",
        version="3.0",
        description="判断数据是否高度集中（CR3/CR5/HHI/帕累托）",
        supported_algorithms=["pareto", "hhi", "gini"],
    )

    runtime = TemplateRuntime(
        REQUIRED_SCHEMA={
            "dimension_type": "category",
            "metric_type": "numeric",
            "min_dimension": 1,
            "min_metric": 1,
        },
        MIN_ROWS=3,
        FALLBACK="ranking_analysis",
    )

    _cache: dict = {}

    def _compute(self, df, dimension, metric):
        """V3：委托 ConcentrationCalculator"""
        m: BusinessMetrics = ConcentrationCalculator.execute(df, dimension, metric)
        self._cache["metrics"] = m
        self._cache["dimension"] = dimension
        self._cache["metric"] = metric
        self._cache["_calculator_used"] = "ConcentrationCalculator"
        return m

    def build_kpis(self, df, dimension, metric, algorithm):
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_category_columns(df)[0]
        m = self._compute(df, dimension, metric)

        hhi_val = m.hhi or 0
        cr3_pct = (m.cr3 or 0) * 100
        cr5_pct = (m.cr5 or 0) * 100
        top20_pct = (m.top20_share or 0) * 100

        return [
            KPIItem(label="HHI指数", value=f"{hhi_val:.0f}", change="", kpi_type="rate"),
            KPIItem(label="CR3", value=f"{cr3_pct:.1f}%", change="", kpi_type="rate"),
            KPIItem(label="CR5", value=f"{cr5_pct:.1f}%", change="", kpi_type="rate"),
            KPIItem(label="Top20%贡献", value=f"{top20_pct:.1f}%", change="", kpi_type="rate"),
            KPIItem(label="分类数", value=str(len(m.labels)), change="", kpi_type="count"),
        ]

    def build_tables(self, df, dimension, metric, algorithm):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return []

        rows = []
        for i in range(len(m.labels)):
            share = m.shares[i] if i < len(m.shares) else 0
            cum_share = m.cumulative_shares[i] if i < len(m.cumulative_shares) else 0
            rows.append([m.labels[i], round(m.values[i], 2),
                         f"{share*100:.1f}%", f"{cum_share*100:.1f}%"])

        return [TableData(
            title=f"{dimension}集中度明细",
            table_type="ranking",
            columns=[dimension, metric, "占比(%)", "累计占比(%)"],
            rows=rows,
        )]

    def build_charts(self, df, dimension, metric, algorithm):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return []

        bar_data = [{"x": m.labels[i], "y": m.values[i]} for i in range(min(15, len(m.labels)))]
        cum_data = [{"x": m.labels[i],
                      "y": (m.cumulative_shares[i] * 100) if i < len(m.cumulative_shares) else 0}
                     for i in range(min(15, len(m.labels)))]

        return [
            ChartData(slot="concentration_bar", chart_type="bar",
                      title=f"{dimension}集中度分布", x=dimension, y=metric, data=bar_data),
            ChartData(slot="pareto_line", chart_type="line",
                      title="帕累托曲线（累计占比）", x=dimension, y="累计占比(%)", data=cum_data),
        ]

    def build_insights(self, df, dimension, metric, algorithm, kpis, chart_data):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return []

        hhi = m.hhi or 0
        top20_pct = (m.top20_share or 0) * 100
        top1_label = m.labels[0] if m.labels else "—"
        top1_share = (m.shares[0] * 100) if m.shares else 0

        insights = [f"「{top1_label}」占比 {top1_share:.1f}%，处于领先地位"]

        if hhi > 2500:
            insights.append(f"HHI={hhi:.0f} → 高度集中市场（>2500），存在垄断风险")
        elif hhi > 1500:
            insights.append(f"HHI={hhi:.0f} → 中度集中市场（1500-2500）")
        else:
            insights.append(f"HHI={hhi:.0f} → 分散竞争市场（<1500）")

        if top20_pct > 80:
            insights.append(f"Top20%贡献 {top20_pct:.1f}%，符合帕累托法则（二八效应显著）")
        else:
            insights.append(f"Top20%贡献 {top20_pct:.1f}%，帕累托效应不显著")

        return insights

    def build_conclusion(self, df, dimension, metric, algorithm, insights):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return ["无法得出有效结论"]

        hhi = m.hhi or 0
        top20_pct = (m.top20_share or 0) * 100

        conclusions = [f"summary: HHI={hhi:.0f}，Top20%贡献 {top20_pct:.1f}%"]
        if hhi > 2500:
            conclusions.append("risk: 市场高度集中，头部依赖严重")
            conclusions.append("recommendation: 评估集中风险，制定多元化策略")
        elif top20_pct > 70:
            conclusions.append("opportunity: 帕累托效应存在，可聚焦头部提升效率")
        return conclusions



    def build_findings(self, df, dimension, metric, algorithm, kpis, chart_data):
        m = self._cache.get("metrics")
        f = self.factory
        findings = []
        if m is None:
            return [f.summary("集中度分析完成")]
        hhi = m.hhi or 0
        cr3_pct = (m.cr3 or 0) * 100
        cr5_pct = (m.cr5 or 0) * 100
        top20_pct = (m.top20_share or 0) * 100
        ba = m.business_assessment or {}
        level = ba.get("level", "")
        risk = ba.get("risk", "")
        resilience = ba.get("resilience", "")
        top1 = m.labels[0] if m.labels else "头部"

        # —— 主集中度发现：业务推理 ——
        meaning = f"市场{level}（HHI={hhi:.0f}），{risk}，增长韧性{resilience}。"
        impact = (f"若头部「{top1}」波动，将显著影响整体（韧性{resilience}）；"
                  f"Top20%贡献{top20_pct:.1f}%，头部集中度{('极高' if top20_pct > 80 else '可控')}。")
        rec = ("评估头部依赖风险，制定多元化/第二曲线策略" if resilience != "高"
               else "维持当前健康结构，关注潜在头部崛起")

        findings.append(f.concentration(
            title=f"HHI={hhi:.0f}，CR3={cr3_pct:.1f}%，CR5={cr5_pct:.1f}%",
            metric="HHI", value=hhi, unit="点", confidence=1.0,
            description=meaning,
            business_meaning=meaning,
            business_impact=impact,
            recommendation=rec))
        if hhi > 2500:
            findings.append(f.risk(f"市场高度集中（HHI>2500），存在垄断依赖风险",
                                   business_impact=impact,
                                   recommendation="评估集中风险，制定多元化策略"))
        findings.append(f.summary(f"共{len(m.labels)}个分类"))
        return findings

    def execute(self, df, dimension, metric, algorithm=None):
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_category_columns(df)[0]
        self._cache = {}
        self._compute(df, dimension, metric)
        return super().execute(df, dimension, metric, algorithm)