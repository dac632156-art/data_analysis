"""
占比分析模板 —— 各部分在整体中的百分比份额

V2：使用 TemplateMeta + TemplateRuntime，拆分 build_*() 方法
"""

import pandas as pd
from src.analysis_templates.base import (
    AnalysisTemplate, TemplateMeta, TemplateRuntime,
    KPIItem, TableData, ChartData,
)


class ProportionAnalysis(AnalysisTemplate):
    meta = TemplateMeta(
        analysis_type="proportion_analysis",
        display_name="占比分析",
        version="2.0",
        description="计算各部分在整体中的百分比份额",
    )

    runtime = TemplateRuntime(
        REQUIRED_SCHEMA={
            "dimension_type": "category",
            "metric_type": "numeric",
            "min_dimension": 1,
            "min_metric": 1,
        },
        MIN_ROWS=2,
        FALLBACK="structure_analysis",
    )

    _cache: dict = {}

    def _compute(self, df, dimension, metric):
        grouped = df.groupby(dimension)[metric].sum().reset_index()
        total = grouped[metric].sum()
        grouped["share"] = (grouped[metric] / total * 100) if total > 0 else 0
        grouped = grouped.sort_values("share", ascending=False)

        self._cache["grouped"] = grouped
        self._cache["dimension"] = dimension
        self._cache["metric"] = metric
        self._cache["total"] = total
        self._cache["top3_share"] = grouped["share"].head(3).sum()
        return grouped

    def build_kpis(self, df, dimension, metric, algorithm):
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_category_columns(df)[0]
        self._compute(df, dimension, metric)

        total = self._cache["total"]
        top3_share = self._cache["top3_share"]

        return [
            KPIItem(label=f"总{metric}", value=f"{total:,.0f}", change="", kpi_type="sum"),
            KPIItem(label="Top3合计占比", value=f"{top3_share:.1f}%", change="", kpi_type="rate"),
        ]

    def build_tables(self, df, dimension, metric, algorithm):
        grouped = self._cache.get("grouped")
        if grouped is None:
            return []
        dimension = self._cache["dimension"]
        metric = self._cache["metric"]

        rows = [[str(row[dimension]), round(row[metric], 2), f"{row['share']:.1f}%"]
                for _, row in grouped.iterrows()]
        return [TableData(
            title=f"{dimension}占比明细",
            table_type="summary",
            columns=[str(dimension), metric, "占比(%)"],
            rows=rows,
        )]

    def build_charts(self, df, dimension, metric, algorithm):
        grouped = self._cache.get("grouped")
        if grouped is None:
            return []
        dimension = self._cache["dimension"]
        metric = self._cache["metric"]

        return [ChartData(
            slot="proportion", chart_type="pie",
            title=f"{dimension}{metric}占比", x=dimension, y=metric,
            data=grouped[[dimension, metric]].to_dict('records'),
        )]

    def build_insights(self, df, dimension, metric, algorithm, kpis, chart_data):
        grouped = self._cache.get("grouped")
        if grouped is None:
            return []
        top3_share = self._cache.get("top3_share", 0)
        dimension = self._cache["dimension"]

        top1 = grouped.iloc[0]
        insights = [
            f"「{top1[dimension]}」占比最高，达{top1['share']:.1f}%",
        ]
        if top3_share > 80:
            insights.append(f"Top3分类合计占比{top3_share:.1f}%，集中度较高")
        return insights

    def build_conclusion(self, df, dimension, metric, algorithm, insights):
        return insights[:1]

    def execute(self, df, dimension, metric, algorithm=None):
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_category_columns(df)[0]
        self._cache = {}
        self._compute(df, dimension, metric)
        return super().execute(df, dimension, metric, algorithm)
