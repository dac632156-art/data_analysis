"""
增长分析模板 —— 趋势、增长率、同比、环比、累计、移动平均、趋势拐点

V3：全面升级为 Business Template，所有业务计算委托 GrowthCalculator
"""

from src.analysis_templates.base import (
    AnalysisTemplate, TemplateMeta, TemplateRuntime,
    AnalysisPackage, KPIItem, TableData, ChartData,
)
from src.calculators import GrowthCalculator, BusinessMetrics
from src.domain import Direction, Severity, FindingCategory


class GrowthAnalysis(AnalysisTemplate):
    meta = TemplateMeta(
        analysis_type="growth_analysis",
        display_name="增长分析",
        version="3.0",
        description="分析指标随时间的变化趋势与增长率（YoY/MoM/QoQ/移动平均/累计/拐点）",
        supported_algorithms=["yoy", "mom", "qoq"],
    )

    runtime = TemplateRuntime(
        REQUIRED_SCHEMA={
            "dimension_type": "time",
            "metric_type": "numeric",
            "min_dimension": 1,
            "min_metric": 1,
        },
        MIN_ROWS=3,
        MIN_DISTINCT_VALUES=3,
        FALLBACK="ranking_analysis",
    )

    _cache: dict = {}

    # ===== 核心计算：全部委托 GrowthCalculator =====

    def _compute(self, df, dimension, metric, algorithm="mom", window=3):
        """V3：全部业务计算委托 GrowthCalculator（含业务维度评估）"""
        segment_col = self._detect_segment_col(df, dimension, metric)
        m: BusinessMetrics = GrowthCalculator.execute(
            df, dimension, metric, algorithm, window, segment_col=segment_col)
        self._cache["metrics"] = m
        self._cache["segment_col"] = segment_col
        # 填充 labels 用于后续 build
        grouped = GrowthCalculator.prepare_series(df, dimension, metric)
        m.labels = [str(v) for v in grouped[dimension].tolist()]
        m.values = [float(v) for v in grouped[metric].tolist()]
        self._cache["dimension"] = dimension
        self._cache["metric"] = metric
        self._cache["algorithm"] = algorithm
        self._cache["_calculator_used"] = "GrowthCalculator"
        return m

    def _detect_segment_col(self, df, dimension, metric):
        """探测合适的分类维度，用于增长来源/贡献分析。

        优先选基数适中（2~20）的非数值、非时间/指标列，
        更接近'地区/类别/渠道'而非'产品名'等高频维度。
        """
        import pandas as pd
        candidates = []
        for col in df.columns:
            if col in (dimension, metric):
                continue
            if pd.api.types.is_numeric_dtype(df[col]):
                continue
            nunique = df[col].nunique(dropna=True)
            if 2 <= nunique <= 20:
                candidates.append((col, nunique))
        if not candidates:
            return None
        # 优先选基数接近 6 的列（地区/类别级别）
        candidates.sort(key=lambda x: abs(x[1] - 6))
        return candidates[0][0]

    # ===== KPI =====

    def build_kpis(self, df, dimension, metric, algorithm):
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_time_columns(df)[0]
        alg = algorithm or "mom"
        m = self._compute(df, dimension, metric, alg)

        total = sum(m.values)
        avg_growth = m.growth_rate_avg or 0
        alg_label = m.growth_rate_label

        # 峰值/谷值
        if m.values:
            max_idx = max(range(len(m.values)), key=lambda i: m.values[i])
            min_idx = min(range(len(m.values)), key=lambda i: m.values[i])
            peak_label = m.labels[max_idx] if max_idx < len(m.labels) else "—"
            trough_label = m.labels[min_idx] if min_idx < len(m.labels) else "—"
        else:
            peak_label = "—"
            trough_label = "—"

        return [
            KPIItem(label=f"总{metric}", value=f"{total:,.0f}", change="", kpi_type="sum"),
            KPIItem(label=f"平均{alg_label}",
                    value=f"{avg_growth:+.1f}%" if avg_growth != 0 else "N/A",
                    change="", kpi_type="rate"),
            KPIItem(label="峰值周期", value=peak_label, change="", kpi_type="sum"),
            KPIItem(label="低谷周期", value=trough_label, change="", kpi_type="sum"),
        ]

    # ===== Table =====

    def build_tables(self, df, dimension, metric, algorithm):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return []

        rows = []
        n = len(m.labels)
        for i in range(n):
            gr = m.growth_rates[i] if i < len(m.growth_rates) else None
            ma = m.moving_averages[i] if i < len(m.moving_averages) else None
            cum = m.cumulative_values[i] if i < len(m.cumulative_values) else None
            rows.append([
                m.labels[i],
                round(m.values[i], 2) if i < len(m.values) else None,
                round(gr, 1) if gr is not None else None,
                round(ma, 2) if ma is not None else None,
                round(cum, 2) if cum is not None else None,
            ])

        return [TableData(
            title=f"{m.growth_rate_label}明细",
            table_type="growth",
            columns=["周期", m.metric or "指标",
                     f"{m.growth_rate_label}(%)", "移动平均", "累计值"],
            rows=rows,
        )]

    # ===== Chart =====

    def build_charts(self, df, dimension, metric, algorithm):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return []
        alg_label = m.growth_rate_label

        trend_data = [{"x": m.labels[i], "y": m.values[i]}
                      for i in range(len(m.labels))]

        growth_data = [{"x": m.labels[i], "y": m.growth_rates[i] if i < len(m.growth_rates) else None}
                       for i in range(len(m.labels))]

        cum_data = [{"x": m.labels[i], "y": m.cumulative_values[i] if i < len(m.cumulative_values) else None}
                    for i in range(len(m.labels))]

        ma_data = [{"x": m.labels[i], "y": m.moving_averages[i] if i < len(m.moving_averages) else None}
                   for i in range(len(m.labels))]

        return [
            ChartData(slot="trend", chart_type="line",
                      title=f"{metric}趋势", x=dimension, y=metric,
                      data=trend_data),
            ChartData(slot="growth_rate", chart_type="bar",
                      title=f"{alg_label}变化", x=dimension, y=f"{metric}增长率",
                      data=growth_data),
            ChartData(slot="cumulative", chart_type="area",
                      title="累计增长", x=dimension, y=f"{metric}累计",
                      data=cum_data),
            ChartData(slot="moving_average", chart_type="line",
                      title="移动平均趋势", x=dimension, y=f"{metric}移动平均",
                      data=ma_data),
        ]

    # ===== Insight（事实，不调用 AI） =====

    def build_insights(self, df, dimension, metric, algorithm, kpis, chart_data):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None or not m.values:
            return ["数据不足，无法生成洞察"]

        avg_growth = m.growth_rate_avg or 0
        trend_word = '上升' if avg_growth > 0 else '下降' if avg_growth < 0 else '平稳'

        insights = [f"{metric}整体呈{trend_word}趋势，平均{m.growth_rate_label}{avg_growth:+.1f}%"]

        if m.values:
            max_idx = max(range(len(m.values)), key=lambda i: m.values[i])
            min_idx = min(range(len(m.values)), key=lambda i: m.values[i])
            if max_idx < len(m.labels):
                insights.append(
                    f"峰值出现在「{m.labels[max_idx]}」（{m.values[max_idx]:,.2f}）")
            if min_idx < len(m.labels) and min_idx != max_idx:
                insights.append(
                    f"低谷出现在「{m.labels[min_idx]}」（{m.values[min_idx]:,.2f}）")

        if m.trend_change_points:
            cp_labels = [m.labels[i] for i in m.trend_change_points if i < len(m.labels)]
            if cp_labels:
                insights.append(f"检测到 {len(cp_labels)} 个趋势拐点：{', '.join(cp_labels[:3])}")

        return insights

    # ===== Conclusion（summary / opportunity / risk / recommendation） =====

    def build_conclusion(self, df, dimension, metric, algorithm, insights):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return ["无法得出有效结论"]

        avg_growth = m.growth_rate_avg or 0
        trend_word = '上升' if avg_growth > 0 else '下降' if avg_growth < 0 else '平稳'

        conclusions = [
            f"summary: {metric}呈{trend_word}趋势，{m.growth_rate_label}平均{avg_growth:+.1f}%",
        ]

        if avg_growth > 5:
            conclusions.append("opportunity: 增长势头良好，可进一步加大投入")
        elif avg_growth < -5:
            conclusions.append("risk: 指标持续下滑，需警惕并排查原因")

        if m.trend_change_points:
            conclusions.append("recommendation: 关注趋势拐点，及时调整策略方向")
        else:
            conclusions.append("recommendation: 持续监控趋势变化，建立预警机制")

        return conclusions


    # ===== V3：业务发现与证据 =====

    def build_findings(self, df, dimension, metric, algorithm, kpis, chart_data):
        """V3 Domain Model：使用 FindingFactory 创建（业务推理级）"""
        m = self._cache.get("metrics")
        f = self.factory
        findings = []
        if m is None:
            return [f.summary(f"{metric}增长分析完成")]

        avg_growth = m.growth_rate_avg or 0
        trend_dir = Direction.UP if avg_growth > 0 else Direction.DOWN if avg_growth < 0 else Direction.FLAT
        alg_label = m.growth_rate_label
        ba = m.business_assessment or {}

        source = ba.get("source", "全量")
        driver = ba.get("driver", "")
        quality = ba.get("quality", "")
        risk = ba.get("risk", "")
        sustainability = ba.get("sustainability", "")
        top_contrib = ba.get("top_contribution")

        # —— 主增长发现：业务推理（来源/驱动/质量/风险/可持续性）——
        if top_contrib is not None:
            meaning = (f"{metric}整体平均{alg_label}{avg_growth:+.1f}%，增长主要来源于{source}"
                       f"（贡献约{top_contrib:.0f}%），由{driver}，增长质量{quality}。")
            impact = (f"增长集中度：{risk}；若{source}贡献回落，整体增长将明显承压，"
                      f"可持续性{sustainability}。")
            rec = (f"降低{source}单一依赖，拓展其他区域/品类/客户以提升增长韧性；"
                   f"同时维持{alg_label}正向惯性。")
        else:
            meaning = (f"{metric}整体平均{alg_label}{avg_growth:+.1f}%，"
                       f"呈{'上升' if avg_growth > 0 else '下降' if avg_growth < 0 else '平稳'}趋势。")
            impact = f"增长质量{quality}；{risk}；可持续性{sustainability}。"
            rec = "持续监控趋势变化；补充分类维度后可进一步定位增长来源与驱动。"

        findings.append(f.growth(
            entity="全量", metric=metric, value=avg_growth, unit="%",
            direction=trend_dir, confidence=0.95,
            description=meaning,
            business_meaning=meaning,
            business_impact=impact,
            recommendation=rec,
            tags=["trend", "growth_rate", "business_reasoning"]))

        # —— 峰值 / 低谷（事实层，保留）——
        if m.values and len(m.values) > 0:
            max_idx = max(range(len(m.values)), key=lambda i: m.values[i])
            min_idx = min(range(len(m.values)), key=lambda i: m.values[i])
            if max_idx < len(m.labels):
                findings.append(f.ranking(
                    entity=m.labels[max_idx], metric=metric, value=m.values[max_idx],
                    rank=1, confidence=1.0,
                    title=f"峰值：{m.labels[max_idx]}（{m.values[max_idx]:,.2f}）",
                    severity=Severity.INFO))
            if min_idx < len(m.labels) and min_idx != max_idx:
                findings.append(f.ranking(
                    entity=m.labels[min_idx], metric=metric, value=m.values[min_idx],
                    confidence=1.0,
                    title=f"低谷：{m.labels[min_idx]}（{m.values[min_idx]:,.2f}）",
                    severity=Severity.INFO))

        # —— 趋势拐点（风险层）——
        if m.trend_change_points:
            cp_labels = [m.labels[i] for i in m.trend_change_points[:3] if i < len(m.labels)]
            findings.append(f.anomaly(
                entity=", ".join(cp_labels) if cp_labels else "未知",
                title=f"检测到 {len(m.trend_change_points)} 个趋势拐点",
                severity=Severity.MEDIUM,
                business_meaning="趋势方向发生变化，需关注背后驱动是否反转"))

        # —— 机会 / 风险（结合增长质量）——
        if avg_growth > 5 and quality in ("高", "中"):
            findings.append(f.opportunity(
                f"增长势头良好且质量{quality}，可适度加大投入",
                entity="全量", metric=metric,
                business_impact=impact))
        elif avg_growth < -5:
            findings.append(f.risk(
                "指标持续下滑，需警惕", entity="全量", metric=metric,
                business_impact=f"{alg_label}已降至{avg_growth:+.1f}%",
                recommendation="排查下滑原因，制定应对方案"))

        return findings


    def execute(self, df, dimension, metric, algorithm="yoy"):
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_time_columns(df)[0]
        alg = algorithm or "mom"
        self._cache = {}
        self._compute(df, dimension, metric, alg)
        return super().execute(df, dimension, metric, alg)
