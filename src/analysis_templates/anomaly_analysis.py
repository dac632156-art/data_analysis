"""
异常分析模板 —— Z-Score / IQR 异常检测

V3：全面升级为 Business Template，所有业务计算委托 AnomalyCalculator
"""

from src.analysis_templates.base import (
    AnalysisTemplate, TemplateMeta, TemplateRuntime,
    KPIItem, TableData, ChartData,
)
from src.calculators import AnomalyCalculator, BusinessMetrics
from src.domain import Direction, Severity, FindingCategory


class AnomalyAnalysis(AnalysisTemplate):
    meta = TemplateMeta(
        analysis_type="anomaly_analysis",
        display_name="异常分析",
        version="3.0",
        description="检测数据中的异常值和离群点（Z-Score/IQR）",
        supported_algorithms=["zscore", "iqr"],
    )

    runtime = TemplateRuntime(
        REQUIRED_SCHEMA={
            "dimension_type": "category",
            "metric_type": "numeric",
            "min_dimension": 1,
            "min_metric": 1,
        },
        MIN_ROWS=5,
        FALLBACK="structure_analysis",
    )

    _cache: dict = {}

    def _compute(self, df, dimension, metric, method="zscore", threshold=3.0):
        """V3：委托 AnomalyCalculator"""
        grouped = df.groupby(dimension)[metric].sum().reset_index()
        values = [float(v) for v in grouped[metric]]
        labels = [str(v) for v in grouped[dimension]]
        m: BusinessMetrics = AnomalyCalculator.execute(values, labels, method, threshold)
        self._cache["metrics"] = m
        self._cache["dimension"] = dimension
        self._cache["metric"] = metric
        self._cache["_calculator_used"] = "AnomalyCalculator"
        self._cache["grouped"] = grouped
        return m

    def build_kpis(self, df, dimension, metric, algorithm):
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_category_columns(df)[0]
        method = algorithm or "zscore"
        m = self._compute(df, dimension, metric, method)

        total = len(m.values)
        anomaly_count = len(m.anomaly_indices)
        rate = (anomaly_count / total * 100) if total > 0 else 0

        return [
            KPIItem(label="异常值数量", value=str(anomaly_count), change="", kpi_type="count"),
            KPIItem(label="异常率", value=f"{rate:.1f}%", change="", kpi_type="rate"),
            KPIItem(label="检测方法", value=m.anomaly_method.upper(), change="", kpi_type="count"),
        ]

    def build_tables(self, df, dimension, metric, algorithm):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return []

        if not m.anomaly_indices:
            return [TableData(title="异常检测结果", table_type="detail",
                              columns=["结果"], rows=[["未检测到异常值"]])]

        rows = []
        for i in m.anomaly_indices:
            label = m.anomaly_labels[m.anomaly_indices.index(i)] if m.anomaly_labels else str(i)
            val = m.values[i] if i < len(m.values) else None
            z = m.z_scores[i] if i < len(m.z_scores) else None
            rows.append([label, round(val, 2) if val else "—",
                         round(z, 2) if z is not None else "—"])

        return [TableData(title="异常明细", table_type="exception",
                          columns=["分类", metric, "Z-Score"], rows=rows)]

    def build_charts(self, df, dimension, metric, algorithm):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return []

        scatter_data = []
        for i in range(len(m.labels)):
            z = m.z_scores[i] if i < len(m.z_scores) else 0
            is_anom = "异常" if i in m.anomaly_indices else "正常"
            scatter_data.append({"x": m.labels[i], "y": m.values[i],
                                 "z_score": round(z, 2), "category": is_anom})

        return [ChartData(slot="anomaly_scatter", chart_type="scatter",
                          title=f"{metric}异常检测", x=dimension, y=metric, data=scatter_data)]

    def build_insights(self, df, dimension, metric, algorithm, kpis, chart_data):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return []

        anomaly_count = len(m.anomaly_indices)
        total = len(m.values)
        if anomaly_count == 0:
            return [f"未检测到显著异常值（{m.anomaly_method.upper()} 方法，阈值 {m.anomaly_threshold}）"]

        insights = [f"检测到 {anomaly_count}/{total} 个异常值（{(anomaly_count/total*100):.1f}%）"]
        top_anomalies = sorted(
            m.anomaly_indices,
            key=lambda i: abs(m.z_scores[i]) if i < len(m.z_scores) else 0, reverse=True
        )[:3]
        for i in top_anomalies:
            label = m.labels[i] if i < len(m.labels) else str(i)
            z = m.z_scores[i] if i < len(m.z_scores) else 0
            insights.append(f"「{label}」Z-Score={z:.2f}，显著偏离均值")

        return insights[:5]

    def build_conclusion(self, df, dimension, metric, algorithm, insights):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return ["无法得出异常分析结论"]

        anomaly_count = len(m.anomaly_indices)
        total = len(m.values)
        conclusions = [f"summary: {anomaly_count}/{total} 个异常值（{m.anomaly_method.upper()}）"]

        if anomaly_count > 0:
            conclusions.append(f"risk: 存在 {anomaly_count} 个异常点，可能包含数据质量问题或特殊业务场景")
            conclusions.append("recommendation: 核查异常点是否为数据录入错误，或识别特殊业务模式")
        else:
            conclusions.append("insight: 数据质量良好，未见显著异常")

        return conclusions



    def build_findings(self, df, dimension, metric, algorithm, kpis, chart_data):
        m = self._cache.get("metrics")
        f = self.factory
        findings = []
        if m is None:
            return [f.summary("异常分析完成")]
        anomaly_count = len(m.anomaly_indices)
        total = len(m.values)
        if anomaly_count == 0:
            findings.append(f.summary(f"未检测到显著异常值（{m.anomaly_method.upper()}方法）"))
        else:
            rate = (anomaly_count / total * 100) if total > 0 else 0
            findings.append(f.anomaly(
                title=f"检测到{anomaly_count}/{total}个异常值（{rate:.1f}%）",
                entity="全量", metric=metric, confidence=0.9,
                business_impact=f"可能存在数据质量问题或特殊业务场景"))
            top = sorted(m.anomaly_indices, key=lambda i: abs(m.z_scores[i]) if i < len(m.z_scores) else 0, reverse=True)[:2]
            for idx in top:
                label = m.labels[idx] if idx < len(m.labels) else str(idx); z = m.z_scores[idx] if idx < len(m.z_scores) else 0
                findings.append(f.anomaly(entity=label, title=f"「{label}」Z={z:.2f}，显著偏离均值", z_score=z))
        return findings

    def execute(self, df, dimension, metric, algorithm="zscore"):
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_category_columns(df)[0]
        self._cache = {}
        self._compute(df, dimension, metric, algorithm or "zscore")
        return super().execute(df, dimension, metric, algorithm)