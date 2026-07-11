"""
RankingCalculator —— 排名分析业务计算引擎

支持：TOPN / BottomN / Rank / Share / Cumulative Share
"""

import math
import pandas as pd
from typing import List, Optional, Tuple
from src.calculators.base import BusinessMetrics


class RankingCalculator:
    """排名分析业务计算引擎

    使用方式：
        calc = RankingCalculator()
        metrics = calc.calculate_topn(df, dim_col, metric_col, n=10)
        metrics = calc.calculate_cumulative_share(metrics)
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
    def calculate_topn(
        df: pd.DataFrame,
        dim_col: str,
        metric_col: str,
        n: int = 10,
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """TOPN：前 N 名"""
        grouped = RankingCalculator.prepare_grouped(df, dim_col, metric_col)
        m = metrics or BusinessMetrics(calculator="ranking", dimension=dim_col,
                                        metric=metric_col)
        n = min(n, len(grouped))
        top = grouped.head(n)
        m.top_n = n
        m.top_n_labels = [str(v) for v in top[dim_col].tolist()]
        m.top_n_values = [float(v) for v in top[metric_col].tolist()]
        m.labels = [str(v) for v in grouped[dim_col].tolist()]
        m.values = [float(v) for v in grouped[metric_col].tolist()]
        return m

    @staticmethod
    def calculate_bottomn(
        df: pd.DataFrame,
        dim_col: str,
        metric_col: str,
        n: int = 10,
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """BottomN：后 N 名"""
        grouped = RankingCalculator.prepare_grouped(df, dim_col, metric_col)
        m = metrics or BusinessMetrics(calculator="ranking", dimension=dim_col,
                                        metric=metric_col)
        n = min(n, len(grouped))
        bottom = grouped.tail(n)
        m.bottom_n_labels = [str(v) for v in bottom[dim_col].tolist()]
        m.bottom_n_values = [float(v) for v in bottom[metric_col].tolist()]
        m.labels = [str(v) for v in grouped[dim_col].tolist()]
        m.values = [float(v) for v in grouped[metric_col].tolist()]
        return m

    @staticmethod
    def calculate_ranks(
        values: List[float],
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """排名：1-based，同值同排名（min 策略）"""
        m = metrics or BusinessMetrics(calculator="ranking")
        m.values = values
        # 降序排名
        indexed = [(v, i) for i, v in enumerate(values)]
        indexed.sort(key=lambda x: x[0], reverse=True)

        ranks = [0] * len(values)
        current_rank = 1
        for idx, (val, orig_idx) in enumerate(indexed):
            if idx > 0 and indexed[idx - 1][0] > val:
                current_rank = idx + 1
            ranks[orig_idx] = current_rank

        m.ranks = ranks
        return m

    @staticmethod
    def calculate_shares(
        values: List[float],
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """占比：每个值占总和的百分比（0-1）"""
        m = metrics or BusinessMetrics(calculator="ranking")
        m.values = values
        total = sum(values)
        if total > 0:
            m.shares = [round(v / total, 6) for v in values]
        else:
            m.shares = [0.0] * len(values)
        return m

    @staticmethod
    def calculate_cumulative_share(
        values: List[float],
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """累计占比：按降序排列的累计占比"""
        m = metrics or BusinessMetrics(calculator="ranking")
        m.values = values
        total = sum(values)
        if total <= 0:
            m.cumulative_shares = [0.0] * len(values)
            return m

        # 降序排列
        sorted_vals = sorted(values, reverse=True)
        cum = 0.0
        cum_shares = []
        for v in sorted_vals:
            cum += v
            cum_shares.append(round(cum / total, 6))
        m.cumulative_shares = cum_shares
        return m

    @staticmethod
    def execute(
        df: pd.DataFrame,
        dim_col: str,
        metric_col: str,
        n: int = 10,
    ) -> BusinessMetrics:
        """一站式执行"""
        m = RankingCalculator.calculate_topn(df, dim_col, metric_col, n)
        m = RankingCalculator.calculate_ranks(m.values, m)
        m = RankingCalculator.calculate_shares(m.values, m)
        m = RankingCalculator.calculate_cumulative_share(m.values, m)
        m = RankingCalculator.calculate_bottomn(df, dim_col, metric_col, min(n, 5), m)
        return m