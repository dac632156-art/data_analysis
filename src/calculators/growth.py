"""
GrowthCalculator —— 增长分析业务计算引擎

支持：YoY（同比）、MoM（环比）、增长率、移动平均、累计增长、趋势拐点检测

所有方法都是独立的原子操作，Template 可按需自由组合调用。
"""

import math
import pandas as pd
from typing import List, Optional, Tuple, Dict, Any
from src.calculators.base import BusinessMetrics


class GrowthCalculator:
    """增长分析业务计算引擎

    使用方式：
        calc = GrowthCalculator()
        metrics = calc.calculate_yoy(df, time_col, metric_col)
        metrics = calc.calculate_moving_average(metrics, window=3)
    """

    # ========== 原子计算方法 ==========

    @staticmethod
    def prepare_series(
        df: pd.DataFrame,
        time_col: str,
        metric_col: str,
    ) -> pd.DataFrame:
        """预处理：按时间列分组汇总 → 排序 → 解析 datetime → 超阈值时升阶重采样"""
        grouped = df.groupby(time_col)[metric_col].sum().reset_index()
        grouped = grouped.sort_values(time_col).reset_index(drop=True)
        time_parsed = pd.to_datetime(grouped[time_col], errors="coerce")
        can_parse = time_parsed.count() == len(time_parsed)

        # ★ 时间桶过细（如日级 400+ 点）时，自动升阶重采样到「合适粒度」
        #    目标：桶数落在 [_MIN_BUCKETS, _MAX_BUCKETS] 区间内，优先选最细但不过密的
        #    粒度。零售/时序数据直接在原生日级序列上做趋势/拐点检测会被噪声淹没
        #    （如 478 个日级点炸出 80+ 个伪拐点）。月级（~12-24 桶）才是趋势分析的
        #    合理粒度，且对同比/环比语义无损。
        _MIN_BUCKETS = 8
        _MAX_BUCKETS = 60
        if can_parse and len(grouped) > _MAX_BUCKETS:
            grouped["_dt_parsed"] = time_parsed
            chosen_freq = None
            for freq, _freq_label in [("D", "日"), ("W", "周"), ("M", "月"), ("Q", "季"), ("Y", "年")]:
                cnt = grouped["_dt_parsed"].dt.to_period(freq).nunique()
                if _MIN_BUCKETS <= cnt <= _MAX_BUCKETS:
                    chosen_freq = freq
                    break
                if freq == "Y":  # 兜底：年粒度
                    chosen_freq = "Y"
            if chosen_freq:
                grouped["_bucket"] = grouped["_dt_parsed"].dt.to_period(chosen_freq).astype(str)
                grouped = (grouped
                           .groupby("_bucket", as_index=False)
                           .agg({metric_col: "sum", "_dt_parsed": "first"})
                           .sort_values("_dt_parsed")
                           .reset_index(drop=True))
                grouped[time_col] = grouped["_bucket"]
                time_parsed = grouped["_dt_parsed"]
                grouped.drop(columns=["_bucket", "_dt_parsed"], inplace=True)

        if can_parse:
            grouped["_dt"] = time_parsed
            grouped["_year"] = grouped["_dt"].dt.year
            grouped["_month"] = grouped["_dt"].dt.month
        return grouped

    @staticmethod
    def calculate_yoy(
        df: pd.DataFrame,
        time_col: str,
        metric_col: str,
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """YoY（同比）：本月 / 去年同月 - 1"""
        grouped = GrowthCalculator.prepare_series(df, time_col, metric_col)
        m = metrics or BusinessMetrics(calculator="growth", algorithm="yoy",
                                        dimension=time_col, metric=metric_col)

        if "_dt" not in grouped.columns:
            m.growth_rates = [None] * len(grouped)
            m.growth_rate_label = "同比增长率（时间解析失败）"
            return m

        ym_map = {}
        for _, row in grouped.iterrows():
            ym_map[(row["_year"], row["_month"])] = row[metric_col]

        growth_rates = []
        for _, row in grouped.iterrows():
            prev_val = ym_map.get((row["_year"] - 1, row["_month"]))
            if prev_val and prev_val > 0:
                growth_rates.append(round(((row[metric_col] / prev_val) - 1) * 100, 2))
            else:
                growth_rates.append(None)

        m.growth_rates = growth_rates
        m.growth_rate_label = "同比增长率"
        m.labels = [str(v) for v in grouped[time_col].tolist()]
        m.values = [float(v) for v in grouped[metric_col].tolist()]

        valid = [g for g in growth_rates if g is not None]
        m.growth_rate_avg = round(sum(valid) / len(valid), 2) if valid else None

        return m

    @staticmethod
    def calculate_mom(
        df: pd.DataFrame,
        time_col: str,
        metric_col: str,
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """MoM（环比）：每个周期 vs 上一周期"""
        grouped = GrowthCalculator.prepare_series(df, time_col, metric_col)
        m = metrics or BusinessMetrics(calculator="growth", algorithm="mom",
                                        dimension=time_col, metric=metric_col)

        values = grouped[metric_col].tolist()
        growth_rates: List[Optional[float]] = [None]
        for i in range(1, len(values)):
            if values[i - 1] and values[i - 1] > 0:
                growth_rates.append(round(((values[i] / values[i - 1]) - 1) * 100, 2))
            else:
                growth_rates.append(None)

        m.growth_rates = growth_rates
        if "_dt" in grouped.columns and GrowthCalculator._can_parse_time(grouped):
            m.growth_rate_label = "环比变化率"
        else:
            # 退化为逐行变化
            m.growth_rate_label = "环比变化率（逐行对比）"

        m.labels = [str(v) for v in grouped[time_col].tolist()]
        m.values = [float(v) for v in grouped[metric_col].tolist()]

        valid = [g for g in growth_rates if g is not None]
        m.growth_rate_avg = round(sum(valid) / len(valid), 2) if valid else None

        return m

    @staticmethod
    def calculate_qoq(
        df: pd.DataFrame,
        time_col: str,
        metric_col: str,
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """QoQ（季环比）：本季度 vs 上季度"""
        grouped = GrowthCalculator.prepare_series(df, time_col, metric_col)
        m = metrics or BusinessMetrics(calculator="growth", algorithm="qoq",
                                        dimension=time_col, metric=metric_col)

        if "_dt" not in grouped.columns:
            m.growth_rates = [None] * len(grouped)
            m.growth_rate_label = "季环比变化率（时间解析失败）"
            return m

        grouped["_quarter"] = grouped["_dt"].dt.to_period("Q")
        quarterly = grouped.groupby("_quarter")[metric_col].sum().reset_index()
        quarterly = quarterly.sort_values("_quarter").reset_index(drop=True)

        vals = quarterly[metric_col].tolist()
        q_growth = [None]
        for i in range(1, len(vals)):
            if vals[i - 1] > 0:
                q_growth.append(round(((vals[i] / vals[i - 1]) - 1) * 100, 2))
            else:
                q_growth.append(None)

        # 映射回原始粒度
        growth_rates = []
        for _, row in grouped.iterrows():
            q_idx = quarterly[quarterly["_quarter"] == row["_dt"].to_period("Q")].index
            if len(q_idx) > 0 and q_idx[0] < len(q_growth):
                growth_rates.append(q_growth[q_idx[0]])
            else:
                growth_rates.append(None)

        m.growth_rates = growth_rates
        m.growth_rate_label = "季环比变化率"
        m.labels = [str(v) for v in grouped[time_col].tolist()]
        m.values = [float(v) for v in grouped[metric_col].tolist()]

        valid = [g for g in q_growth if g is not None]
        m.growth_rate_avg = round(sum(valid) / len(valid), 2) if valid else None

        return m

    @staticmethod
    def calculate_growth_rate(
        values: List[float],
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """通用增长率：逐行 pct_change（不依赖时间语义）"""
        m = metrics or BusinessMetrics(calculator="growth", algorithm="pct_change")
        m.values = values
        growth_rates: List[Optional[float]] = [None]
        for i in range(1, len(values)):
            if values[i - 1] and values[i - 1] != 0:
                growth_rates.append(round(((values[i] / values[i - 1]) - 1) * 100, 2))
            else:
                growth_rates.append(None)
        m.growth_rates = growth_rates
        m.growth_rate_label = "逐行变化率"
        valid = [g for g in growth_rates if g is not None]
        m.growth_rate_avg = round(sum(valid) / len(valid), 2) if valid else None
        return m

    @staticmethod
    def calculate_moving_average(
        values: List[float],
        window: int = 3,
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """移动平均：前 window 期的均值"""
        m = metrics or BusinessMetrics(calculator="growth", algorithm="moving_average")
        m.values = values
        mas: List[Optional[float]] = []
        for i in range(len(values)):
            start = max(0, i - window + 1)
            subset = values[start:i + 1]
            mas.append(round(sum(subset) / len(subset), 2))
        m.moving_averages = mas
        return m

    @staticmethod
    def calculate_cumulative_growth(
        values: List[float],
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """累计增长：累加求和"""
        m = metrics or BusinessMetrics(calculator="growth", algorithm="cumulative")
        m.values = values
        cumsum = []
        total = 0.0
        for v in values:
            total += v
            cumsum.append(round(total, 2))
        m.cumulative_values = cumsum
        return m

    @staticmethod
    def detect_trend_change_points(
        values: List[float],
        sensitivity: float = 0.3,
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """趋势拐点检测：识别增长率「方向发生反转」且幅度非噪声的点

        策略：遍历增长率序列，仅当相邻增长率发生符号翻转（正→负 或 负→正）
              且翻转两侧幅度均超过 sensitivity 阈值（默认 30%，过滤零附近的微小
              噪声）时，才记为拐点。单纯的加速 / 减速（同向变化）不算拐点，避免
              把噪声波动误判为趋势反转。
        """
        m = metrics or BusinessMetrics(calculator="growth", algorithm="trend_change")
        m.values = values

        if len(values) < 4:
            return m

        # 计算增长率
        rates: List[Optional[float]] = [None]
        for i in range(1, len(values)):
            if values[i - 1] and values[i - 1] != 0:
                rates.append((values[i] / values[i - 1]) - 1)
            else:
                rates.append(None)

        change_points = []
        for i in range(2, len(rates)):
            prev = rates[i - 1]
            curr = rates[i]
            if prev is None or curr is None:
                continue
            # 仅判定「方向反转」为拐点，且两侧幅度都需超过阈值（过滤噪声）
            flipped = (prev > 0 and curr < 0) or (prev < 0 and curr > 0)
            if flipped and abs(prev) >= sensitivity and abs(curr) >= sensitivity:
                change_points.append(i)

        m.trend_change_points = change_points
        return m

    # ========== 业务维度：分段贡献度与增长评估 ==========

    @staticmethod
    def calculate_segment_contribution(
        df: pd.DataFrame,
        time_col: str,
        metric_col: str,
        segment_col: str,
    ) -> Dict[str, float]:
        """分段增长贡献度：计算每个 segment 对总体增长的贡献百分比。

        方法：取时间序列最后两个可比较周期，总变化 = 末周期合计 - 前周期合计；
        各 segment 贡献 = (末周期该 segment 合计 - 前周期该 segment 合计) / 总变化 × 100。
        若总变化为 0，退化为按末周期占比。
        """
        if segment_col not in df.columns:
            return {}
        grouped = GrowthCalculator.prepare_series(df, time_col, metric_col)
        seg = df.groupby([time_col, segment_col])[metric_col].sum().reset_index()
        periods = list(dict.fromkeys(seg[time_col].tolist()))
        if len(periods) < 2:
            return {}
        last_p, prev_p = periods[-1], periods[-2]
        last_df = seg[seg[time_col] == last_p].set_index(segment_col)[metric_col]
        prev_df = seg[seg[time_col] == prev_p].set_index(segment_col)[metric_col]
        total_change = float(last_df.sum() - prev_df.sum())
        contribution: Dict[str, float] = {}
        if total_change != 0:
            for seg_name in set(last_df.index) | set(prev_df.index):
                lc = float(last_df.get(seg_name, 0) or 0)
                pc = float(prev_df.get(seg_name, 0) or 0)
                contribution[str(seg_name)] = round((lc - pc) / total_change * 100, 2)
        else:
            total_last = float(last_df.sum()) or 1.0
            for seg_name, v in last_df.items():
                contribution[str(seg_name)] = round(float(v) / total_last * 100, 2)
        return contribution

    @staticmethod
    def _assess_growth(m: BusinessMetrics, contribution: Dict[str, float]) -> Dict[str, Any]:
        """基于分段贡献度推导 来源 / 驱动 / 质量 / 风险 / 可持续性。"""
        if not contribution:
            return GrowthCalculator._assess_growth_aggregate(m)
        sorted_seg = sorted(contribution.items(), key=lambda kv: abs(kv[1]), reverse=True)
        top_seg, top_val = sorted_seg[0]
        top_abs = abs(top_val)
        positive = [s for s, v in contribution.items() if v > 0]
        if top_abs < 50 and len(positive) >= 2:
            quality = "高"
        elif top_abs < 70:
            quality = "中"
        else:
            quality = "低"
        if top_abs >= 60:
            risk = f"{top_seg}集中度过高，增长结构性脆弱"
        elif top_abs >= 40:
            risk = f"增长较依赖{top_seg}，存在一定集中度"
        else:
            risk = "增长来源较为分散，结构稳健"
        if quality == "高" and top_abs < 50:
            sustainability = "较好"
        elif top_abs >= 60:
            sustainability = "一般（高度依赖单一来源）"
        else:
            sustainability = "中等"
        return {
            "source": top_seg,
            "contribution": contribution,
            "top_contribution": round(top_abs, 2),
            "driver": f"{top_seg}驱动",
            "quality": quality,
            "risk": risk,
            "sustainability": sustainability,
            "positive_segments": positive,
        }

    @staticmethod
    def _assess_growth_aggregate(m: BusinessMetrics) -> Dict[str, Any]:
        """无分段维度时的聚合级评估（基于趋势稳定性）。"""
        n_cp = len(m.trend_change_points or [])
        n = len(m.values or [])
        # 用「拐点密度」而非绝对数量判定稳定性，避免序列长度不同导致误判
        # （日级 80 个伪拐点与月级 2 个真实拐点，密度才具可比性）
        density = (n_cp / (n - 1)) if n and n > 1 else 0.0
        stability = "高" if density <= 0.1 else ("中" if density <= 0.3 else "低")
        avg = m.growth_rate_avg or 0
        quality = "高" if (stability == "高" and abs(avg) < 50) else ("中" if stability != "低" else "低")
        return {
            "source": "全量（无可用分段维度）",
            "driver": "未知（缺少分类维度）",
            "quality": quality,
            "risk": f"趋势波动点 {n_cp} 个，稳定性{stability}",
            "sustainability": "中等" if stability != "低" else "一般",
            "contribution": {},
        }

    # ========== 便利方法：一站式计算 ==========

    @staticmethod
    def execute(
        df: pd.DataFrame,
        time_col: str,
        metric_col: str,
        algorithm: str = "mom",
        window: int = 3,
        segment_col: Optional[str] = None,
    ) -> BusinessMetrics:
        """一站式执行：根据算法计算完整的增长指标。

        当传入 segment_col 时，额外计算分段增长贡献度并写入
        m.business_assessment（来源/驱动/质量/风险/可持续性），
        作为业务级推理的原料。
        """
        grouped = GrowthCalculator.prepare_series(df, time_col, metric_col)
        values = [float(v) for v in grouped[metric_col].tolist()]

        # Step 1: 核心增长率
        if algorithm in ("yoy", "同比"):
            m = GrowthCalculator.calculate_yoy(df, time_col, metric_col)
        elif algorithm in ("qoq", "季环比"):
            m = GrowthCalculator.calculate_qoq(df, time_col, metric_col)
        else:
            m = GrowthCalculator.calculate_mom(df, time_col, metric_col)

        # Step 2: 累计增长
        m = GrowthCalculator.calculate_cumulative_growth(values, m)

        # Step 3: 移动平均
        m = GrowthCalculator.calculate_moving_average(values, window, m)

        # Step 4: 趋势拐点
        m = GrowthCalculator.detect_trend_change_points(values, metrics=m)

        # Step 5: 业务维度评估（业务级推理原料）
        if segment_col and segment_col in df.columns:
            contribution = GrowthCalculator.calculate_segment_contribution(
                df, time_col, metric_col, segment_col)
            m.business_assessment = GrowthCalculator._assess_growth(m, contribution)
        else:
            m.business_assessment = GrowthCalculator._assess_growth_aggregate(m)

        return m

    # ========== 内部工具 ==========

    @staticmethod
    def _can_parse_time(grouped: pd.DataFrame) -> bool:
        return "_dt" in grouped.columns