"""分布分析模板"""
from src.analysis_templates.base import (AnalysisTemplate,TemplateSpec,AnalysisPackage,KPIItem,TableData,ChartData)

class DistributionAnalysis(AnalysisTemplate):
    spec=TemplateSpec(analysis_type="distribution_analysis",display_name="分布分析",
        REQUIRED_SCHEMA={"dimension_type":"none","metric_type":"numeric","min_dimension":0,"min_metric":1},
        MIN_ROWS=10,FALLBACK="proportion_analysis",
        OUTPUT_CHARTS=["histogram","box"],OUTPUT_TABLES=["bins"],
        OUTPUT_KPIS=["mean","median","std","skew"])
    def execute(self,df,dimension,metric,algorithm=None):
        metric=metric or self._get_numeric_columns(df)[0]
        series=df[metric].dropna()
        mean_val=series.mean(); mid=series.median(); std=series.std()
        skew_val=series.skew()
        kpis=[KPIItem(label="均值",value=f"{mean_val:,.2f}",change="",kpi_type="avg"),
              KPIItem(label="中位数",value=f"{mid:,.2f}",change="",kpi_type="avg"),
              KPIItem(label="标准差",value=f"{std:,.2f}",change="",kpi_type="avg"),
              KPIItem(label="偏度",value=f"{skew_val:.2f}",change="",kpi_type="rate")]
        bins=pd.cut(series,bins=min(10,len(series)//5)).value_counts().sort_index()
        table=TableData(title="分箱统计",table_type="detail",
                        columns=["区间","频次"],rows=[[str(k),v] for k,v in bins.items()])
        charts=[ChartData(slot="dist",chart_type="histogram",title=f"{metric}分布",x=metric,y="")]
        return AnalysisPackage(id="",analysis_type="distribution_analysis",business_question="",algorithm=algorithm,
                               dimension=None,metric=metric,kpis=kpis,tables=[table],charts=[],can_run=True,
                               data_profile=self._get_data_profile(df))
