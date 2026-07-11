"""
复购分析模板 —— 客户重复购买行为分析

V3：全面升级为 Business Template，所有业务计算委托 RetentionCalculator
支持三种模式：原始数据复购率 / 预计算复购率 / 客户数量分布
"""

from src.analysis_templates.base import (
    AnalysisTemplate, TemplateMeta, TemplateRuntime,
    KPIItem, TableData, ChartData,
)
from src.calculators import RetentionCalculator, BusinessMetrics
from src.domain import Direction, Severity, FindingCategory


class RetentionAnalysis(AnalysisTemplate):
    meta = TemplateMeta(
        analysis_type="retention_analysis",
        display_name="复购分析",
        version="3.0",
        description="分析客户复购率 / 复购客户数 / 平均购买频次",
    )

    runtime = TemplateRuntime(
        REQUIRED_SCHEMA={
            "dimension_type": "category",
            "metric_type": "numeric",
            "min_dimension": 1,
            "min_metric": 1,
        },
        MIN_ROWS=3,
        DERIVED_REQUIREMENTS={},
        FALLBACK="ranking_analysis",
    )

    _cache: dict = {}

    def can_run(self, df) -> bool:
        if not self._has_category_column(df):
            return False
        if len(self._get_numeric_columns(df)) < 1:
            return False
        if len(df) < self.runtime.MIN_ROWS:
            return False

        cols = [str(c).lower() for c in df.columns]
        for c in cols:
            for kw in ["客户", "customer", "复购", "retention", "回购", "repeat"]:
                if kw in c:
                    return True
        return False

    # ===== 核心计算 =====

    def _compute(self, df, dimension=None, metric=None):
        """V3：委托 RetentionCalculator，自动识别客户ID列和订单列"""
        m: BusinessMetrics = RetentionCalculator.execute(df)
        self._cache["metrics"] = m
        self._cache["dimension"] = dimension or m.dimension
        self._cache["metric"] = metric or m.metric
        return m
        self._cache["_calculator_used"] = "RetentionCalculator"

    # ===== KPI =====

    def build_kpis(self, df, dimension, metric, algorithm):
        m = self._compute(df, dimension, metric)

        rate = m.repeat_purchase_rate
        rate_str = f"{rate*100:.1f}%" if rate is not None else "N/A"

        kpis = [
            KPIItem(label="复购率", value=rate_str, change="", kpi_type="rate"),
            KPIItem(label="复购客户数", value=str(m.repeat_customer_count or 0),
                    change="", kpi_type="count"),
            KPIItem(label="总客户数", value=str(m.total_customer_count or 0),
                    change="", kpi_type="count"),
        ]

        if m.avg_purchase_frequency is not None:
            kpis.append(KPIItem(label="人均购买次数",
                                value=f"{m.avg_purchase_frequency:.1f}",
                                change="", kpi_type="avg"))

        return kpis

    # ===== Table =====

    def build_tables(self, df, dimension, metric, algorithm):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None or not m.values:
            return []

        # 购买频次分布
        from collections import Counter
        freq_counter = Counter([int(v) for v in m.values])
        rows = [[f"{cnt}次", freq_counter.get(cnt, 0)]
                for cnt in sorted(freq_counter.keys())]

        return [TableData(
            title="购买频次分布",
            table_type="summary",
            columns=["购买次数", "客户数"],
            rows=rows,
        )]

    # ===== Chart =====

    def build_charts(self, df, dimension, metric, algorithm):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None or not m.values:
            return []

        from collections import Counter
        freq_counter = Counter([int(v) for v in m.values])
        freq_data = [{"x": f"{cnt}次", "y": count}
                     for cnt, count in sorted(freq_counter.items())]

        # 复购 vs 单次
        repeat = m.repeat_customer_count or 0
        one_time = (m.total_customer_count or 0) - repeat
        pie_data = [{"x": "复购客户", "y": repeat},
                    {"x": "单次客户", "y": max(0, one_time)}]

        return [
            ChartData(slot="frequency_bar", chart_type="bar",
                      title="购买频次分布", x="购买次数", y="客户数", data=freq_data),
            ChartData(slot="retention_pie", chart_type="pie",
                      title="复购客户占比", x="客户类型", y="客户数", data=pie_data),
        ]

    # ===== Insight =====

    def build_insights(self, df, dimension, metric, algorithm, kpis, chart_data):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return ["数据不足，无法进行复购分析"]

        rate = m.repeat_purchase_rate
        rate_pct = f"{rate*100:.1f}%" if rate is not None else "N/A"
        insights = [f"客户复购率为 {rate_pct}，复购客户数 {m.repeat_customer_count or 0}"]

        if rate is not None:
            if rate < 0.2:
                insights.append("复购率偏低（<20%），客户黏性不足，需加强召回策略")
            elif rate > 0.5:
                insights.append("复购率较高（>50%），客户忠诚度高，可探索会员体系")
            else:
                insights.append("复购率处于中等水平（20%-50%），仍有提升空间")

        if m.avg_purchase_frequency is not None:
            insights.append(f"人均购买 {m.avg_purchase_frequency:.1f} 次")

        return insights

    # ===== Conclusion =====

    def build_conclusion(self, df, dimension, metric, algorithm, insights):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return ["无法得出有效复购结论"]

        rate = m.repeat_purchase_rate
        conclusions = []
        if rate is not None:
            conclusions.append(f"summary: 复购率 {rate*100:.1f}%，{m.repeat_customer_count}/{m.total_customer_count} 客户有复购行为")

        if rate is not None and rate < 0.3:
            conclusions.append("risk: 复购率偏低，客户流失风险较高")
            conclusions.append("recommendation: 建立客户分层体系，对低复购客户推送定向优惠")
        elif rate is not None:
            conclusions.append("opportunity: 复购基础良好，可深化高复购客户价值挖掘")
            conclusions.append("recommendation: 建立VIP等级体系，激励高频客户带来更多转介绍")

        return conclusions



    def build_findings(self, df, dimension, metric, algorithm, kpis, chart_data):
        m = self._cache.get("metrics")
        f = self.factory
        findings = []
        if m is None:
            return [f.summary("复购分析完成")]
        rate = m.repeat_purchase_rate
        rate_pct = f"{rate*100:.1f}%" if rate is not None else "N/A"
        ba = m.business_assessment or {}
        loyalty_rate = ba.get("loyalty_rate")
        repeat_value_share = ba.get("repeat_value_share")
        quality = ba.get("quality", "")
        risk = ba.get("risk", "")

        # —— 主复购发现：业务推理 ——
        meaning = f"复购率{rate_pct}，忠诚客户比例"
        meaning += f"{loyalty_rate*100:.1f}%" if loyalty_rate is not None else "N/A"
        if repeat_value_share is not None:
            meaning += f"，复购客户贡献{repeat_value_share*100:.1f}%的收入"
        meaning += f"，客户结构质量{quality}。"
        impact = f"{risk}；"
        if repeat_value_share is not None:
            impact += f"若复购客户流失，将直接影响约{repeat_value_share*100:.0f}%的收入。"
        else:
            impact += "需持续监控复购结构变化。"
        if quality == "低":
            rec = "建立客户分层与召回体系，对低复购客户推送定向优惠，提升首购→复购转化。"
        elif quality == "高":
            rec = "深化高复购客户价值（会员/VIP 体系），同时拓展新客以平衡结构。"
        else:
            rec = "巩固复购基本盘，针对中频客户设计升级激励。"

        findings.append(f.retention(
            metric="复购率", value=rate*100 if rate else None, unit="%",
            title=f"客户复购率{rate_pct}，{m.repeat_customer_count or 0}/{m.total_customer_count or 0}客户有复购",
            confidence=1.0,
            description=meaning,
            business_meaning=meaning,
            business_impact=impact,
            recommendation=rec))
        if m.avg_purchase_frequency is not None:
            findings.append(f.summary(f"人均购买{m.avg_purchase_frequency:.1f}次"))
        return findings

    def execute(self, df, dimension=None, metric=None, algorithm=None):
        self._cache = {}
        self._compute(df, dimension, metric)
        return super().execute(df, dimension, metric, algorithm)