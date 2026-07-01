"""
增长分析模板 —— 趋势、增长率、同比、环比
"""
import pandas as pd
from src.analysis_templates.base import (
    AnalysisTemplate, TemplateSpec,
    AnalysisPackage, KPIItem, TableData, ChartData, ChartItem,
)


class GrowthAnalysis(AnalysisTemplate):
    spec = TemplateSpec(
        analysis_type="growth_analysis",
        display_name="增长分析",
        REQUIRED_SCHEMA={
            "dimension_type": "time",
            "metric_type": "numeric",
            "min_dimension": 1,
            "min_metric": 1,
        },
        MIN_ROWS=3,
        MIN_DISTINCT_VALUES=3,
        DEFAULT_ALGORITHM="yoy",
        FALLBACK="ranking_analysis",
        OUTPUT_CHARTS=["line", "bar", "area"],          # 3张：趋势/增长率/累计
        OUTPUT_TABLES=["growth_table", "cumsum_table"],  # 2张：增长率明细/累计值
        OUTPUT_KPIS=["total", "avg_growth", "max_month", "min_month"],
    )

    def execute(self, df: pd.DataFrame, dimension: str | None,
                metric: str | None, algorithm: str | None = "yoy") -> AnalysisPackage:
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_time_columns(df)[0]

        # 1. groupby + sum
        grouped = df.groupby(dimension)[metric].sum().reset_index()
        grouped = grouped.sort_values(dimension)

        # 2. 计算增长率
        grouped["growth_rate"] = grouped[metric].pct_change() * 100

        # 3. 计算累计值
        grouped["cumsum"] = grouped[metric].cumsum()

        # 4. KPIs
        total = grouped[metric].sum()
        avg_growth = grouped["growth_rate"].mean()
        max_idx = grouped[metric].idxmax()
        min_idx = grouped[metric].idxmin()
        kpis = [
            KPIItem(label=f"总{metric}", value=f"{total:,.0f}", change="", kpi_type="sum"),
            KPIItem(label="平均增长率", value=f"{avg_growth:.1f}%", change="", kpi_type="rate"),
            KPIItem(label="最大增长月", value=str(grouped.loc[max_idx, dimension]), change="", kpi_type="sum"),
            KPIItem(label="最低增长月", value=str(grouped.loc[min_idx, dimension]), change="", kpi_type="sum"),
        ]

        # 5. 生成表格
        table = TableData(
            title="增长率明细",
            table_type="growth",
            columns=[str(dimension), metric, "增长率(%)", "累计值"],
            rows=grouped.values.tolist(),
        )

        # 6. 生成 ChartData
        chart_data_list = [
            ChartData(slot="trend",      chart_type="line",
                      title=f"{metric}趋势", x=dimension, y=metric),
            ChartData(slot="growth_rate", chart_type="bar",
                      title="增长率变化", x=dimension, y="growth_rate"),
            ChartData(slot="cumulative",  chart_type="area",
                      title="累计趋势", x=dimension, y="cumsum"),
        ]

        # 7. 生成 insights
        insights = [
            f"{metric}整体呈{'上升' if avg_growth > 0 else '下降'}趋势",
            f"{grouped.loc[max_idx, dimension]}增速最高",
        ]

        return AnalysisPackage(
            id="",
            analysis_type="growth_analysis",
            business_question="",
            algorithm=algorithm,
            dimension=dimension,
            metric=metric,
            kpis=kpis,
            tables=[table],
            charts=[],  # 由 ChartRenderer 填充
            insights=insights,
            conclusions=[],
            can_run=True,
            data_profile=self._get_data_profile(df),
        )
