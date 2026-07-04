"""
相关分析模板 —— 数值指标间的关联关系

V2：使用 TemplateMeta + TemplateRuntime，拆分 build_*() 方法
"""

import pandas as pd
import numpy as np
from src.analysis_templates.base import (
    AnalysisTemplate, TemplateMeta, TemplateRuntime,
    KPIItem, TableData, ChartData,
)


class CorrelationAnalysis(AnalysisTemplate):
    meta = TemplateMeta(
        analysis_type="correlation_analysis",
        display_name="相关分析",
        version="2.0",
        description="分析两个数值指标之间的关联关系强度",
        supported_algorithms=["pearson", "spearman"],
    )

    runtime = TemplateRuntime(
        REQUIRED_SCHEMA={
            "dimension_type": "",
            "metric_type": "numeric",
            "min_dimension": 0,
            "min_metric": 2,
        },
        MIN_ROWS=3,
        FALLBACK="ranking_analysis",
    )

    _cache: dict = {}

    def _compute(self, df, dimension, metric):
        numeric_cols = self._get_numeric_columns(df)
        if len(numeric_cols) < 2:
            self._cache["error"] = "至少需要2个数值列"
            return

        col1 = dimension or numeric_cols[0]
        col2 = metric or numeric_cols[1]

        if col1 not in df.columns or col2 not in df.columns:
            self._cache["error"] = f"列不存在: {col1}, {col2}"
            return

        clean = df[[col1, col2]].dropna()
        if len(clean) < 3:
            self._cache["error"] = "有效数据行不足"
            return

        corr = clean[col1].corr(clean[col2])
        # 相关性矩阵
        corr_matrix = df[numeric_cols].corr()

        self._cache["col1"] = col1
        self._cache["col2"] = col2
        self._cache["corr"] = corr
        self._cache["clean"] = clean
        self._cache["corr_matrix"] = corr_matrix
        self._cache["sample_size"] = len(clean)

    def build_kpis(self, df, dimension, metric, algorithm):
        numeric_cols = self._get_numeric_columns(df)
        col1 = dimension or numeric_cols[0]
        col2 = metric or (numeric_cols[1] if len(numeric_cols) > 1 else None)
        self._compute(df, col1, col2)

        corr = self._cache.get("corr")
        if corr is None:
            return [KPIItem(label="无法计算", value="N/A", change="", kpi_type="rate")]

        return [
            KPIItem(label=f"{self._cache['col1']} vs {self._cache['col2']}",
                    value=f"r={corr:.3f}", change="", kpi_type="rate"),
            KPIItem(label="样本量", value=str(self._cache["sample_size"]), change="", kpi_type="count"),
        ]

    def build_tables(self, df, dimension, metric, algorithm):
        corr_matrix = self._cache.get("corr_matrix")
        if corr_matrix is None:
            return []

        # 将矩阵转为行列格式
        cols = list(corr_matrix.columns)
        rows = []
        for i, row_name in enumerate(corr_matrix.index):
            row_data = [row_name]
            for col_name in cols:
                row_data.append(round(corr_matrix.loc[row_name, col_name], 3))
            rows.append(row_data)

        return [TableData(
            title="相关系数矩阵",
            table_type="correlation",
            columns=["指标"] + [str(c) for c in cols],
            rows=rows,
        )]

    def build_charts(self, df, dimension, metric, algorithm):
        clean = self._cache.get("clean")
        col1 = self._cache.get("col1")
        col2 = self._cache.get("col2")
        if clean is None:
            return []

        return [ChartData(
            slot="correlation", chart_type="scatter",
            title=f"{col1} vs {col2}", x=col1, y=col2,
            data=clean[[col1, col2]].to_dict('records'),
        )]

    def build_insights(self, df, dimension, metric, algorithm, kpis, chart_data):
        corr = self._cache.get("corr")
        col1 = self._cache.get("col1", "")
        col2 = self._cache.get("col2", "")
        if corr is None:
            return ["无法计算相关系数"]

        abs_corr = abs(corr)
        if abs_corr > 0.7:
            strength = "强" if abs_corr > 0.9 else "较强"
        elif abs_corr > 0.4:
            strength = "中等"
        elif abs_corr > 0.2:
            strength = "弱"
        else:
            strength = "极弱"

        direction = "正" if corr > 0 else "负"
        return [
            f"「{col1}」与「{col2}」呈{direction}相关（r={corr:.3f}），相关强度为「{strength}」",
            f"样本量 {self._cache.get('sample_size', 0)} 条有效记录",
        ]

    def build_conclusion(self, df, dimension, metric, algorithm, insights):
        return insights[:1]

    def execute(self, df, dimension, metric, algorithm="pearson"):
        numeric_cols = self._get_numeric_columns(df)
        col1 = dimension or numeric_cols[0] if len(numeric_cols) > 0 else None
        col2 = metric or (numeric_cols[1] if len(numeric_cols) > 1 else None)
        self._cache = {}
        self._compute(df, col1, col2)
        return super().execute(df, dimension, metric, algorithm)
