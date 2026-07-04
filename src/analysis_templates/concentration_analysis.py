"""
集中度分析模板 —— 帕累托效应、HHI指数、基尼系数

V2：使用 TemplateMeta + TemplateRuntime，拆分 build_*() 方法
"""

import pandas as pd
import numpy as np
from src.analysis_templates.base import (
    AnalysisTemplate, TemplateMeta, TemplateRuntime,
    KPIItem, TableData, ChartData,
)


class ConcentrationAnalysis(AnalysisTemplate):
    meta = TemplateMeta(
        analysis_type="concentration_analysis",
        display_name="集中度分析",
        version="2.0",
        description="判断数据是否高度集中（帕累托效应/二八法则）",
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
        grouped = df.groupby(dimension)[metric].sum().reset_index()
        grouped = grouped.sort_values(metric, ascending=False)
        total = grouped[metric].sum()

        # 累计占比
        grouped["cumsum"] = grouped[metric].cumsum()
        grouped["cumshare"] = (grouped["cumsum"] / total * 100) if total > 0 else 0

        # HHI 指数
        if total > 0:
            shares = grouped[metric] / total
            hhi = (shares ** 2).sum() * 10000
        else:
            hhi = 0

        # Top20%贡献率
        top20_count = max(1, int(len(grouped) * 0.2))
        top20_share = grouped["share"].head(top20_count).sum() if total > 0 else 0
        # 顺便把 share 列算出来
        grouped["share"] = (grouped[metric] / total * 100) if total > 0 else 0

        self._cache["grouped"] = grouped
        self._cache["dimension"] = dimension
        self._cache["metric"] = metric
        self._cache["total"] = total
        self._cache["hhi"] = hhi
        self._cache["top20_share"] = top20_share
        self._cache["category_count"] = len(grouped)
        return grouped

    def build_kpis(self, df, dimension, metric, algorithm):
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_category_columns(df)[0]
        self._compute(df, dimension, metric)

        return [
            KPIItem(label="HHI指数", value=f"{self._cache['hhi']:.0f}", change="", kpi_type="rate"),
            KPIItem(label="Top20%贡献", value=f"{self._cache['top20_share']:.1f}%", change="", kpi_type="rate"),
            KPIItem(label="分类数量", value=str(self._cache["category_count"]), change="", kpi_type="count"),
        ]

    def build_tables(self, df, dimension, metric, algorithm):
        grouped = self._cache.get("grouped")
        if grouped is None:
            return []
        dimension = self._cache["dimension"]
        metric = self._cache["metric"]

        rows = [[str(row[dimension]), round(row[metric], 2), f"{row['share']:.1f}%", f"{row['cumshare']:.1f}%"]
                for _, row in grouped.iterrows()]
        return [TableData(
            title="集中度明细",
            table_type="ranking",
            columns=[str(dimension), metric, "占比(%)", "累计占比(%)"],
            rows=rows,
        )]

    def build_charts(self, df, dimension, metric, algorithm):
        grouped = self._cache.get("grouped")
        if grouped is None:
            return []
        dimension = self._cache["dimension"]
        metric = self._cache["metric"]

        return [ChartData(
            slot="concentration", chart_type="bar",
            title=f"{dimension}帕累托图", x=dimension, y=metric,
            data=grouped[[dimension, metric, "cumshare"]].to_dict('records'),
        )]

    def build_insights(self, df, dimension, metric, algorithm, kpis, chart_data):
        top20_share = self._cache.get("top20_share", 0)
        hhi = self._cache.get("hhi", 0)
        grouped = self._cache.get("grouped")

        if grouped is None:
            return []

        top1 = grouped.iloc[0]
        insights = [
            f"「{top1[dimension]}」占比{top1['share']:.1f}%，处于绝对领先地位",
        ]

        if hhi > 2500:
            insights.append(f"HHI 指数 {hhi:.0f} → 高度集中市场（>2500）")
        elif hhi > 1500:
            insights.append(f"HHI 指数 {hhi:.0f} → 中度集中市场")
        else:
            insights.append(f"HHI 指数 {hhi:.0f} → 分散市场")

        if top20_share > 80:
            insights.append(f"Top20% 分类贡献了 {top20_share:.1f}% → 符合二八法则")
        return insights

    def build_conclusion(self, df, dimension, metric, algorithm, insights):
        return insights[:1]

    def execute(self, df, dimension, metric, algorithm="pareto"):
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_category_columns(df)[0]
        self._cache = {}
        self._compute(df, dimension, metric)
        return super().execute(df, dimension, metric, algorithm)
