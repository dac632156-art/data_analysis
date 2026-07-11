"""
ComparisonCalculator —— 对比分析业务计算引擎

支持：差异（Difference）、差异率（Difference Rate）、提升度（Lift）
"""

import pandas as pd
from typing import List, Optional, Dict
from src.calculators.base import BusinessMetrics


class ComparisonCalculator:
    """对比分析业务计算引擎

    使用方式：
        calc = ComparisonCalculator()
        metrics = calc.calculate_difference(df, dim_col, metric_col)
        metrics = calc.calculate_lift(metrics, baseline_label="对照组")
    """

    @staticmethod
    def prepare_grouped(
        df: pd.DataFrame,
        dim_col: str,
        metric_col: str,
    ) -> pd.DataFrame:
        """预处理：按维度分组汇总"""
        grouped = df.groupby(dim_col)[metric_col].agg(
            ["sum", "mean", "count"]
        ).reset_index()
        grouped.columns = [dim_col, "sum", "mean", "count"]
        return grouped

    @staticmethod
    def calculate_difference(
        df: pd.DataFrame,
        dim_col: str,
        metric_col: str,
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """差异：各组均值 vs 全局均值"""
        grouped = ComparisonCalculator.prepare_grouped(df, dim_col, metric_col)
        m = metrics or BusinessMetrics(calculator="comparison", dimension=dim_col,
                                        metric=metric_col)

        global_mean = grouped["mean"].mean()
        m.global_mean = round(float(global_mean), 2)
        m.global_sum = round(float(grouped["sum"].sum()), 2)
        m.labels = [str(v) for v in grouped[dim_col].tolist()]
        m.values = [float(v) for v in grouped["mean"].tolist()]
        m.differences = [round(float(v - global_mean), 2) for v in grouped["mean"]]
        return m

    @staticmethod
    def calculate_difference_rate(
        metrics: BusinessMetrics,
    ) -> BusinessMetrics:
        """差异率：各组 vs 全局均值的百分比差异"""
        if metrics.global_mean and metrics.global_mean != 0:
            metrics.difference_rates = [
                round((d / metrics.global_mean) * 100, 2) if d is not None else None
                for d in metrics.differences
            ]
        else:
            metrics.difference_rates = [None] * len(metrics.differences)
        return metrics

    @staticmethod
    def calculate_lift(
        df: pd.DataFrame,
        dim_col: str,
        metric_col: str,
        baseline_label: str,
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """提升度（Lift）：各组 vs 指定基准组

        Lift = 目标组指标 / 基准组指标
        """
        grouped = ComparisonCalculator.prepare_grouped(df, dim_col, metric_col)
        m = metrics or BusinessMetrics(calculator="comparison", dimension=dim_col,
                                        metric=metric_col)
        m.labels = [str(v) for v in grouped[dim_col].tolist()]
        m.values = [float(v) for v in grouped["mean"].tolist()]

        # 找基准组
        baseline_val = None
        for _, row in grouped.iterrows():
            if str(row[dim_col]) == baseline_label:
                baseline_val = float(row["mean"])
                break

        lifts = []
        for _, row in grouped.iterrows():
            if baseline_val and baseline_val > 0:
                lifts.append(round(float(row["mean"]) / baseline_val, 4))
            else:
                lifts.append(None)

        m.lifts = lifts
        return m

    @staticmethod
    def execute(
        df: pd.DataFrame,
        dim_col: str,
        metric_col: str,
    ) -> BusinessMetrics:
        """一站式执行：差异 + 差异率"""
        m = ComparisonCalculator.calculate_difference(df, dim_col, metric_col)
        m = ComparisonCalculator.calculate_difference_rate(m)
        return m