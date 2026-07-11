"""
RetentionCalculator —— 复购/留存分析业务计算引擎

支持：复购率、重复购买客户数、平均购买频次

输入要求：客户ID列 + 订单号/日期列（用于判断多次购买）
"""

import pandas as pd
from typing import Optional, Dict, Any
from src.calculators.base import BusinessMetrics


class RetentionCalculator:
    """复购分析业务计算引擎

    使用方式：
        calc = RetentionCalculator()
        metrics = calc.calculate_repeat_purchase_rate(df, customer_col, order_col)
        metrics = calc.calculate_avg_purchase_frequency(metrics, df, customer_col, order_col)
    """

    @staticmethod
    def _identify_columns(df: pd.DataFrame) -> dict:
        """自动识别客户ID列和订单列"""
        cols = [str(c).lower() for c in df.columns]
        orig_cols = list(df.columns)

        customer_kw = ["客户id", "customer_id", "customer", "客户",
                       "用户id", "user_id", "会员id", "member_id", "买家id", "buyer_id"]
        order_kw = ["订单号", "order_id", "orderid", "订单编号", "交易号",
                    "transaction_id", "订单id"]

        customer_col = None
        for kw in customer_kw:
            for i, c in enumerate(cols):
                if kw in c:
                    if any(ex in c for ex in ["数量", "数", "count", "总量", "total"]):
                        continue
                    customer_col = orig_cols[i]
                    break
            if customer_col:
                break

        order_col = None
        for kw in order_kw:
            for i, c in enumerate(cols):
                if kw in c:
                    order_col = orig_cols[i]
                    break
            if order_col:
                break

        # 降级匹配
        if customer_col is None:
            for i, c in enumerate(cols):
                if "客户" in c or "customer" in c:
                    if not any(kw in c for kw in ["数量", "数", "count", "总量", "total"]):
                        customer_col = orig_cols[i]
                        break

        return {"customer_col": customer_col, "order_col": order_col}

    @staticmethod
    def calculate_repeat_purchase_rate(
        df: pd.DataFrame,
        customer_col: Optional[str] = None,
        order_col: Optional[str] = None,
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """复购率：购买次数 ≥ 2 的客户占比"""
        m = metrics or BusinessMetrics(calculator="retention")

        if customer_col is None or order_col is None:
            identified = RetentionCalculator._identify_columns(df)
            customer_col = customer_col or identified["customer_col"]
            order_col = order_col or identified["order_col"]

        if customer_col is None:
            m.extra["error"] = "未找到客户ID列"
            return m

        m.dimension = customer_col
        if order_col:
            m.metric = order_col

        # 按客户统计购买次数
        order_count_col = order_col or customer_col
        cust_orders = df.groupby(customer_col)[order_count_col].nunique().reset_index(name="order_count")
        cust_orders.columns = ["customer", "order_count"]

        total_cust = len(cust_orders)
        repeat_cust = int((cust_orders["order_count"] >= 2).sum())

        m.total_customer_count = total_cust
        m.repeat_customer_count = repeat_cust
        if total_cust > 0:
            m.repeat_purchase_rate = round(repeat_cust / total_cust, 4)

        m.values = [float(v) for v in cust_orders["order_count"].tolist()]
        m.labels = [str(v) for v in cust_orders["customer"].tolist()]

        return m

    @staticmethod
    def calculate_avg_purchase_frequency(
        df: pd.DataFrame,
        customer_col: Optional[str] = None,
        order_col: Optional[str] = None,
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """平均购买频次"""
        m = metrics or BusinessMetrics(calculator="retention")

        if customer_col is None:
            identified = RetentionCalculator._identify_columns(df)
            customer_col = customer_col or identified["customer_col"]
            order_col = order_col or identified["order_col"]

        if customer_col is None:
            return m

        order_count_col = order_col or customer_col
        cust_orders = df.groupby(customer_col)[order_count_col].nunique()

        m.avg_purchase_frequency = round(float(cust_orders.mean()), 2)
        m.total_customer_count = m.total_customer_count or len(cust_orders)
        return m

    @staticmethod
    def calculate_repeat_customer_count(
        df: pd.DataFrame,
        customer_col: Optional[str] = None,
        order_col: Optional[str] = None,
        metrics: Optional[BusinessMetrics] = None,
    ) -> BusinessMetrics:
        """独立计算复购客户数（不覆盖其他字段）"""
        m = metrics or BusinessMetrics(calculator="retention")
        if customer_col is None:
            identified = RetentionCalculator._identify_columns(df)
            customer_col = customer_col or identified["customer_col"]

        if customer_col is None:
            return m

        order_count_col = order_col or customer_col
        cust_orders = df.groupby(customer_col)[order_count_col].nunique()

        m.total_customer_count = len(cust_orders)
        m.repeat_customer_count = int((cust_orders >= 2).sum())
        if m.total_customer_count > 0:
            m.repeat_purchase_rate = round(m.repeat_customer_count / m.total_customer_count, 4)
        return m

    @staticmethod
    def _identify_value_col(df: pd.DataFrame) -> Optional[str]:
        """自动识别金额/收入类价值列（用于计算复购客户收入贡献）"""
        cols = [str(c).lower() for c in df.columns]
        orig = list(df.columns)
        for kw in ["销售金额", "销售额", "金额", "收入", "利润", "revenue",
                   "amount", "sales", "profit", "gmv"]:
            for i, c in enumerate(cols):
                if kw in c:
                    return orig[i]
        return None

    @staticmethod
    def _assess_retention(
        df: pd.DataFrame,
        m: BusinessMetrics,
        customer_col: Optional[str],
        order_col: Optional[str],
        value_col: Optional[str] = None,
    ) -> Dict[str, Any]:
        """基于复购结构推导 忠诚客户比例 / 收入贡献 / 质量 / 风险。"""
        if customer_col is None:
            return {}
        order_col = order_col or customer_col
        value_col = value_col or RetentionCalculator._identify_value_col(df)
        grp = df.groupby(customer_col)
        order_counts = grp[order_col].nunique() if order_col in df.columns else grp.size()
        total = len(order_counts)
        if total == 0:
            return {}
        repeat = int((order_counts >= 2).sum())
        loyalty = int((order_counts >= 3).sum())
        loyalty_rate = round(loyalty / total, 4)
        repeat_rate = m.repeat_purchase_rate or round(repeat / total, 4)

        repeat_value_share = None
        if value_col and value_col in df.columns:
            cust_val = df.groupby(customer_col)[value_col].sum()
            repeat_mask = order_counts >= 2
            total_value = float(cust_val.sum())
            repeat_value = float(cust_val[repeat_mask].sum())
            repeat_value_share = round(repeat_value / total_value, 4) if total_value else None

        if repeat_rate >= 0.4 and loyalty_rate >= 0.15:
            quality = "高"
        elif repeat_rate >= 0.2:
            quality = "中"
        else:
            quality = "低"

        if repeat_rate < 0.2:
            risk = "复购率偏低，客户流失/黏性不足风险高"
        elif repeat_value_share is not None and repeat_value_share > 0.7:
            risk = "收入高度依赖少数复购客户，集中度风险"
        else:
            risk = "客户结构相对健康"

        return {
            "repeat_rate": repeat_rate,
            "loyalty_rate": loyalty_rate,
            "repeat_value_share": repeat_value_share,
            "quality": quality,
            "risk": risk,
        }

    @staticmethod
    def _identify_precalculated(df: pd.DataFrame) -> dict:
        """识别已聚合数据中的现成指标列（复购率 / 客户数量）。

        许多业务数据是「按 地区×月份 聚合」后的汇总表，直接带有 复购率、客户数量
        等列，而非交易明细（无 customer_id / order_id）。此时应从这些现成列读取，
        而不是因找不到明细列而把复购率降级为 0 / N/A。
        """
        rate_col = None
        cust_col = None
        for col in df.columns:
            cl = str(col).lower()
            # 复购率：命中「复购率 / 回购率 / repurchase_rate」，排除「复购客户数」等
            if rate_col is None:
                if ("复购率" in cl or "回购率" in cl or "repurchase_rate" in cl
                        or ("repurchase" in cl and "rate" in cl)):
                    rate_col = col
            # 客户数量：命中「客户数量 / 客户数 / 总客户数 / customer_count」等
            if cust_col is None:
                if any(k in cl for k in ["客户数量", "客户数", "总客户数",
                                         "客户总数", "customer_count", "customer number"]):
                    cust_col = col
        return {"rate_col": rate_col, "customer_count_col": cust_col}

    @staticmethod
    def _compute_from_precalculated(df: pd.DataFrame, pre: dict,
                                    value_col: Optional[str] = None) -> BusinessMetrics:
        """预聚合模式：直接从现成指标列读取复购率 / 客户规模。

        聚合数据无法还原客户级复购分布，因此：
        - 复购率 = 复购率列的均值（整体水平）
        - 总客户数 = 客户数量列的均值（代表性客户规模）
        - 复购客户数 = round(复购率 × 总客户数)
        """
        m = BusinessMetrics(calculator="retention")
        rate_col = pre.get("rate_col")
        cust_col = pre.get("customer_count_col")

        if rate_col and rate_col in df.columns:
            vals = pd.to_numeric(df[rate_col], errors="coerce").dropna()
            if len(vals):
                m.repeat_purchase_rate = round(float(vals.mean()), 4)
                m.values = [float(v) for v in vals.tolist()]
                m.labels = [str(v) for v in df.index.tolist()]

        if cust_col and cust_col in df.columns:
            vals = pd.to_numeric(df[cust_col], errors="coerce").dropna()
            if len(vals):
                m.total_customer_count = int(round(float(vals.mean())))

        if m.repeat_purchase_rate is not None and m.total_customer_count:
            m.repeat_customer_count = int(round(m.repeat_purchase_rate * m.total_customer_count))

        # 业务评估（无明细，基于整体复购率直接判定质量/风险）
        rate = m.repeat_purchase_rate
        if rate is not None:
            quality = "高" if rate >= 0.4 else ("中" if rate >= 0.2 else "低")
            risk = ("复购率偏低，客户黏性不足风险高" if rate < 0.2
                    else "客户结构相对健康")
            m.business_assessment = {
                "repeat_rate": rate,
                "loyalty_rate": None,
                "repeat_value_share": None,
                "quality": quality,
                "risk": risk,
            }

        m.dimension = cust_col or rate_col
        m.metric = rate_col or cust_col
        return m

    @staticmethod
    def execute(
        df: pd.DataFrame,
        customer_col: Optional[str] = None,
        order_col: Optional[str] = None,
        value_col: Optional[str] = None,
    ) -> BusinessMetrics:
        """一站式执行（含业务维度评估）

        优先尝试从预聚合的现成指标列（复购率 / 客户数量）读取；
        找不到时回退到基于 customer_id / order_id 明细的复购计算。
        """
        if customer_col is None:
            pre = RetentionCalculator._identify_precalculated(df)
            if pre.get("rate_col") or pre.get("customer_count_col"):
                return RetentionCalculator._compute_from_precalculated(df, pre, value_col)

        m = RetentionCalculator.calculate_repeat_purchase_rate(df, customer_col, order_col)
        m = RetentionCalculator.calculate_avg_purchase_frequency(df, customer_col, order_col, m)
        m.business_assessment = RetentionCalculator._assess_retention(
            df, m, m.dimension, m.metric, value_col)
        return m