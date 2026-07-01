"""排名分析模板"""
import pandas as pd
from src.analysis_templates.base import (
    AnalysisTemplate, TemplateSpec, AnalysisPackage, KPIItem, TableData, ChartData,
)

class RankingAnalysis(AnalysisTemplate):
    spec = TemplateSpec(
        analysis_type="ranking_analysis", display_name="排名分析",
        REQUIRED_SCHEMA={"dimension_type":"category","metric_type":"numeric","min_dimension":1,"min_metric":1},
        MIN_ROWS=2, MIN_DISTINCT_VALUES=2, FALLBACK="proportion_analysis",
        OUTPUT_CHARTS=["bar"], OUTPUT_TABLES=["ranking_table"],
        OUTPUT_KPIS=["top1","top3","top5"],
    )
    def execute(self, df, dimension, metric, algorithm=None):
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_category_columns(df)[0]
        grouped = df.groupby(dimension)[metric].sum().sort_values(ascending=False).head(10)
        total = grouped.sum()
        top1_val = grouped.iloc[0] if len(grouped)>0 else 0
        top3 = grouped.head(3).sum()/total*100 if total else 0
        top5 = grouped.head(5).sum()/total*100 if total else 0
        kpis = [KPIItem(label="TOP1 "+dimension, value=f"{top1_val:,.0f}", change="", kpi_type="sum"),
                 KPIItem(label="TOP3占比", value=f"{top3:.1f}%", change="", kpi_type="rate"),
                 KPIItem(label="TOP5占比", value=f"{top5:.1f}%", change="", kpi_type="rate")]
        table = TableData(title="排名明细", table_type="ranking",
                          columns=[dimension, metric], rows=[[k,v] for k,v in grouped.items()])
        charts = [ChartData(slot="ranking",chart_type="bar",title=f"TOP10 {dimension}",x=dimension,y=metric)]
        return AnalysisPackage(id="", analysis_type="ranking_analysis", business_question="", algorithm=algorithm,
                               dimension=dimension, metric=metric, kpis=kpis, tables=[table], charts=[], can_run=True,
                               data_profile=self._get_data_profile(df))
