"""相关分析模板"""
from src.analysis_templates.base import (AnalysisTemplate,TemplateSpec,AnalysisPackage,KPIItem,TableData,ChartData)

class CorrelationAnalysis(AnalysisTemplate):
    spec=TemplateSpec(analysis_type="correlation_analysis",display_name="相关分析",
        REQUIRED_SCHEMA={"dimension_type":"none","metric_type":"numeric","min_dimension":0,"min_metric":2},
        MIN_ROWS=5,DEFAULT_ALGORITHM="pearson",FALLBACK="ranking_analysis",
        OUTPUT_CHARTS=["scatter","heatmap"],OUTPUT_TABLES=["correlation_matrix"],
        OUTPUT_KPIS=["pearson","spearman","pvalue"])
    def execute(self,df,dimension,metric,algorithm="pearson"):
        numeric_cols=self._get_numeric_columns(df)
        dim=numeric_cols[0] if len(numeric_cols)>=2 else None
        met=numeric_cols[1] if len(numeric_cols)>=2 else (numeric_cols[0] if numeric_cols else None)
        corr_val=df[dim].corr(df[met]) if dim and met else 0
        pearson_val=df[numeric_cols].corr(method="pearson").iloc[0,1] if len(numeric_cols)>=2 else 0
        kpis=[KPIItem(label="Pearson r",value=f"{pearson_val:.3f}",change="",kpi_type="rate"),
              KPIItem(label="相关系数",value=f"{corr_val:.3f}",change="",kpi_type="rate")]
        table=TableData(title="相关系数矩阵",table_type="correlation",
                        columns=["列1","列2","相关系数"],rows=[[dim,met,round(corr_val,3)]])
        charts=[ChartData(slot="scatter",chart_type="scatter",title=f"{dim}vs{met}",x=dim,y=met)]
        return AnalysisPackage(id="",analysis_type="correlation_analysis",business_question="",algorithm=algorithm,
                               dimension=dim,metric=met,kpis=kpis,tables=[table],charts=[],can_run=True,
                               data_profile=self._get_data_profile(df))
