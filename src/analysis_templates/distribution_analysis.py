"""
分布分析模板 —— 数值的分布形态与频次统计

V2：使用 TemplateMeta + TemplateRuntime，拆分 build_*() 方法
"""

import pandas as pd
import numpy as np
from src.analysis_templates.base import (
    AnalysisTemplate, TemplateMeta, TemplateRuntime,
    KPIItem, TableData, ChartData,
)


class DistributionAnalysis(AnalysisTemplate):
    meta = TemplateMeta(
        analysis_type="distribution_analysis",
        display_name="分布分析",
        version="2.0",
        description="分析数值数据的分布形态（偏态、峰度、区间分布）",
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

    def _compute(self, df, metric):
        series = df[metric].dropna()
        mean_val = series.mean()
        median_val = series.median()
        std_val = self._safe_agg(series, "std", 0)
        skew_val = self._safe_agg(series, "skew", 0)
        kurt_val = self._safe_agg(series, "kurt", 0)

        # 区间分布（分箱为10个区间）
        bins = np.histogram_bin_edges(series, bins=10)
        hist, edges = np.histogram(series, bins=bins)

        self._cache["series"] = series
        self._cache["metric"] = metric
        self._cache["mean"] = mean_val
        self._cache["median"] = median_val
        self._cache["std"] = std_val
        self._cache["skew"] = skew_val
        self._cache["kurt"] = kurt_val
        self._cache["hist"] = hist
        self._cache["edges"] = edges
        self._cache["min_val"] = series.min()
        self._cache["max_val"] = series.max()
        self._cache["count"] = len(series)

    def build_kpis(self, df, dimension, metric, algorithm):
        metric = metric or self._get_numeric_columns(df)[0]
        self._compute(df, metric)

        return [
            KPIItem(label="均值", value=f"{self._cache['mean']:,.2f}", change="", kpi_type="avg"),
            KPIItem(label="中位数", value=f"{self._cache['median']:,.2f}", change="", kpi_type="avg"),
            KPIItem(label="标准差", value=f"{self._cache['std']:,.2f}", change="", kpi_type="rate"),
            KPIItem(label="偏度", value=f"{self._cache['skew']:.2f}" if self._cache['skew'] else "0", change="", kpi_type="rate"),
        ]

    def build_tables(self, df, dimension, metric, algorithm):
        edges = self._cache.get("edges")
        hist = self._cache.get("hist")
        if edges is None:
            return []

        rows = [[f"{edges[i]:.1f} - {edges[i+1]:.1f}", int(hist[i])] for i in range(len(hist))]
        return [TableData(
            title=f"{self._cache['metric']}区间分布",
            table_type="summary",
            columns=["区间", "频次"],
            rows=rows,
        )]

    def build_charts(self, df, dimension, metric, algorithm):
        series = self._cache.get("series")
        if series is None:
            return []
        metric = self._cache["metric"]

        # histogram 用 x=metric, y="" 表示单变量直方图
        hist_data = self._cache["hist"]
        edges = self._cache["edges"]
        chart_data = []
        for i in range(len(hist_data)):
            chart_data.append({
                "x": f"{edges[i]:.1f}-{edges[i+1]:.1f}",
                "y": int(hist_data[i]),
            })

        return [ChartData(
            slot="distribution", chart_type="histogram",
            title=f"{metric}分布直方图", x=metric, y="频次",
            data=chart_data,
        )]

    def build_insights(self, df, dimension, metric, algorithm, kpis, chart_data):
        mean_val = self._cache.get("mean", 0)
        median_val = self._cache.get("median", 0)
        skew_val = self._cache.get("skew", 0) or 0
        std_val = self._cache.get("std", 0) or 0
        metric = self._cache.get("metric", "")

        insights = [f"{metric}均值为{mean_val:,.2f}，标准差{std_val:,.2f}"]

        if abs(skew_val) > 1:
            direction = "右偏" if skew_val > 0 else "左偏"
            insights.append(f"数据呈{direction}分布（偏度={skew_val:.2f}），存在较长的{direction}尾部")
        else:
            insights.append("数据分布接近对称")

        if mean_val > median_val * 1.1 and median_val > 0:
            insights.append("均值显著高于中位数，说明少数高值拉高了整体水平")
        return insights

    def build_conclusion(self, df, dimension, metric, algorithm, insights):
        return insights[:1]

    def execute(self, df, dimension, metric, algorithm=None):
        metric = metric or self._get_numeric_columns(df)[0]
        self._cache = {}
        self._compute(df, metric)
        return super().execute(df, dimension, metric, algorithm)
