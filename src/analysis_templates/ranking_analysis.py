"""
排名分析模板 —— Top/Bottom N 对比排名

V2：使用 TemplateMeta + TemplateRuntime，拆分 build_*() 方法
"""

import pandas as pd
from src.analysis_templates.base import (
    AnalysisTemplate, TemplateMeta, TemplateRuntime,
    KPIItem, TableData, ChartData,
)


class RankingAnalysis(AnalysisTemplate):
    meta = TemplateMeta(
        analysis_type="ranking_analysis",
        display_name="排名分析",
        version="2.0",
        description="按维度对比排名，识别表现最好和最差的分类",
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

    def _compute(self, df, dimension, metric):
        grouped = df.groupby(dimension)[metric].sum().reset_index()
        grouped_sorted = grouped.sort_values(metric, ascending=False)
        top_n = min(10, len(grouped_sorted))
        self._cache["grouped_full"] = grouped_sorted
        self._cache["grouped"] = grouped_sorted.head(top_n)
        self._cache["dimension"] = dimension
        self._cache["metric"] = metric
        self._cache["total"] = grouped[metric].sum()
        # Top3 集中度
        top3_sum = grouped_sorted[metric].head(3).sum()
        self._cache["top3_share"] = (top3_sum / self._cache["total"] * 100) if self._cache["total"] > 0 else 0
        return grouped_sorted

    def build_kpis(self, df, dimension, metric, algorithm):
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_category_columns(df)[0]
        self._compute(df, dimension, metric)

        grouped = self._cache["grouped"]
        if len(grouped) == 0:
            return [KPIItem(label="无数据", value="0", change="", kpi_type="sum")]

        top1_val = grouped.iloc[0][metric]
        top1_name = grouped.iloc[0][dimension]
        top3_share = self._cache["top3_share"]

        return [
            KPIItem(label=f"Top1: {top1_name}", value=f"{top1_val:,.2f}", change="", kpi_type="sum"),
            KPIItem(label="Top3集中度", value=f"{top3_share:.1f}%", change="", kpi_type="rate"),
        ]

    def build_tables(self, df, dimension, metric, algorithm):
        grouped = self._cache.get("grouped")
        if grouped is None:
            return []
        dimension = self._cache["dimension"]
        metric = self._cache["metric"]

        rows = [[str(row[dimension]), round(row[metric], 2)] for _, row in grouped.iterrows()]
        return [TableData(
            title=f"{dimension}排名",
            table_type="ranking",
            columns=[str(dimension), metric],
            rows=rows,
        )]

    def build_charts(self, df, dimension, metric, algorithm):
        grouped = self._cache.get("grouped")
        if grouped is None:
            return []
        dimension = self._cache["dimension"]
        metric = self._cache["metric"]

        return [ChartData(
            slot="ranking", chart_type="bar",
            title=f"{dimension}排名", x=dimension, y=metric,
            data=grouped[[dimension, metric]].to_dict('records'),
        )]

    def build_insights(self, df, dimension, metric, algorithm, kpis, chart_data):
        grouped = self._cache.get("grouped_full")
        if grouped is None:
            return []
        dimension = self._cache["dimension"]
        metric = self._cache["metric"]
        top3_share = self._cache["top3_share"]

        top1 = grouped.iloc[0]
        bottom1 = grouped.iloc[-1]
        return [
            f"「{top1[dimension]}」的{metric}最高，达到{top1[metric]:,.2f}",
            f"「{bottom1[dimension]}」的{metric}最低，仅{bottom1[metric]:,.2f}",
            f"Top3 分类占据了{top3_share:.1f}%的{metric}",
        ]

    def build_conclusion(self, df, dimension, metric, algorithm, insights):
        return insights[:1]

    def execute(self, df, dimension, metric, algorithm=None):
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_category_columns(df)[0]
        self._cache = {}
        self._compute(df, dimension, metric)
        return super().execute(df, dimension, metric, algorithm)
