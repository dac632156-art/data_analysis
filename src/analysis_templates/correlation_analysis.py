"""
相关分析模板 —— 数值指标间的关联关系（Pearson/Spearman）

V3：全面升级为 Business Template，所有业务计算委托 CorrelationCalculator
"""

from src.analysis_templates.base import (
    AnalysisTemplate, TemplateMeta, TemplateRuntime,
    KPIItem, TableData, ChartData,
)
from src.calculators import CorrelationCalculator, BusinessMetrics
from src.domain import Direction, Severity, FindingCategory


class CorrelationAnalysis(AnalysisTemplate):
    meta = TemplateMeta(
        analysis_type="correlation_analysis",
        display_name="相关分析",
        version="3.0",
        description="分析数值指标间的关联关系（Pearson/Spearman/相关性矩阵）",
        supported_algorithms=["pearson", "spearman"],
    )

    runtime = TemplateRuntime(
        REQUIRED_SCHEMA={
            "dimension_type": "",
            "metric_type": "numeric",
            "min_dimension": 0,
            "min_metric": 2,
        },
        MIN_ROWS=3,
        FALLBACK="ranking_analysis",
    )

    _cache: dict = {}

    def _compute(self, df, col1, col2, method="pearson"):
        """V3：委托 CorrelationCalculator"""
        numeric_cols = self._get_numeric_columns(df)
        if len(numeric_cols) < 2:
            self._cache["error"] = "至少需要2个数值列"
            return
        col1 = col1 or numeric_cols[0]
        col2 = col2 or (numeric_cols[1] if len(numeric_cols) > 1 else None)
        if col2 is None:
            self._cache["error"] = "至少需要2个数值列"
            return
        # 避免 col1 == col2 导致 df[[col1, col2]] 产生重复列名，进而 df[col] 返回 DataFrame 而非 Series
        if col1 == col2:
            for c in numeric_cols:
                if c != col1:
                    col2 = c
                    break


        clean = df[[col1, col2]].dropna()
        m: BusinessMetrics = CorrelationCalculator.execute(clean[col1], clean[col2], method)
        # 相关性矩阵
        m = CorrelationCalculator.calculate_correlation_matrix(df, numeric_cols, method, m)
        self._cache["metrics"] = m
        self._cache["col1"] = col1
        self._cache["col2"] = col2
        self._cache["clean"] = clean
        return m

    def build_kpis(self, df, dimension, metric, algorithm):
        numeric_cols = self._get_numeric_columns(df)
        col1 = dimension or (numeric_cols[0] if numeric_cols else None)
        col2 = metric or (numeric_cols[1] if len(numeric_cols) > 1 else None)
        if col1 is None or col2 is None:
            return [KPIItem(label="数据不足", value="N/A", change="", kpi_type="rate")]
        m = self._compute(df, col1, col2, algorithm or "pearson")
        if m is None:
            return [KPIItem(label="无法计算", value="N/A", change="", kpi_type="rate")]

        corr = m.correlation_coefficient
        return [
            KPIItem(label=f"{col1} vs {col2}",
                    value=f"r={corr:.3f}" if corr is not None else "N/A",
                    change="", kpi_type="rate"),
            KPIItem(label=f"方法", value=m.correlation_method, change="", kpi_type="count"),
            KPIItem(label="样本量", value=str(len(self._cache.get("clean", []))), change="", kpi_type="count"),
        ]

    def build_tables(self, df, dimension, metric, algorithm):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return []

        if not m.correlation_pairs:
            return [TableData(title="相关性矩阵", table_type="correlation",
                              columns=["提示"], rows=[["无可计算的数值列对"]])]

        rows = [[p["x"], p["y"], p["coefficient"]] for p in m.correlation_pairs]
        return [TableData(
            title=f"相关性矩阵（{m.correlation_method}）",
            table_type="correlation",
            columns=["指标A", "指标B", "相关系数"],
            rows=rows,
        )]

    def build_charts(self, df, dimension, metric, algorithm):
        clean = self._cache.get("clean")
        col1 = self._cache.get("col1")
        col2 = self._cache.get("col2")
        if clean is None:
            return []

        # ★ 散点数据上限采样：避免百万行全量进入 ECharts option
        MAX_SCATTER = 3000
        if len(clean) > MAX_SCATTER:
            clean_sample = clean.sample(n=MAX_SCATTER, random_state=42)
        else:
            clean_sample = clean

        return [ChartData(slot="correlation_scatter", chart_type="scatter",
                          title=f"{col1} vs {col2}", x=col1, y=col2,
                          data=clean_sample[[col1, col2]].to_dict("records"))]

    def build_insights(self, df, dimension, metric, algorithm, kpis, chart_data):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return ["数据不足"]

        corr = m.correlation_coefficient
        col1 = self._cache.get("col1", "")
        col2 = self._cache.get("col2", "")
        if corr is None:
            return ["无法计算相关系数"]

        abs_corr = abs(corr)
        strength = "强" if abs_corr > 0.7 else "较强" if abs_corr > 0.5 else "中等" if abs_corr > 0.3 else "弱"
        direction = "正" if corr > 0 else "负"

        insights = [f"「{col1}」与「{col2}」呈{direction}相关，强度「{strength}」（r={corr:.3f}）"]

        if m.correlation_pairs:
            top = sorted(m.correlation_pairs, key=lambda p: abs(p["coefficient"]), reverse=True)
            for p in top[:3]:
                if p["x"] != col1 or p["y"] != col2:
                    insights.append(f"「{p['x']}」与「{p['y']}」r={p['coefficient']:.3f}")

        return insights[:4]

    def build_conclusion(self, df, dimension, metric, algorithm, insights):
        m: BusinessMetrics = self._cache.get("metrics")
        if m is None:
            return ["无法得出相关分析结论"]

        corr = m.correlation_coefficient
        conclusions = [f"summary: r={corr:.3f}（{m.correlation_method}）"]
        if corr is not None and abs(corr) > 0.7:
            conclusions.append("opportunity: 强相关关系可指导交叉销售或捆绑策略")
        elif corr is not None and abs(corr) < 0.2:
            conclusions.append("insight: 弱相关或无线性关系，可能需要探索非线性或其他因子")
        return conclusions



    def build_findings(self, df, dimension, metric, algorithm, kpis, chart_data):
        m = self._cache.get("metrics")
        f = self.factory
        findings = []
        if m is None:
            return [f.summary("相关分析完成")]
        corr = m.correlation_coefficient
        if corr is not None:
            abs_corr = abs(corr)
            strength = "强" if abs_corr > 0.7 else "较强" if abs_corr > 0.5 else "中等" if abs_corr > 0.3 else "弱"
            direction_str = "正" if corr > 0 else "负"
            findings.append(f.correlation(
                title=f"r={corr:.3f}，呈{direction_str}相关（{strength}）",
                metric=f"{self._cache.get('col1','?')} vs {self._cache.get('col2','?')}", value=corr, confidence=0.9,
                business_meaning=f"两个指标存在{direction_str}向{strength}相关关系"))
        if m.correlation_pairs:
            top = sorted(m.correlation_pairs, key=lambda p: abs(p.get("coefficient", 0)), reverse=True)
            for p in top[:3]:
                findings.append(f.correlation(
                    title=f"「{p['x']}」与「{p['y']}」r={p['coefficient']:.3f}",
                    metric=f"{p['x']} vs {p['y']}", value=p['coefficient'], confidence=0.9))
        return findings

    def execute(self, df, dimension, metric, algorithm="pearson"):
        numeric_cols = self._get_numeric_columns(df)
        col1 = dimension or (numeric_cols[0] if numeric_cols else None)
        col2 = metric or (numeric_cols[1] if len(numeric_cols) > 1 else None)
        self._cache = {}
        self._compute(df, col1, col2, algorithm or "pearson")
        return super().execute(df, dimension, metric, algorithm)
