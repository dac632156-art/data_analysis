"""
AnomalyCalculator —— 异常分析业务计算引擎

支持：Z-Score 异常检测、IQR 异常检测
"""

import math
import pandas as pd
import numpy as np
from typing import List, Optional
from src.calculators.base import BusinessMetrics


class AnomalyCalculator:
    """异常分析业务计算引擎

    使用方式：
        calc = AnomalyCalculator()
        metrics = calc.calculate_zscore(values, threshold=3.0)
        metrics = calc.calculate_iqr(values)
    """

    @staticmethod
    def calculate_zscore(
        values: List[float],
        threshold: float = 3.0,
        labels: Optional[List[str]] = None,
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """Z-Score 异常检测

        |Z| > threshold 视为异常（默认 threshold=3，即 3σ 原则）
        """
        m = metrics or BusinessMetrics(calculator="anomaly", algorithm="zscore")
        m.values = values
        m.anomaly_method = "zscore"
        m.anomaly_threshold = threshold

        if len(values) < 3:
            m.z_scores = [0.0] * len(values)
            return m

        mean = sum(values) / len(values)
        std = (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5

        z_scores = []
        anomaly_indices = []
        anomaly_labels = []

        for i, v in enumerate(values):
            if std > 0:
                z = (v - mean) / std
            else:
                z = 0.0
            z_scores.append(round(z, 4))
            if abs(z) > threshold:
                anomaly_indices.append(i)
                if labels and i < len(labels):
                    anomaly_labels.append(labels[i])
                else:
                    anomaly_labels.append(f"index_{i}")

        m.z_scores = z_scores
        m.anomaly_indices = anomaly_indices
        m.anomaly_labels = anomaly_labels
        m.labels = labels or []
        return m

    @staticmethod
    def calculate_iqr(
        values: List[float],
        multiplier: float = 1.5,
        labels: Optional[List[str]] = None,
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """IQR（四分位距）异常检测

        异常值 = 低于 Q1 - 1.5×IQR 或 高于 Q3 + 1.5×IQR
        """
        m = metrics or BusinessMetrics(calculator="anomaly", algorithm="iqr")
        m.values = values
        m.anomaly_method = "iqr"

        sorted_vals = sorted(values)
        n = len(sorted_vals)

        if n < 4:
            m.anomaly_indices = []
            return m

        # 使用 numpy.percentile 线性插值计算分位数，比 int() 截断更精确
        q1 = float(np.percentile(sorted_vals, 25))
        q3 = float(np.percentile(sorted_vals, 75))
        iqr = q3 - q1

        m.q1 = round(q1, 4)
        m.q3 = round(q3, 4)
        m.iqr = round(iqr, 4)

        lower = q1 - multiplier * iqr
        upper = q3 + multiplier * iqr

        anomaly_indices = []
        anomaly_labels = []

        for i, v in enumerate(values):
            if v < lower or v > upper:
                anomaly_indices.append(i)
                if labels and i < len(labels):
                    anomaly_labels.append(labels[i])
                else:
                    anomaly_labels.append(f"index_{i}")

        m.anomaly_indices = anomaly_indices
        m.anomaly_labels = anomaly_labels
        m.labels = labels or []
        return m

    @staticmethod
    def execute(
        values: List[float],
        labels: Optional[List[str]] = None,
        method: str = "zscore",
        threshold: float = 3.0,
    ) -> BusinessMetrics:
        """一站式执行"""
        if method == "iqr":
            return AnomalyCalculator.calculate_iqr(values, labels=labels)
        return AnomalyCalculator.calculate_zscore(values, threshold=threshold, labels=labels)