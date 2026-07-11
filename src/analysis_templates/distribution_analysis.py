"""
分布分析模板 —— 数值的分布形态与频次统计

V3：全面升级为 Business Template，所有业务计算委托 DistributionCalculator
"""

from src.analysis_templates.base import (
    AnalysisTemplate, TemplateMeta, TemplateRuntime,
    KPIItem, TableData, ChartData,
)
from src.calculators import DistributionCalculator, BusinessMetrics
from src.domain import Direction, Severity, FindingCategory


class DistributionAnalysis(AnalysisTemplate):
    meta = TemplateMeta(
        analysis_type="distribution_analysis",
        display_name="分布分析",
        version="3.0",
        description="分析数值数据的分布形态（均值/中位数/标准差/偏度/峰度/分位数/直方图）",
    )

    runtime = TemplateRuntime(
        REQUIRED_SCHEMA={
            "dimension_type": "",
            "metric_type": "numeric",
            "min_dimension": 0,
            "min_metric": 1,
        },
        MIN_ROWS=3,
        FALLBACK="structure_analysis",
    )

    _cache: dict = {}

    def _compute(self, df, metric, bins=10):
        """V3：委托 DistributionCalculator"""
        series = df[metric].dropna()
        m: BusinessMetrics = DistributionCalculator.execute(series, bins)
        self._cache["metrics"] = m
        self._cache["metric"] = metric
        self._cache["_calculator_used"] = "DistributionCalculator"
        return m

    def build_kpis(self, df, dimension, metric, algorithm):
        metric = metric or self._get_numeric_columns(df)[0]
        m = self._compute(df, metric)

        return [
            KPIItem(label="均值", value=f"{m.mean:.2f}" if m.mean else "N/A", change="", kpi_type="avg"),
            KPIItem(label="中位数", value=f"{m.median:.2f}" if m.median else "N/A", change="", kpi_type="avg"),
            KPIItem(label="标准差", value=f"{m.std:.2f}" if m.std else "N/A", change="", kpi_type="rate"),
            KPIItem(label="偏度", value=f"{m.skew:.2f}" if m.skew is not None else "N/A", change="", kpi_type="rate"),
            KPIItem(label="IQR", value=f"{m.iqr:.2f}" if m.iqr else "N/A", change="", kpi_type="rate"),
        ]

    def build_tables(self, df, dimension, metric, algorithm):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return []

        rows = []
        for i in range(len(m.histogram_counts)):
            lo = m.histogram_bins[i] if i < len(m.histogram_bins) else "—"
            hi = m.histogram_bins[i+1] if i+1 < len(m.histogram_bins) else "—"
            rows.append([f"[{lo:.1f}, {hi:.1f})" if isinstance(lo, float) else str(lo),
                         m.histogram_counts[i]])

        return [TableData(
            title=f"{metric}区间分布",
            table_type="summary",
            columns=["区间", "频次"],
            rows=rows,
        )]

    def build_charts(self, df, dimension, metric, algorithm):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return []

        hist_data = []
        for i in range(len(m.histogram_counts)):
            lo = m.histogram_bins[i] if i < len(m.histogram_bins) else 0
            hi = m.histogram_bins[i+1] if i+1 < len(m.histogram_bins) else lo+1
            hist_data.append({"x": f"{lo:.1f}", "y": m.histogram_counts[i]})

        return [ChartData(slot="distribution", chart_type="bar",
                          title=f"{metric}分布直方图", x=dimension, y=metric, data=hist_data)]

    def build_insights(self, df, dimension, metric, algorithm, kpis, chart_data):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return []

        skew_val = m.skew or 0
        if skew_val > 0.5:
            skew_desc = "右偏（长尾在右侧，多数值偏小）"
        elif skew_val < -0.5:
            skew_desc = "左偏（长尾在左侧，多数值偏大）"
        else:
            skew_desc = "近似对称分布"

        return [
            f"{metric}均值为 {m.mean:.2f}，中位数为 {m.median:.2f}，分布呈{skew_desc}",
            f"标准差 {m.std:.2f}，IQR={m.iqr:.2f}，数据离散程度{'较高' if m.std and m.mean and m.std/m.mean > 0.5 else '适中'}",
        ]

    def build_conclusion(self, df, dimension, metric, algorithm, insights):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return ["无法得出分布结论"]

        skew_val = m.skew or 0
        conclusions = [f"summary: {metric}均值 {m.mean:.2f}（中位数 {m.median:.2f}）"]
        if abs(skew_val) > 1:
            conclusions.append("risk: 偏度较大，数据分布不均衡，可能影响平均值代表性")
            conclusions.append("recommendation: 使用中位数替代均值进行决策")
        return conclusions



    def build_findings(self, df, dimension, metric, algorithm, kpis, chart_data):
        m = self._cache.get("metrics")
        f = self.factory
        findings = []
        if m is None:
            return [f.summary("分布分析完成")]
        skew_val = m.skew or 0
        skew_desc = "右偏" if skew_val > 0.5 else "左偏" if skew_val < -0.5 else "近似对称"
        findings.append(f.distribution(
            title=f"{metric}均值为{m.mean:.2f}（中位数{m.median:.2f}），分布呈{skew_desc}",
            metric=metric, confidence=0.95,
            business_meaning=f"数据分布{skew_desc}，{'多数值偏小' if skew_val > 0.5 else '多数值偏大' if skew_val < -0.5 else '分布均匀'}"))
        findings.append(f.summary(f"标准差{m.std:.2f}，IQR={m.iqr:.2f}"))
        if abs(skew_val) > 1:
            findings.append(f.risk(f"偏度较大（{skew_val:.2f}），数据分布不均衡",
                                   business_impact="可能影响平均值代表性",
                                   recommendation="使用中位数替代均值进行决策"))
        return findings

    def execute(self, df, dimension, metric, algorithm=None):
        metric = metric or self._get_numeric_columns(df)[0]
        self._cache = {}
        self._compute(df, metric)
        return super().execute(df, dimension, metric, algorithm)