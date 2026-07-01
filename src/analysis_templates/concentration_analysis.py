"""集中度分析模板"""
from src.analysis_templates.base import (AnalysisTemplate,TemplateSpec,AnalysisPackage,KPIItem,TableData,ChartData)

class ConcentrationAnalysis(AnalysisTemplate):
    spec=TemplateSpec(analysis_type="concentration_analysis",display_name="集中度分析",
        REQUIRED_SCHEMA={"dimension_type":"category","metric_type":"numeric","min_dimension":1,"min_metric":1},
        MIN_ROWS=3,MIN_DISTINCT_VALUES=3,DEFAULT_ALGORITHM="pareto",FALLBACK="ranking_analysis",
        OUTPUT_CHARTS=["bar","line"],OUTPUT_TABLES=["pareto"],OUTPUT_KPIS=["top20","hhi"])
    def execute(self,df,dimension,metric,algorithm="pareto"):
        metric=metric or self._get_numeric_columns(df)[0]
        dimension=dimension or self.classifier.get_category_columns(df)[0]
        grouped=df.groupby(dimension)[metric].sum().sort_values(ascending=False)
        total=grouped.sum()
        cumsum=grouped.cumsum(); cum_pct=cumsum/total*100 if total else grouped*0
        top20_pct=cum_pct.iloc[min(round(len(grouped)*0.2),len(grouped)-1)] if len(grouped)>0 else 0
        hhi=((grouped/total)**2).sum()*10000 if total else 0
        kpis=[KPIItem(label="TOP20%贡献率",value=f"{top20_pct:.1f}%",change="",kpi_type="rate"),
              KPIItem(label="HHI指数",value=f"{hhi:.0f}",change="",kpi_type="sum")]
        rows=[[i,grouped.get(k,0),cum_pct.get(k,0)] for k in grouped.index]
        table=TableData(title="Pareto明细",table_type="ranking",columns=[dimension,metric,"累计占比%"],rows=rows)
        charts=[ChartData(slot="pareto_bar",chart_type="bar",title=f"{dimension}{metric}排序",x=dimension,y=metric),
                ChartData(slot="pareto_line",chart_type="line",title="累计贡献率",x=dimension,y="累计")]
        return AnalysisPackage(id="",analysis_type="concentration_analysis",business_question="",algorithm=algorithm,
                               dimension=dimension,metric=metric,kpis=kpis,tables=[table],charts=[],can_run=True,
                               data_profile=self._get_data_profile(df))
