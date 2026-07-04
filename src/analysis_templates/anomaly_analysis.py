"""
异常分析模板 —— 检测数据中的离群值和异常点

V2：使用 TemplateMeta + TemplateRuntime，拆分 build_*() 方法
"""

import pandas as pd
import numpy as np
from src.analysis_templates.base import (
    AnalysisTemplate, TemplateMeta, TemplateRuntime,
    KPIItem, TableData, ChartData,
)


class AnomalyAnalysis(AnalysisTemplate):
    meta = TemplateMeta(
        analysis_type="anomaly_analysis",
        display_name="异常分析",
        version="2.0",
        description="检测数据中的异常值、离群点和突变波动",
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

    def _compute(self, df, dimension, metric):
        grouped = df.groupby(dimension)[metric].sum().reset_index()
        values = grouped[metric]

        # Z-score
        mean_val = values.mean()
        std_val = values.std()
        if std_val > 0:
            grouped["z_score"] = (values - mean_val) / std_val
        else:
            grouped["z_score"] = 0

        # IQR
        q1 = values.quantile(0.25)
        q3 = values.quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        grouped["is_anomaly"] = (grouped["z_score"].abs() > 2) | \
                                 (values < lower) | (values > upper)

        anomaly_count = grouped["is_anomaly"].sum()
        anomaly_df = grouped[grouped["is_anomaly"]].copy()

        self._cache["grouped"] = grouped
        self._cache["anomaly_df"] = anomaly_df
        self._cache["dimension"] = dimension
        self._cache["metric"] = metric
        self._cache["anomaly_count"] = anomaly_count
        self._cache["total_count"] = len(grouped)
        self._cache["anomaly_rate"] = (anomaly_count / len(grouped) * 100) if len(grouped) > 0 else 0

    def build_kpis(self, df, dimension, metric, algorithm):
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_category_columns(df)[0]
        self._compute(df, dimension, metric)

        return [
            KPIItem(label="异常值数量", value=str(self._cache["anomaly_count"]), change="", kpi_type="count"),
            KPIItem(label="异常率", value=f"{self._cache['anomaly_rate']:.1f}%", change="", kpi_type="rate"),
        ]

    def build_tables(self, df, dimension, metric, algorithm):
        anomaly_df = self._cache.get("anomaly_df")
        grouped = self._cache.get("grouped")
        if anomaly_df is None or grouped is None:
            return []
        dimension = self._cache["dimension"]
        metric = self._cache["metric"]

        if len(anomaly_df) == 0:
            return [TableData(
                title="异常检测结果",
                table_type="detail",
                columns=["结果"],
                rows=[["未检测到异常值"]],
            )]

        rows = [[str(row[dimension]), round(row[metric], 2), round(row["z_score"], 2)]
                for _, row in anomaly_df.iterrows()]
        return [TableData(
            title="异常明细",
            table_type="exception",
            columns=[str(dimension), metric, "Z-score"],
            rows=rows,
        )]

    def build_charts(self, df, dimension, metric, algorithm):
        grouped = self._cache.get("grouped")
        if grouped is None:
            return []
        dimension = self._cache["dimension"]
        metric = self._cache["metric"]

        chart_data_list = grouped[[dimension, metric, "z_score"]].to_dict('records')
        return [ChartData(
            slot="anomaly", chart_type="scatter",
            title=f"{metric}异常检测", x=dimension, y=metric,
            data=chart_data_list,
        )]

    def build_insights(self, df, dimension, metric, algorithm, kpis, chart_data):
        anomaly_count = self._cache.get("anomaly_count", 0)
        anomaly_rate = self._cache.get("anomaly_rate", 0)
        anomaly_df = self._cache.get("anomaly_df")

        if anomaly_count == 0:
            return ["未检测到显著异常值，数据波动在正常范围内"]

        insights = [f"检测到 {anomaly_count} 个异常值（异常率 {anomaly_rate:.1f}%）"]

        if anomaly_df is not None and len(anomaly_df) > 0:
            dimension = self._cache["dimension"]
            metric = self._cache["metric"]
            top_anomaly = anomaly_df.sort_values("z_score", ascending=False).head(3)
            for _, row in top_anomaly.iterrows():
                direction = "偏高" if row["z_score"] > 0 else "偏低"
                insights.append(f"「{row[dimension]}」{direction}（z={row['z_score']:.2f}）")

        return insights

    def build_conclusion(self, df, dimension, metric, algorithm, insights):
        anomaly_count = self._cache.get("anomaly_count", 0)
        if anomaly_count == 0:
            return ["数据质量良好，未发现异常值"]
        return [f"发现{anomaly_count}个异常点，建议重点核查"]

    def execute(self, df, dimension, metric, algorithm="zscore"):
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_category_columns(df)[0]
        self._cache = {}
        self._compute(df, dimension, metric)
        return super().execute(df, dimension, metric, algorithm)
