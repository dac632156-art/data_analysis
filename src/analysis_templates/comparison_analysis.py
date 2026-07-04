"""
对比分析模板 —— 两个或多个分类组之间的差异对比（L3 业务分析）

V2 新增：分组均值/总和对比，计算差异率和优胜组
"""

import pandas as pd
import numpy as np
from src.analysis_templates.base import (
    AnalysisTemplate, TemplateMeta, TemplateRuntime,
    KPIItem, TableData, ChartData,
)


class ComparisonAnalysis(AnalysisTemplate):
    meta = TemplateMeta(
        analysis_type="comparison_analysis",
        display_name="对比分析",
        version="1.0",
        description="对比两个或多个分类组之间的指标差异，识别优劣和差异程度",
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
        # 分组汇总
        grouped = df.groupby(dimension)[metric].agg(["sum", "mean", "count", "std"]).reset_index()
        grouped.columns = [dimension, "总和", "均值", "样本数", "标准差"]
        grouped = grouped.sort_values("均值", ascending=False)

        total_mean = grouped["均值"].mean()
        total_sum = grouped["总和"].sum()

        # 计算各组 vs 全局均值的差异
        grouped["vs全局均值"] = grouped["均值"] - total_mean
        grouped["差异率(%)"] = ((grouped["均值"] / total_mean - 1) * 100) if total_mean > 0 else 0

        # 最优组和最差组
        if len(grouped) >= 2:
            winner = grouped.iloc[0]
            loser = grouped.iloc[-1]
            max_gap_pct = ((winner["均值"] / loser["均值"] - 1) * 100) if loser["均值"] > 0 else 0
        else:
            winner = loser = None
            max_gap_pct = 0

        self._cache["grouped"] = grouped
        self._cache["dimension"] = dimension
        self._cache["metric"] = metric
        self._cache["total_mean"] = total_mean
        self._cache["total_sum"] = total_sum
        self._cache["winner"] = winner
        self._cache["loser"] = loser
        self._cache["max_gap_pct"] = max_gap_pct
        self._cache["group_count"] = len(grouped)

    def build_kpis(self, df, dimension, metric, algorithm):
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_category_columns(df)[0]
        self._compute(df, dimension, metric)

        winner = self._cache.get("winner")
        loser = self._cache.get("loser")
        max_gap_pct = self._cache.get("max_gap_pct", 0)
        total_mean = self._cache.get("total_mean", 0)

        kpis = [
            KPIItem(label="全局均值", value=f"{total_mean:,.2f}", change="", kpi_type="avg"),
        ]
        if winner is not None:
            kpis.append(KPIItem(
                label=f"最优组: {winner[dimension]}",
                value=f"{winner['均值']:,.2f}",
                change=f"+{winner['差异率(%)']:.1f}%" if winner['差异率(%)'] > 0 else f"{winner['差异率(%)']:.1f}%",
                kpi_type="avg",
            ))
        if max_gap_pct > 0:
            kpis.append(KPIItem(
                label="组间最大差异",
                value=f"{max_gap_pct:.1f}%",
                change="",
                kpi_type="rate",
            ))
        return kpis

    def build_tables(self, df, dimension, metric, algorithm):
        grouped = self._cache.get("grouped")
        if grouped is None:
            return []
        dimension = self._cache["dimension"]
        metric = self._cache["metric"]

        # 对比明细表
        rows = []
        for _, row in grouped.iterrows():
            diff_str = f"+{row['差异率(%)']:.1f}%" if row['差异率(%)'] > 0 else f"{row['差异率(%)']:.1f}%"
            rows.append([
                str(row[dimension]),
                round(row["总和"], 2),
                round(row["均值"], 2),
                int(row["样本数"]),
                diff_str,
            ])

        return [TableData(
            title=f"{dimension}对比明细",
            table_type="ranking",
            columns=[str(dimension), f"{metric}总和", f"{metric}均值", "样本数", "vs全局差异"],
            rows=rows,
        )]

    def build_charts(self, df, dimension, metric, algorithm):
        grouped = self._cache.get("grouped")
        if grouped is None:
            return []
        dimension = self._cache["dimension"]
        metric = self._cache["metric"]

        chart_data = []
        for _, row in grouped.iterrows():
            chart_data.append({
                "x": str(row[dimension]),
                "y": round(row["均值"], 2),
            })

        return [ChartData(
            slot="comparison_bar", chart_type="bar",
            title=f"{dimension}{metric}均值对比",
            x=dimension, y=f"{metric}均值",
            data=chart_data,
        )]

    def build_insights(self, df, dimension, metric, algorithm, kpis, chart_data):
        winner = self._cache.get("winner")
        loser = self._cache.get("loser")
        max_gap_pct = self._cache.get("max_gap_pct", 0)
        group_count = self._cache.get("group_count", 0)
        dimension = self._cache.get("dimension", "")
        metric = self._cache.get("metric", "")

        if winner is None:
            return ["数据不足以进行对比分析"]

        insights = [
            f"「{winner[dimension]}」的{metric}均值最高（{winner['均值']:,.2f}），"
            f"较全局均值高出{winner['差异率(%)']:.1f}%",
        ]

        if loser is not None and loser[dimension] != winner[dimension]:
            insights.append(
                f"「{loser[dimension]}」表现最弱（{loser['均值']:,.2f}），"
                f"仅为「{winner[dimension]}」的{100 - max_gap_pct:.1f}%"
            )

        if max_gap_pct > 50:
            insights.append(f"组间差异较大（>{max_gap_pct:.0f}%），数据分布不均衡，需关注弱势组")
        else:
            insights.append(f"各组{metric}差异在{max_gap_pct:.1f}%以内，整体分布较均匀")

        return insights

    def build_conclusion(self, df, dimension, metric, algorithm, insights):
        winner = self._cache.get("winner")
        if winner is None:
            return ["无法得出有效对比结论"]
        dimension = self._cache["dimension"]
        return [f"「{winner[dimension]}」在{self._cache['metric']}指标上表现最优，建议作为标杆推广其经验"]

    def execute(self, df, dimension, metric, algorithm=None):
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_category_columns(df)[0]
        self._cache = {}
        self._compute(df, dimension, metric)
        return super().execute(df, dimension, metric, algorithm)
