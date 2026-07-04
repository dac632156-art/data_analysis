"""
增长分析模板 —— 趋势、增长率、同比、环比、累计

V2：使用 TemplateMeta + TemplateRuntime，拆分 build_*() 方法
"""

import pandas as pd
from src.analysis_templates.base import (
    AnalysisTemplate, TemplateMeta, TemplateRuntime,
    AnalysisPackage, KPIItem, TableData, ChartData,
)


class GrowthAnalysis(AnalysisTemplate):
    meta = TemplateMeta(
        analysis_type="growth_analysis",
        display_name="增长分析",
        version="2.0",
        description="分析指标随时间的变化趋势与增长率",
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

    # ===== 内部缓存（build_* 之间共享） =====
    _cache: dict = {}

    def _compute(self, df: pd.DataFrame, dimension: str, metric: str, algorithm: str = "mom"):
        """核心计算：支持真正的 YoY/MoM/QoQ 算法

        算法说明：
        - mom（环比）：每个周期 vs 上一周期
        - yoy（同比）：每个周期 vs 去年同期
        - qoq（季环比）：每个季度 vs 上一季度
        如果时间列无法解析为 datetime，所有算法退化为逐行 pct_change。
        """
        grouped = df.groupby(dimension)[metric].sum().reset_index()
        grouped = grouped.sort_values(dimension)

        # 尝试解析时间列
        time_parsed = pd.to_datetime(grouped[dimension], errors='coerce')
        # 安全检查：用 count 对比长度判断是否有 NaT（避免 .notna() 触发 Linux checknull 崩溃）
        can_parse_time = (time_parsed.count() == len(time_parsed))
        self._cache["can_parse_time"] = can_parse_time

        if can_parse_time:
            grouped["_dt"] = time_parsed
            grouped["_year"] = grouped["_dt"].dt.year

            if algorithm in ("yoy", "同比"):
                grouped = self._calc_yoy(grouped, metric)
            elif algorithm in ("qoq", "季环比"):
                grouped = self._calc_qoq(grouped, metric)
            else:  # mom / 环比
                grouped = self._calc_mom(grouped, metric)
        else:
            # 时间列不可解析 → 退化为逐行 pct_change
            algorithm = "mom"
            grouped["growth_rate"] = self._safe_pct_change(grouped[metric]) * 100
            self._cache["algorithm_label"] = "环比变化率"
            self._cache["algorithm"] = algorithm

        # 累计值
        grouped["cumsum"] = grouped[metric].cumsum()

        self._cache["grouped"] = grouped
        self._cache["dimension"] = dimension
        self._cache["metric"] = metric
        self._cache["algorithm"] = algorithm

        valid_growth = grouped["growth_rate"].dropna()
        self._cache["avg_growth"] = valid_growth.mean() if len(valid_growth) > 0 else 0
        self._cache["max_idx"] = grouped[metric].idxmax()
        self._cache["min_idx"] = grouped[metric].idxmin()
        self._cache["max_growth_idx"] = grouped["growth_rate"].idxmax() if len(valid_growth) > 0 else None
        return grouped

    def _calc_yoy(self, grouped, metric):
        """YoY：本月 / 去年同月 - 1"""
        grouped["_month"] = grouped["_dt"].dt.month
        # 构建 (year, month) → value 映射
        ym_map = {}
        for _, row in grouped.iterrows():
            ym_map[(row["_year"], row["_month"])] = row[metric]

        growth_rates = []
        for _, row in grouped.iterrows():
            prev_val = ym_map.get((row["_year"] - 1, row["_month"]))
            if prev_val and prev_val > 0:
                growth_rates.append(((row[metric] / prev_val) - 1) * 100)
            else:
                growth_rates.append(None)

        grouped["growth_rate"] = growth_rates
        self._cache["algorithm_label"] = "同比增长率"
        return grouped

    def _calc_mom(self, grouped, metric):
        """MoM：本月 / 上月 - 1"""
        # 按月排序后的逐行对比（与 pct_change 一致但更语义化）
        grouped["_year_month"] = grouped["_dt"].dt.to_period("M")
        grouped = grouped.sort_values("_year_month").reset_index(drop=True)
        grouped["growth_rate"] = self._safe_pct_change(grouped[metric]) * 100
        self._cache["algorithm_label"] = "环比变化率"
        return grouped

    def _calc_qoq(self, grouped, metric):
        """QoQ：本季度 / 上季度 - 1"""
        grouped["_quarter"] = grouped["_dt"].dt.to_period("Q")
        quarterly = grouped.groupby("_quarter")[metric].sum().reset_index()
        quarterly = quarterly.sort_values("_quarter")
        quarterly["growth_rate"] = self._safe_pct_change(quarterly[metric]) * 100
        # 把季度数据合并回原始粒度（标记为季度级）
        grouped["growth_rate"] = None
        for _, qrow in quarterly.iterrows():
            mask = grouped["_dt"].dt.to_period("Q") == qrow["_quarter"]
            grouped.loc[mask, "growth_rate"] = qrow["growth_rate"]
        self._cache["algorithm_label"] = "季环比变化率"
        return grouped

    def build_kpis(self, df, dimension, metric, algorithm):
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_time_columns(df)[0]
        alg = algorithm or "mom"

        grouped = self._compute(df, dimension, metric, alg)
        total = grouped[metric].sum()
        avg_growth = self._cache["avg_growth"]
        max_idx = self._cache["max_idx"]
        min_idx = self._cache["min_idx"]
        alg_label = self._cache.get("algorithm_label", "增长率")

        return [
            KPIItem(label=f"总{metric}", value=f"{total:,.0f}", change="", kpi_type="sum"),
            KPIItem(label=f"平均{alg_label}",
                    value=f"{avg_growth:+.1f}%" if avg_growth != 0 else "N/A",
                    change="", kpi_type="rate"),
            KPIItem(label="峰值周期", value=str(grouped.loc[max_idx, dimension]), change="", kpi_type="sum"),
            KPIItem(label="低谷周期", value=str(grouped.loc[min_idx, dimension]), change="", kpi_type="sum"),
        ]

    def build_tables(self, df, dimension, metric, algorithm):
        grouped = self._cache.get("grouped")
        if grouped is None:
            return []
        dimension = self._cache["dimension"]
        metric = self._cache["metric"]
        alg_label = self._cache.get("algorithm_label", "增长率")

        rows = []
        for _, row in grouped.iterrows():
            gr_val = row["growth_rate"]
            gr = None if (gr_val is None or (isinstance(gr_val, float) and gr_val != gr_val)) else round(gr_val, 1)
            rows.append([str(row[dimension]), round(row[metric], 2), gr, round(row["cumsum"], 2)])

        return [TableData(
            title=f"{alg_label}明细",
            table_type="growth",
            columns=[str(dimension), metric, f"{alg_label}(%)", "累计值"],
            rows=rows,
        )]

    def build_charts(self, df, dimension, metric, algorithm):
        grouped = self._cache.get("grouped")
        if grouped is None:
            return []
        dimension = self._cache["dimension"]
        metric = self._cache["metric"]
        alg_label = self._cache.get("algorithm_label", "增长率")

        # 处理 NaN → None 便于 JSON 序列化（避免 .notna() 触发 Linux checknull 崩溃）
        gr_data = grouped[[dimension, "growth_rate"]].copy()
        gr_data["growth_rate"] = gr_data["growth_rate"].apply(
            lambda x: None if (x is None or (isinstance(x, float) and x != x)) else x
        )

        return [
            ChartData(slot="trend", chart_type="line",
                      title=f"{metric}趋势", x=dimension, y=metric,
                      data=grouped[[dimension, metric]].to_dict('records')),
            ChartData(slot="growth_rate", chart_type="bar",
                      title=f"{alg_label}变化", x=dimension, y="growth_rate",
                      data=gr_data.to_dict('records')),
            ChartData(slot="cumulative", chart_type="area",
                      title="累计趋势", x=dimension, y="cumsum",
                      data=grouped[[dimension, "cumsum"]].to_dict('records')),
        ]

    def build_insights(self, df, dimension, metric, algorithm, kpis, chart_data):
        grouped = self._cache.get("grouped")
        if grouped is None:
            return []
        dimension = self._cache["dimension"]
        metric = self._cache["metric"]
        avg_growth = self._cache["avg_growth"]
        max_idx = self._cache["max_idx"]
        max_growth_idx = self._cache.get("max_growth_idx")
        alg_label = self._cache.get("algorithm_label", "增长率")

        trend_word = '上升' if avg_growth > 0 else '下降' if avg_growth < 0 else '平稳'
        insights = [
            f"{metric}整体呈{trend_word}趋势，平均{alg_label}{avg_growth:+.1f}%",
            f"{grouped.loc[max_idx, dimension]}的{metric}最高（{grouped.loc[max_idx, metric]:,.2f}）",
        ]
        if max_growth_idx is not None:
            insights.append(f"{grouped.loc[max_growth_idx, dimension]}的{alg_label}最大")
        return insights

    def build_conclusion(self, df, dimension, metric, algorithm, insights):
        return insights[:1]  # 将最高优先级的洞察作为结论

    def execute(self, df, dimension, metric, algorithm="yoy"):
        """覆盖 execute：先执行计算再调用父类自动组装"""
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self.classifier.get_time_columns(df)[0]
        alg = algorithm or "mom"
        self._cache = {}
        self._compute(df, dimension, metric, alg)
        return super().execute(df, dimension, metric, alg)
