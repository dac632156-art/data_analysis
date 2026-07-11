"""
CorrelationCalculator —— 相关性分析业务计算引擎

支持：Pearson 相关系数、Spearman 秩相关系数、相关性矩阵
"""

import math
import pandas as pd
from typing import List, Optional
from src.calculators.base import BusinessMetrics


class CorrelationCalculator:
    """相关性分析业务计算引擎

    使用方式：
        calc = CorrelationCalculator()
        metrics = calc.calculate_pearson(series_a, series_b)
        metrics = calc.calculate_spearman(series_a, series_b)
    """

    @staticmethod
    def calculate_pearson(
        x: pd.Series,
        y: pd.Series,
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """Pearson 线性相关系数

        范围：-1（完全负相关）～ 1（完全正相关），0 表示无线性相关
        """
        m = metrics or BusinessMetrics(calculator="correlation",
                                        dimension=x.name, metric=y.name)
        m.correlation_method = "pearson"

        mask = x.notna() & y.notna()
        clean_x = x[mask]
        clean_y = y[mask]

        if len(clean_x) < 3:
            m.correlation_coefficient = None
            return m

        corr = clean_x.corr(clean_y, method="pearson")
        m.correlation_coefficient = round(float(corr), 4) if not (math.isnan(corr) or math.isinf(corr)) else None

        return m

    @staticmethod
    def calculate_spearman(
        x: pd.Series,
        y: pd.Series,
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """Spearman 秩相关系数

        范围：-1～1，度量单调关系强度（不受异常值影响）
        """
        m = metrics or BusinessMetrics(calculator="correlation",
                                        dimension=x.name, metric=y.name)
        m.correlation_method = "spearman"

        mask = x.notna() & y.notna()
        clean_x = x[mask]
        clean_y = y[mask]

        if len(clean_x) < 3:
            m.correlation_coefficient = None
            return m

        corr = clean_x.corr(clean_y, method="spearman")
        m.correlation_coefficient = round(float(corr), 4) if not (math.isnan(corr) or math.isinf(corr)) else None

        return m

    @staticmethod
    def calculate_correlation_matrix(
        df: pd.DataFrame,
        numeric_cols: Optional[List[str]] = None,
        method: str = "pearson",
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """相关性矩阵：数值列两两之间的相关系数"""
        m = metrics or BusinessMetrics(calculator="correlation")
        m.correlation_method = method

        if numeric_cols is None:
            numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()

        if len(numeric_cols) < 2:
            return m

        corr_matrix = df[numeric_cols].corr(method=method)
        pairs = []
        for i, col_a in enumerate(numeric_cols):
            for j, col_b in enumerate(numeric_cols):
                if i < j:
                    val = corr_matrix.loc[col_a, col_b]
                    if not (math.isnan(val) or math.isinf(val)):
                        pairs.append({
                            "x": col_a,
                            "y": col_b,
                            "coefficient": round(float(val), 4),
                        })

        m.correlation_pairs = pairs
        return m

    @staticmethod
    def execute(
        x: pd.Series,
        y: pd.Series,
        method: str = "pearson",
    ) -> BusinessMetrics:
        """一站式执行"""
        if method == "spearman":
            return CorrelationCalculator.calculate_spearman(x, y)
        return CorrelationCalculator.calculate_pearson(x, y)