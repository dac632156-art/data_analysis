"""异常分析模板"""
from src.analysis_templates.base import (AnalysisTemplate,TemplateSpec,AnalysisPackage,KPIItem,TableData,ChartData)
import numpy as np

class AnomalyAnalysis(AnalysisTemplate):
    spec=TemplateSpec(analysis_type="anomaly_analysis",display_name="异常分析",
        REQUIRED_SCHEMA={"dimension_type":"optional","metric_type":"numeric","min_dimension":0,"min_metric":1},
        MIN_ROWS=10,DEFAULT_ALGORITHM="zscore",FALLBACK="distribution_analysis",
        OUTPUT_CHARTS=["box","scatter"],OUTPUT_TABLES=["anomaly_detail"],
        OUTPUT_KPIS=["anomaly_count","anomaly_rate"])
    def execute(self,df,dimension,metric,algorithm="zscore"):
        metric=metric or self._get_numeric_columns(df)[0]
        series=df[metric].dropna(); z=(series-series.mean())/series.std()
        anomalies=series[abs(z)>2.5]
        rate=len(anomalies)/len(series)*100
        kpis=[KPIItem(label="异常数",value=f"{len(anomalies)}",change="",kpi_type="count"),
              KPIItem(label="异常率",value=f"{rate:.2f}%",change="",kpi_type="rate")]
        idxs=list(anomalies.index[:10])
        rows=[[i,df.loc[i,metric] if i in df.index else 0] for i in idxs]
        table=TableData(title="异常值明细",table_type="exception",
                        columns=["索引",metric],rows=rows)
        charts=[ChartData(slot="box",chart_type="box",title=f"{metric}箱线图",x=metric,y="")]
        return AnalysisPackage(id="",analysis_type="anomaly_analysis",business_question="",algorithm=algorithm,
                               dimension=None,metric=metric,kpis=kpis,tables=[table],charts=[],can_run=True,
                               data_profile=self._get_data_profile(df))
