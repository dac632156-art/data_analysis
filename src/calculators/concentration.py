"""
ConcentrationCalculator —— 集中度分析业务计算引擎

支持：帕累托（Pareto）、CR3、CR5、HHI、基尼系数
"""

import math
import pandas as pd
import numpy as np
from typing import List, Optional, Dict, Any
from src.calculators.base import BusinessMetrics


class ConcentrationCalculator:
    """集中度分析业务计算引擎

    使用方式：
        calc = ConcentrationCalculator()
        metrics = calc.calculate_pareto(df, dim_col, metric_col)
        metrics = calc.calculate_hhi(metrics)
    """

    @staticmethod
    def prepare_grouped(
        df: pd.DataFrame,
        dim_col: str,
        metric_col: str,
    ) -> pd.DataFrame:
        """预处理：按维度分组汇总 → 降序排列"""
        grouped = df.groupby(dim_col)[metric_col].sum().reset_index()
        return grouped.sort_values(metric_col, ascending=False).reset_index(drop=True)

    @staticmethod
    def calculate_pareto(
        df: pd.DataFrame,
        dim_col: str,
        metric_col: str,
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """帕累托分析：Top20% 的维度贡献了多少 % 的指标"""
        grouped = ConcentrationCalculator.prepare_grouped(df, dim_col, metric_col)
        m = metrics or BusinessMetrics(calculator="concentration",
                                        dimension=dim_col, metric=metric_col)

        total = float(grouped[metric_col].sum())
        n = len(grouped)

        m.labels = [str(v) for v in grouped[dim_col].tolist()]
        m.values = [float(v) for v in grouped[metric_col].tolist()]

        # 累计占比
        cumsum = grouped[metric_col].cumsum()
        m.cumulative_shares = [
            round(float(cs) / total, 6) if total > 0 else 0.0
            for cs in cumsum
        ]

        # 占比
        m.shares = [
            round(float(v) / total, 6) if total > 0 else 0.0
            for v in grouped[metric_col]
        ]

        # Top20% 贡献率
        top20_count = max(1, int(n * 0.2))
        if total > 0:
            top20_sum = grouped[metric_col].head(top20_count).sum()
            m.top20_share = round(float(top20_sum) / total, 4)
            # 帕累托比例：表示 "Top20% 的维度贡献了 X% 的指标"
            # pareto_ratio 存储维度占比（0-1），top20_share 存储指标占比（0-1）
            m.pareto_ratio = round(top20_count / n, 4) if n > 0 else 0.0
        else:
            m.top20_share = 0.0
            m.pareto_ratio = 0.0

        return m

    @staticmethod
    def calculate_cr3(
        values: List[float],
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """CR3：前3名集中度"""
        m = metrics or BusinessMetrics(calculator="concentration")
        m.values = values
        total = sum(values)
        if total > 0:
            top3 = sorted(values, reverse=True)[:3]
            m.cr3 = round(sum(top3) / total, 4)
        else:
            m.cr3 = 0.0
        return m

    @staticmethod
    def calculate_cr5(
        values: List[float],
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """CR5：前5名集中度"""
        m = metrics or BusinessMetrics(calculator="concentration")
        m.values = values
        total = sum(values)
        if total > 0:
            top5 = sorted(values, reverse=True)[:5]
            m.cr5 = round(sum(top5) / total, 4)
        else:
            m.cr5 = 0.0
        return m

    @staticmethod
    def calculate_hhi(
        values: List[float],
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """HHI（赫芬达尔-赫希曼指数）：Σ(份额²) × 10000

        范围：0（完全竞争）～ 10000（完全垄断）
        1800 以上视为高度集中
        """
        m = metrics or BusinessMetrics(calculator="concentration")
        m.values = values
        total = sum(values)
        if total > 0:
            shares = [v / total for v in values]
            hhi = sum(s ** 2 for s in shares) * 10000
            m.hhi = round(hhi, 2)
        else:
            m.hhi = 0.0
        return m

    @staticmethod
    def _assess(m: BusinessMetrics) -> Dict[str, Any]:
        """基于 HHI/CR3/Top20% 推导 集中度等级 / 风险 / 增长韧性。"""
        hhi = m.hhi or 0
        cr3 = (m.cr3 or 0) * 100
        top20 = (m.top20_share or 0) * 100
        if hhi >= 2500:
            level, resilience = "高度集中", "低"
            risk = "头部依赖严重，单点失效将导致整体大幅波动"
        elif hhi >= 1500:
            level, resilience = "中度集中", "中"
            risk = "存在一定头部集中度，需关注头部稳定性"
        else:
            level, resilience = "分散竞争", "高"
            risk = "集中度低，结构稳健"
        return {"level": level, "risk": risk, "resilience": resilience,
                "hhi": hhi, "cr3": cr3, "top20": top20}

    @staticmethod
    def execute(
        df: pd.DataFrame,
        dim_col: str,
        metric_col: str,
    ) -> BusinessMetrics:
        """一站式执行：帕累托 + CR3 + CR5 + HHI（含业务维度评估）"""
        m = ConcentrationCalculator.calculate_pareto(df, dim_col, metric_col)
        m = ConcentrationCalculator.calculate_cr3(m.values, m)
        m = ConcentrationCalculator.calculate_cr5(m.values, m)
        m = ConcentrationCalculator.calculate_hhi(m.values, m)
        m.business_assessment = ConcentrationCalculator._assess(m)
        return m