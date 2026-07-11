"""
DistributionCalculator —— 分布分析业务计算引擎

支持：均值、中位数、标准差、偏度、峰度、分位数、IQR、直方图分箱
"""

import math
import pandas as pd
import numpy as np
from typing import List, Optional
from src.calculators.base import BusinessMetrics


class DistributionCalculator:
    """分布分析业务计算引擎

    使用方式：
        calc = DistributionCalculator()
        metrics = calc.calculate_stats(df, metric_col)
        metrics = calc.calculate_histogram(metrics, bins=10)
    """

    @staticmethod
    def calculate_stats(
        series: pd.Series,
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """基础统计：均值、中位数、标准差、偏度、峰度、分位数"""
        m = metrics or BusinessMetrics(calculator="distribution", metric=series.name)

        clean = series.dropna()
        if len(clean) == 0:
            return m

        m.values = [float(v) for v in clean.tolist()]
        m.mean = round(float(clean.mean()), 4)
        m.median = round(float(clean.median()), 4)
        m.min_val = round(float(clean.min()), 4)
        m.max_val = round(float(clean.max()), 4)

        if len(clean) >= 2:
            m.std = round(float(clean.std()), 4)
        try:
            if len(clean) >= 3:
                m.skew = round(float(clean.skew()), 4)
        except Exception:
            pass
        try:
            if len(clean) >= 4:
                m.kurtosis = round(float(clean.kurtosis()), 4)
        except Exception:
            pass

        if len(clean) >= 2:
            m.q1 = round(float(clean.quantile(0.25)), 4)
            m.q3 = round(float(clean.quantile(0.75)), 4)
            m.iqr = round(m.q3 - m.q1, 4)
        else:
            m.q1 = m.mean
            m.q3 = m.mean
            m.iqr = 0.0

        return m

    @staticmethod
    def calculate_histogram(
        values: List[float],
        bins: int = 10,
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """直方图分箱"""
        m = metrics or BusinessMetrics(calculator="distribution")
        m.values = values

        if len(values) < 2:
            return m

        try:
            hist, edges = np.histogram(values, bins=bins)
            m.histogram_counts = [int(h) for h in hist]
            m.histogram_bins = [round(float(e), 4) for e in edges]
        except Exception:
            pass

        return m

    @staticmethod
    def execute(
        series: pd.Series,
        bins: int = 10,
    ) -> BusinessMetrics:
        """一站式执行"""
        m = DistributionCalculator.calculate_stats(series)
        if len(series.dropna()) >= 2:
            clean = series.dropna().tolist()
            m = DistributionCalculator.calculate_histogram(clean, bins, m)
        return m