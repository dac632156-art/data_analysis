"""
对比分析模板 —— 分组差异对比、差异率、提升度

V3：全面升级为 Business Template，所有业务计算委托 ComparisonCalculator
"""

from src.analysis_templates.base import (
    AnalysisTemplate, TemplateMeta, TemplateRuntime,
    KPIItem, TableData, ChartData,
)
from src.calculators import ComparisonCalculator, BusinessMetrics
from src.domain import Direction, Severity, FindingCategory


class ComparisonAnalysis(AnalysisTemplate):
    meta = TemplateMeta(
        analysis_type="comparison_analysis",
        display_name="对比分析",
        version="3.0",
        description="对比多个分类组之间的指标差异，识别优劣和差异程度（差异/差异率/提升度）",
    )

    runtime = TemplateRuntime(
        REQUIRED_SCHEMA={
            "dimension_type": "category",
            "metric_type": "numeric",
            "min_dimension": 1,
            "min_metric": 1,
        },
        MIN_ROWS=3,
        MIN_DISTINCT_VALUES=2,
        FALLBACK="ranking_analysis",
    )

    _cache: dict = {}

    def _compute(self, df, dimension, metric):
        """V3：全部委托 ComparisonCalculator"""
        m: BusinessMetrics = ComparisonCalculator.execute(df, dimension, metric)
        self._cache["metrics"] = m
        self._cache["dimension"] = dimension
        self._cache["metric"] = metric
        self._cache["_calculator_used"] = "ComparisonCalculator"
        return m

    def build_kpis(self, df, dimension, metric, algorithm):
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_category_columns(df)[0]
        m = self._compute(df, dimension, metric)

        global_mean = m.global_mean or 0
        kpis = [KPIItem(label="全局均值", value=f"{global_mean:,.2f}", change="", kpi_type="avg")]

        if m.values:
            best_idx = max(range(len(m.values)), key=lambda i: m.values[i])
            worst_idx = min(range(len(m.values)), key=lambda i: m.values[i])
            best_label = m.labels[best_idx] if best_idx < len(m.labels) else "—"
            best_val = m.values[best_idx]
            dr_best = m.difference_rates[best_idx] if best_idx < len(m.difference_rates) else None

            kpis.append(KPIItem(
                label=f"最优组: {best_label}",
                value=f"{best_val:,.2f}",
                change=f"+{dr_best:.1f}%" if dr_best and dr_best > 0 else f"{dr_best:.1f}%" if dr_best else "",
                kpi_type="avg"))

            if best_idx != worst_idx and len(m.values) > 1:
                worst_val = m.values[worst_idx]
                max_gap = ((best_val / worst_val - 1) * 100) if worst_val > 0 else 0
                kpis.append(KPIItem(label="组间最大差距", value=f"{max_gap:.1f}%", change="", kpi_type="rate"))

        return kpis

    def build_tables(self, df, dimension, metric, algorithm):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return []

        rows = []
        for i in range(len(m.labels)):
            diff = m.differences[i] if i < len(m.differences) else None
            dr = m.difference_rates[i] if i < len(m.difference_rates) else None
            dr_str = f"+{dr:.1f}%" if dr and dr > 0 else f"{dr:.1f}%" if dr else "—"
            rows.append([m.labels[i], round(m.values[i], 2),
                         round(diff, 2) if diff else "—", dr_str])

        return [TableData(
            title=f"{dimension}对比明细",
            table_type="comparison",
            columns=[dimension, f"{metric}均值", "vs全局差异", "差异率(%)"],
            rows=rows,
        )]

    def build_charts(self, df, dimension, metric, algorithm):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return []

        bar_data = [{"x": m.labels[i], "y": m.values[i]} for i in range(len(m.labels))]
        diff_data = [{"x": m.labels[i],
                       "y": m.differences[i] if i < len(m.differences) else None}
                     for i in range(len(m.labels))]

        return [
            ChartData(slot="comparison_bar", chart_type="bar",
                      title=f"{dimension}均值对比", x=dimension, y=metric, data=bar_data),
            ChartData(slot="difference_bar", chart_type="bar",
                      title=f"vs全局均值差异", x=dimension, y=f"{metric}差异", data=diff_data),
        ]

    def build_insights(self, df, dimension, metric, algorithm, kpis, chart_data):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return ["数据不足以进行对比分析"]

        if not m.values:
            return ["无可比较数据"]

        best_idx = max(range(len(m.values)), key=lambda i: m.values[i])
        worst_idx = min(range(len(m.values)), key=lambda i: m.values[i])
        best_label = m.labels[best_idx]
        worst_label = m.labels[worst_idx]
        dr_best = m.difference_rates[best_idx] if best_idx < len(m.difference_rates) else 0
        dr_worst = m.difference_rates[worst_idx] if worst_idx < len(m.difference_rates) else 0

        insights = [
            f"「{best_label}」的{metric}均值最高，较全局均值高出 {dr_best:.1f}%",
            f"「{worst_label}」的{metric}均值最低，低于全局均值 {abs(dr_worst):.1f}%",
        ]

        best_val = m.values[best_idx]
        worst_val = m.values[worst_idx]
        gap = ((best_val / worst_val - 1) * 100) if worst_val > 0 else 0
        if gap > 50:
            insights.append(f"组间差异较大（{gap:.0f}%），需关注弱势组")
        else:
            insights.append(f"组间差异在 {gap:.1f}% 以内，整体分布较均匀")

        return insights

    def build_conclusion(self, df, dimension, metric, algorithm, insights):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return ["无法得出有效对比结论"]

        best_idx = max(range(len(m.values)), key=lambda i: m.values[i])
        worst_idx = min(range(len(m.values)), key=lambda i: m.values[i])

        conclusions = [
            f"summary: 「{m.labels[best_idx]}」在{metric}上表现最优，建议作为标杆推广其经验",
        ]

        best_val = m.values[best_idx]
        worst_val = m.values[worst_idx]
        gap = ((best_val / worst_val - 1) * 100) if worst_val > 0 else 0
        if gap > 30:
            conclusions.append(
                f"risk: 最优/最弱组差距达 {gap:.0f}%，"f"「{m.labels[worst_idx]}」需重点改进")
            conclusions.append(
                f"recommendation: 分析「{m.labels[best_idx]}」成功因素，"f"向「{m.labels[worst_idx]}」推广最佳实践")
        else:
            conclusions.append("opportunity: 各组差距不大，可通过精细化管理进一步拉开差距")

        return conclusions



    def build_findings(self, df, dimension, metric, algorithm, kpis, chart_data):
        m = self._cache.get("metrics")
        f = self.factory
        findings = []
        if m is None or not m.values:
            return [f.summary("对比分析完成")]

        best_idx = max(range(len(m.values)), key=lambda i: m.values[i]) if m.values else 0
        worst_idx = min(range(len(m.values)), key=lambda i: m.values[i]) if m.values else 0
        best_label = m.labels[best_idx] if best_idx < len(m.labels) else "?"
        worst_label = m.labels[worst_idx] if worst_idx < len(m.labels) else "?"
        dr_best = m.difference_rates[best_idx] if best_idx < len(m.difference_rates) else 0

        dr_word = "高出" if (dr_best or 0) > 0 else "低于"
        findings.append(f.comparison(
            entity=best_label, metric=metric, value=m.values[best_idx],
            title="最优：" + best_label + "（较全局均值" + dr_word + " " + str(abs(dr_best))[:4] + "%）",
            confidence=1.0))

        if best_idx != worst_idx and len(m.values) > 1:
            best_val = m.values[best_idx]; worst_val = m.values[worst_idx]
            gap = ((best_val / worst_val - 1) * 100) if worst_val > 0 else 0
            findings.append(f.comparison(
                entity=worst_label, metric=metric,
                title="最优与最弱组差距" + str(int(gap)) + "%",
                business_impact=worst_label + "需重点关注",
                severity=Severity.MEDIUM if gap > 50 else Severity.INFO))

        if m.global_mean:
            above_avg = sum(1 for v in m.values if v > m.global_mean)
            findings.append(f.summary("共" + str(above_avg) + "/" + str(len(m.values)) + "个分组高于全局均值"))

        return findings

    def execute(self, df, dimension, metric, algorithm=None):
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_category_columns(df)[0]
        self._cache = {}
        self._compute(df, dimension, metric)
        return super().execute(df, dimension, metric, algorithm)