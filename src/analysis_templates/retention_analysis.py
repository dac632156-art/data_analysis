"""
复购分析模板 —— 客户重复购买行为分析（L3 业务分析）

V2 新增：识别客户复购率、产品复购排行
需要字段：客户ID + 订单日期 + 订单号（DERIVED_REQUIREMENTS）
"""

import pandas as pd
import numpy as np
from src.analysis_templates.base import (
    AnalysisTemplate, TemplateMeta, TemplateRuntime,
    KPIItem, TableData, ChartData,
)


class RetentionAnalysis(AnalysisTemplate):
    meta = TemplateMeta(
        analysis_type="retention_analysis",
        display_name="复购分析",
        version="2.0",
        description="分析客户复购率，识别重复购买客户占比和产品复购排行",
    )

    runtime = TemplateRuntime(
        REQUIRED_SCHEMA={
            "dimension_type": "category",
            "metric_type": "numeric",
            "min_dimension": 1,
            "min_metric": 1,
        },
        MIN_ROWS=3,
        # DERIVED_REQUIREMENTS 不再用精确列名匹配
        # 改为 can_run() 里用关键词模糊匹配
        DERIVED_REQUIREMENTS={},
        FALLBACK="ranking_analysis",
    )

    _cache: dict = {}

    def can_run(self, df: pd.DataFrame) -> bool:
        """关键词模糊匹配：三种模式均可运行
        模式A(raw)：有客户ID/订单列 → 从原始数据计算复购率
        模式B(precomputed)：有预计算的复购率列 → 直接按维度分析复购率
        模式C(count_only)：有客户数量列 → 按维度分析客户数量分布
        """
        # 1. 基本条件：需要分类列 + 数值列
        if not self._has_category_column(df):
            return False
        if len(self._get_numeric_columns(df)) < 1:
            return False
        if len(df) < self.runtime.MIN_ROWS:
            return False

        cols = df.columns.tolist()
        # 模式A：原始客户/订单数据（必须是ID类，不含"数量"/"数"/"count"等聚合词）
        customer_id_keywords = ["客户id", "customer_id", "用户id", "user_id", "会员id", "member_id", "买家id", "buyer_id"]
        has_customer_id = any(any(kw in str(c).lower() for kw in customer_id_keywords) for c in cols)
        # 也匹配单独的"客户"/"customer"列，但排除聚合列
        for c in cols:
            cl = str(c).lower()
            if any(kw in cl for kw in ["客户", "customer"]) and not any(kw in cl for kw in ["数量", "数", "count", "总量", "人数", "total"]):
                has_customer_id = True

        # 模式B：预计算的复购率列
        retention_keywords = ["复购率", "retention", "回购率", "重复购买率", "repeat_rate", "retention_rate"]
        has_retention_col = any(any(kw in str(c).lower() for kw in retention_keywords) for c in cols)

        # 模式C：客户数量列
        cust_count_keywords = ["客户数量", "客户数", "customer_count", "客户总量"]
        has_cust_count = any(any(kw in str(c).lower() for kw in cust_count_keywords) for c in cols)

        return has_customer_id or has_retention_col or has_cust_count

    def _detect_mode_and_columns(self, df: pd.DataFrame):
        """检测运行模式和相关列"""
        cols = df.columns.tolist()

        # 客户ID
        customer_keywords = ["客户id", "customer_id", "customer", "客户", "用户id", "user_id", "会员id", "member_id"]
        customer_col = next((c for c in cols if any(kw in str(c).lower() for kw in customer_keywords)), None)

        # 订单日期
        date_keywords = ["订单日期", "order_date", "购买日期", "日期", "date", "time"]
        date_col = next((c for c in cols if any(kw in str(c).lower() for kw in date_keywords)), None)

        # 订单号
        order_keywords = ["订单号", "order_id", "订单id", "订单编号"]
        order_col = next((c for c in cols if any(kw in str(c).lower() for kw in order_keywords)), None)

        # 复购率列（预计算）
        retention_keywords = ["复购率", "retention", "回购率", "重复购买率", "repeat_rate", "retention_rate"]
        retention_col = next((c for c in cols if any(kw in str(c).lower() for kw in retention_keywords)), None)

        # 客户数量列
        cust_count_keywords = ["客户数量", "客户数", "customer_count", "客户总量"]
        cust_count_col = next((c for c in cols if any(kw in str(c).lower() for kw in cust_count_keywords) for c in cols), None)

        # 确定模式
        if customer_col:
            mode = "raw"
        elif retention_col:
            mode = "precomputed"
        elif cust_count_col:
            mode = "count_only"
        else:
            mode = "none"

        return mode, customer_col, date_col, order_col, retention_col, cust_count_col

    def _compute(self, df, metric):
        mode, customer_col, date_col, order_col, retention_col, cust_count_col = \
            self._detect_mode_and_columns(df)
        self._cache["mode"] = mode

        # ===== 模式B：预计算的复购率列（最常见场景） =====
        if mode == "precomputed":
            cat_cols = self.classifier.get_category_columns(df)
            dimension = cat_cols[0] if cat_cols else None

            if dimension and retention_col:
                # 按维度分组分析复购率
                grouped = df.groupby(dimension)[retention_col].agg(['mean', 'min', 'max', 'count']).reset_index()
                grouped = grouped.sort_values('mean', ascending=False)
                self._cache["grouped"] = grouped
                self._cache["dimension"] = dimension
                self._cache["retention_col"] = retention_col
                self._cache["overall_rate"] = df[retention_col].mean()
                self._cache["total_rows"] = len(df)
                return

        # ===== 模式C：有客户数量列（无复购率列） =====
        if mode == "count_only" and cust_count_col:
            cat_cols = self.classifier.get_category_columns(df)
            dimension = cat_cols[0] if cat_cols else None
            num_cols = self._get_numeric_columns(df)
            metric_col = num_cols[0] if num_cols else None

            if dimension:
                # 按维度汇总客户数量和核心指标
                agg_dict = {cust_count_col: 'sum'}
                if metric_col:
                    agg_dict[metric_col] = 'sum'
                grouped = df.groupby(dimension).agg(agg_dict).reset_index()
                grouped = grouped.sort_values(cust_count_col, ascending=False)
                # 计算人均指标
                if metric_col:
                    grouped[f'人均{metric_col}'] = grouped[metric_col] / grouped[cust_count_col]
                self._cache["grouped"] = grouped
                self._cache["dimension"] = dimension
                self._cache["cust_count_col"] = cust_count_col
                self._cache["metric_col"] = metric_col
                self._cache["total_customers"] = df[cust_count_col].sum()
                return

        # ===== 模式A：原始客户/订单数据 =====
        if mode == "raw" and customer_col:
            # 按客户统计购买次数
            if order_col:
                purchase_counts = df.groupby(customer_col)[order_col].nunique()
            else:
                purchase_counts = df.groupby(customer_col).size()

            total_customers = len(purchase_counts)
            repeat_customers = (purchase_counts >= 2).sum()
            retention_rate = (repeat_customers / total_customers * 100) if total_customers > 0 else 0
            avg_freq = purchase_counts.mean()

            # 按产品维度统计复购率
            product_keywords = ["产品", "product", "商品", "品类", "类别", "item", "goods"]
            product_col = next((c for c in df.columns if any(kw in str(c).lower() for kw in product_keywords)), None)

            product_retention = None
            if product_col:
                product_stats = []
                for prod in df[product_col].unique():
                    prod_df = df[df[product_col] == prod]
                    prod_customers = prod_df[customer_col].nunique()
                    if order_col:
                        prod_repeat = (prod_df.groupby(customer_col)[order_col].nunique() >= 2).sum()
                    else:
                        prod_repeat = (prod_df.groupby(customer_col).size() >= 2).sum()
                    prod_rate = (prod_repeat / prod_customers * 100) if prod_customers > 0 else 0
                    product_stats.append({
                        product_col: str(prod),
                        "复购客户数": int(prod_repeat),
                        "总客户数": int(prod_customers),
                        "复购率": round(prod_rate, 1),
                    })
                product_retention = pd.DataFrame(product_stats).sort_values("复购率", ascending=False)

            freq_dist = purchase_counts.value_counts().sort_index()
            freq_rows = [[int(freq), int(cnt)] for freq, cnt in freq_dist.items()]

            self._cache["total_customers"] = total_customers
            self._cache["repeat_customers"] = repeat_customers
            self._cache["retention_rate"] = retention_rate
            self._cache["avg_freq"] = avg_freq
            self._cache["purchase_counts"] = purchase_counts
            self._cache["customer_col"] = customer_col
            self._cache["product_retention"] = product_retention
            self._cache["product_col"] = product_col
            self._cache["freq_rows"] = freq_rows
            return

        # 无法运行
        self._cache["error"] = "数据中未找到客户ID、复购率或客户数量相关列"

    def build_kpis(self, df, dimension, metric, algorithm):
        metric = metric or self._get_numeric_columns(df)[0]
        self._compute(df, metric)

        if self._cache.get("error"):
            return [KPIItem(label="错误", value=self._cache["error"], change="", kpi_type="rate")]

        mode = self._cache.get("mode", "none")

        if mode == "precomputed":
            overall = self._cache.get("overall_rate", 0)
            return [
                KPIItem(label="平均复购率", value=f"{overall:.1%}", change="", kpi_type="rate"),
                KPIItem(label="数据行数", value=str(self._cache.get("total_rows", 0)), change="", kpi_type="count"),
            ]

        if mode == "count_only":
            return [
                KPIItem(label="总客户数", value=str(int(self._cache.get("total_customers", 0))), change="", kpi_type="count"),
            ]

        # mode == "raw"
        rate = self._cache.get("retention_rate", 0)
        return [
            KPIItem(label="复购率", value=f"{rate:.1f}%", change="", kpi_type="rate"),
            KPIItem(label="复购客户数", value=str(self._cache.get("repeat_customers", 0)), change="", kpi_type="count"),
            KPIItem(label="总客户数", value=str(self._cache.get("total_customers", 0)), change="", kpi_type="count"),
            KPIItem(label="人均购买次数", value=f"{self._cache.get('avg_freq', 0):.1f}", change="", kpi_type="avg"),
        ]

    def build_tables(self, df, dimension, metric, algorithm):
        if self._cache.get("error"):
            return []

        mode = self._cache.get("mode", "none")
        tables = []

        if mode == "precomputed":
            grouped = self._cache.get("grouped")
            dimension = self._cache.get("dimension", "")
            retention_col = self._cache.get("retention_col", "复购率")
            if grouped is not None:
                rows = [[str(row[dimension]), f"{row['mean']:.2%}", f"{row['min']:.2%}", f"{row['max']:.2%}"]
                        for _, row in grouped.iterrows()]
                tables.append(TableData(
                    title=f"各{dimension}复购率",
                    table_type="ranking",
                    columns=[dimension, "平均复购率", "最低复购率", "最高复购率"],
                    rows=rows,
                ))

        elif mode == "count_only":
            grouped = self._cache.get("grouped")
            dimension = self._cache.get("dimension", "")
            cust_count_col = self._cache.get("cust_count_col", "客户数量")
            metric_col = self._cache.get("metric_col")
            if grouped is not None:
                cols = [dimension, cust_count_col]
                if metric_col:
                    cols.append(metric_col)
                    per_capita_col = f'人均{metric_col}'
                    if per_capita_col in grouped.columns:
                        cols.append(per_capita_col)
                rows = [[str(row[c]) for c in cols] for _, row in grouped.iterrows()]
                tables.append(TableData(
                    title=f"各{dimension}客户数量",
                    table_type="ranking",
                    columns=cols,
                    rows=rows,
                ))

        else:
            # mode == "raw"
            freq_rows = self._cache.get("freq_rows", [])
            if freq_rows:
                tables.append(TableData(
                    title="客户购买频次分布",
                    table_type="summary",
                    columns=["购买次数", "客户数"],
                    rows=freq_rows,
                ))

            product_retention = self._cache.get("product_retention")
            if product_retention is not None and len(product_retention) > 0:
                product_col = self._cache.get("product_col", "产品")
                rows = [[str(row[product_col]), int(row["复购客户数"]),
                        int(row["总客户数"]), f"{row['复购率']}%"]
                        for _, row in product_retention.iterrows()]
                tables.append(TableData(
                    title="产品复购率排行",
                    table_type="ranking",
                    columns=["产品", "复购客户数", "总客户数", "复购率(%)"],
                    rows=rows,
                ))

        return tables

    def build_charts(self, df, dimension, metric, algorithm):
        if self._cache.get("error"):
            return []

        mode = self._cache.get("mode", "none")
        chart_data_list = []

        if mode == "precomputed":
            grouped = self._cache.get("grouped")
            dimension = self._cache.get("dimension", "")
            retention_col = self._cache.get("retention_col", "复购率")
            if grouped is not None:
                # 按维度的复购率柱状图
                chart_data_list.append(ChartData(
                    slot="retention_by_dim", chart_type="bar",
                    title=f"各{dimension}复购率对比",
                    x=dimension, y="平均复购率",
                    data=[{"x": str(row[dimension]), "y": round(row['mean'] * 100, 1)}
                          for _, row in grouped.iterrows()],
                ))

        elif mode == "count_only":
            grouped = self._cache.get("grouped")
            dimension = self._cache.get("dimension", "")
            cust_count_col = self._cache.get("cust_count_col", "客户数量")
            if grouped is not None:
                chart_data_list.append(ChartData(
                    slot="cust_count_by_dim", chart_type="bar",
                    title=f"各{dimension}客户数量对比",
                    x=dimension, y=cust_count_col,
                    data=[{"x": str(row[dimension]), "y": int(row[cust_count_col])}
                          for _, row in grouped.iterrows()],
                ))

        else:
            # mode == "raw"
            total = self._cache.get("total_customers", 0)
            repeat = self._cache.get("repeat_customers", 0)
            if total > 0:
                chart_data_list.append(ChartData(
                    slot="retention_pie", chart_type="pie",
                    title="复购客户占比",
                    x="客户类型", y="数量",
                    data=[
                        {"x": "复购客户", "y": repeat},
                        {"x": "单次购买客户", "y": total - repeat},
                    ],
                ))

            product_retention = self._cache.get("product_retention")
            if product_retention is not None and len(product_retention) > 0:
                product_col = self._cache.get("product_col", "产品")
                chart_data_list.append(ChartData(
                    slot="product_retention_bar", chart_type="bar",
                    title="各产品复购率对比",
                    x=product_col, y="复购率",
                    data=[{"x": str(row[product_col]), "y": row["复购率"]}
                          for _, row in product_retention.iterrows()],
                ))

        return chart_data_list

    def build_insights(self, df, dimension, metric, algorithm, kpis, chart_data):
        if self._cache.get("error"):
            return [self._cache["error"]]

        mode = self._cache.get("mode", "none")

        if mode == "precomputed":
            overall = self._cache.get("overall_rate", 0)
            grouped = self._cache.get("grouped")
            dimension = self._cache.get("dimension", "")
            insights = [f"整体平均复购率为 {overall:.1%}"]
            if grouped is not None and len(grouped) > 0:
                top = grouped.iloc[0]
                bottom = grouped.iloc[-1]
                insights.append(f"「{top[dimension]}」复购率最高（{top['mean']:.1%}）")
                insights.append(f"「{bottom[dimension]}」复购率最低（{bottom['mean']:.1%}）")
                if overall > 0.4:
                    insights.append("复购率较高（>40%），客户忠诚度良好")
                elif overall > 0.2:
                    insights.append("复购率处于中等水平，有提升空间")
                else:
                    insights.append("复购率偏低（<20%），建议加强客户留存策略")
            return insights

        if mode == "count_only":
            grouped = self._cache.get("grouped")
            dimension = self._cache.get("dimension", "")
            total_cust = self._cache.get("total_customers", 0)
            insights = [f"总计 {int(total_cust)} 名客户"]
            if grouped is not None and len(grouped) > 0:
                top = grouped.iloc[0]
                insights.append(f"「{top[dimension]}」客户最多（{int(top[grouped.columns[1]])}）")
            return insights

        # mode == "raw"
        rate = self._cache.get("retention_rate", 0)
        total = self._cache.get("total_customers", 0)
        repeat = self._cache.get("repeat_customers", 0)
        avg_freq = self._cache.get("avg_freq", 0)

        insights = [
            f"整体复购率为 {rate:.1f}%，共 {total} 名客户中有 {repeat} 名为复购客户",
            f"客户平均购买 {avg_freq:.1f} 次",
        ]

        if rate > 40:
            insights.append("复购率较高（>40%），客户忠诚度良好")
        elif rate > 20:
            insights.append("复购率处于中等水平，有提升空间")
        else:
            insights.append("复购率偏低（<20%），建议加强客户留存策略")

        product_retention = self._cache.get("product_retention")
        if product_retention is not None and len(product_retention) > 0:
            top_product = product_retention.iloc[0]
            product_col = self._cache["product_col"]
            insights.append(
                f"「{top_product[product_col]}」复购率最高（{top_product['复购率']}%），"
                f"可作为引流产品重点推广"
            )

        return insights

    def build_conclusion(self, df, dimension, metric, algorithm, insights):
        mode = self._cache.get("mode", "none")

        if mode == "precomputed":
            overall = self._cache.get("overall_rate", 0)
            if overall > 0.4:
                return ["客户忠诚度较高，复购表现良好，建议关注高复购维度的持续优化"]
            elif overall > 0.2:
                return ["复购率有提升空间，建议通过会员体系和精准营销提高客户回购意愿"]
            return ["复购率较低，需重点关注客户留存策略，分析流失原因并采取挽回措施"]

        if mode == "count_only":
            return ["基于客户数量分布，建议重点关注客户量大的维度，同时探索客户粘性提升方案"]

        # mode == "raw"
        rate = self._cache.get("retention_rate", 0)
        if rate > 40:
            return ["客户忠诚度较高，复购表现良好，建议关注高复购产品的持续供应"]
        elif rate > 20:
            return ["复购率有提升空间，建议通过会员体系和精准营销提高客户回购意愿"]
        return ["复购率较低，需重点关注客户留存策略，分析流失原因并采取挽回措施"]

    def execute(self, df, dimension, metric, algorithm=None):
        metric = metric or self._get_numeric_columns(df)[0]
        self._cache = {}
        self._compute(df, metric)
        return super().execute(df, dimension, metric, algorithm)
