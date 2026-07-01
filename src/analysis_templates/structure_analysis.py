"""结构分析模板"""
from src.analysis_templates.base import (AnalysisTemplate,TemplateSpec,AnalysisPackage,KPIItem,TableData,ChartData)

class StructureAnalysis(AnalysisTemplate):
    spec=TemplateSpec(analysis_type="structure_analysis",display_name="结构分析",
        REQUIRED_SCHEMA={"dimension_type":"category","metric_type":"numeric","min_dimension":1,"min_metric":1},
        MIN_ROWS=2,MIN_DISTINCT_VALUES=1,FALLBACK="proportion_analysis",
        OUTPUT_CHARTS=["pie","treemap"],OUTPUT_TABLES=["summary"],OUTPUT_KPIS=["top_pct","cat_count"])
    def execute(self,df,dimension,metric,algorithm=None):
        metric=metric or self._get_numeric_columns(df)[0]
        dimension=dimension or self.classifier.get_category_columns(df)[0]
        grouped=df.groupby(dimension)[metric].sum()
        total=grouped.sum()
        max_pct=grouped.max()/total*100 if total else 0
        kpis=[KPIItem(label="最大占比",value=f"{max_pct:.1f}%",change="",kpi_type="rate"),
              KPIItem(label="分类数",value=f"{len(grouped)}",change="",kpi_type="count")]
        table=TableData(title=f"{dimension}{metric}汇总",table_type="summary",
                        columns=[dimension,metric],rows=[[k,v] for k,v in grouped.items()])
        charts=[ChartData(slot="structure",chart_type="pie",title=f"{dimension}{metric}占比",x=dimension,y=metric)]
        return AnalysisPackage(id="",analysis_type="structure_analysis",business_question="",algorithm=algorithm,
                               dimension=dimension,metric=metric,kpis=kpis,tables=[table],charts=[],can_run=True,
                               data_profile=self._get_data_profile(df))
