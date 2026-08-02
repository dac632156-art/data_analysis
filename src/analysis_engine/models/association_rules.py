"""商品关联规则（购物篮分析）模型。

从订单明细中挖掘哪些商品经常被一起购买，计算双向关联规则的
Support（支持度）/ Confidence（置信度）/ Lift（提升度），并支持三个可选进阶：
  - A：有商品类目列时，把粒度从具体商品改写为品类维度
  - B：有毛利/单价列时，给规则挂载平均毛利与总收入
  - C：消费上游 RFM / K-means 分层结果，按用户ID join 后按客群切分重算并打 Action 标签

设计约束（与用户确认）：
  - 核心列（订单ID、商品ID）硬匹配双保险，未命中即坚决不分析
  - 模型本体与 RFM 无关；仅进阶 C 依赖上游 `rfm_user_segmentation`
  - C 触发条件 = 上游分层存在 且 订单含 用户ID；缺失则 base 照常跑、C 坚决不做并说明
"""

from collections import Counter
from dataclasses import dataclass
from itertools import combinations

import pandas as pd

from src.analysis_templates.base import (
    AnalysisPackage,
    ChartData,
    KPIItem,
    TableData,
)
from src.analysis_engine.base import AnalysisModel
from src.analysis_engine.registry import register_model


# --------------------------------------------------------------------------
# 列归一化（中英文别名 → 标准中文列名，沿用 cohort 风格）
# --------------------------------------------------------------------------
COLUMN_ALIASES = {
    "订单ID": ["订单id", "订单号", "订单编号", "交易id", "交易号", "order_id", "orderid", "order no", "order_no", "transaction_id", "tid"],
    "商品ID": ["商品id", "货号", "产品id", "sku", "skuid", "item_id", "itemid", "product_id", "productid", "goods_id", "goodsid"],
    "商品类目": ["品类", "类目", "类别", "商品类别", "category", "cat", "cate", "item_category", "product_category", "type"],
    "商品毛利": ["毛利", "利润", "边际利润", "margin", "profit", "gross_margin"],
    "商品单价": ["单价", "价格", "售价", "price", "unit_price", "sale_price"],
    "折扣金额": ["折扣", "优惠", "discount", "discount_amount", "coupon"],
    "数量": ["件数", "购买数量", "qty", "quantity", "count", "num", "amount"],
    "用户ID": ["用户id", "会员id", "客户id", "买家id", "userid", "uid", "member_id", "memberid", "customer_id", "buyer_id"],
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """按 COLUMN_ALIASES 把英文/异名列名归一为标准中文列名（不修改原表）。"""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    lower_map = {c.lower(): c for c in df.columns}
    rename = {}
    for std, aliases in COLUMN_ALIASES.items():
        if std in df.columns:
            continue
        for alias in aliases:
            if alias in df.columns:
                rename[alias] = std
                break
            if alias.lower() in lower_map:
                rename[lower_map[alias.lower()]] = std
                break
    if rename:
        df = df.rename(columns=rename)
    return df


def _has_cols(df: pd.DataFrame, cols) -> bool:
    return all(c in df.columns for c in cols)


# --------------------------------------------------------------------------
# 配置
# --------------------------------------------------------------------------
@dataclass
class ARConfig:
    min_support: float = 0.01   # 候选单品 / 候选对的最小支持度阈值
    top_n: int = 100            # 输出规则数量上限（按 Lift 降序）
    chart_top: int = 15         # 图表展示 Top 规则数


CFG = ARConfig()


# --------------------------------------------------------------------------
# 购物篮构建 + 规则矩阵计算（确定性算法，无 LLM）
# --------------------------------------------------------------------------
def _build_baskets(work: pd.DataFrame, item_col: str):
    """按 订单ID 聚合出购物篮（商品集合）。返回 list[frozenset[str]]。"""
    if "订单ID" not in work.columns or item_col not in work.columns:
        return []
    grouped = work.groupby("订单ID")[item_col].apply(
        lambda s: frozenset(str(v) for v in s.dropna())
    )
    baskets = [b for b in grouped.tolist() if b]
    return baskets


def _compute_rules(baskets, n_baskets: int, min_support: float, top_n: int):
    """从购物篮计算双向关联规则，返回原始数值规则列表（按 Lift 降序截断）。

    每条规则：{antecedent, consequent, support, confidence, lift}
    - support(X→Y) = P(X∪Y) = 共现篮子数 / 总篮子数
    - confidence(X→Y) = P(X∪Y) / P(X)
    - lift(X→Y) = P(X∪Y) / (P(X)·P(Y))
    """
    if n_baskets == 0:
        return []

    # 1) 单品支持度，过滤候选单品（候选对阶段已消除分母为 0 的风险）
    item_counts: Counter = Counter()
    for b in baskets:
        item_counts.update(b)
    freq_items = {it: c for it, c in item_counts.items() if c / n_baskets >= min_support}
    item_support = {it: c / n_baskets for it, c in freq_items.items()}

    # 2) 只对候选单品算 pair 计数，避免全量 O(n^2)
    pair_counts: Counter = Counter()
    for b in baskets:
        its = sorted(it for it in b if it in freq_items)
        for x, y in combinations(its, 2):
            pair_counts[frozenset((x, y))] += 1

    # 3) 计算双向规则
    rules = []
    for pair, cnt in pair_counts.items():
        x, y = sorted(pair)
        supp_xy = cnt / n_baskets
        if supp_xy < min_support:
            continue
        sx = item_support[x]
        sy = item_support[y]
        conf_xy = supp_xy / sx if sx > 0 else 0.0
        conf_yx = supp_xy / sy if sy > 0 else 0.0
        lift = supp_xy / (sx * sy) if (sx * sy) > 0 else 0.0
        rules.append({"antecedent": x, "consequent": y,
                      "support": supp_xy, "confidence": conf_xy, "lift": lift,
                      "count": cnt})
        rules.append({"antecedent": y, "consequent": x,
                      "support": supp_xy, "confidence": conf_yx, "lift": lift,
                      "count": cnt})

    rules.sort(key=lambda r: r["lift"], reverse=True)
    return rules[:top_n]


# --------------------------------------------------------------------------
# 空包（核心列缺失等，防御性双保险）
# --------------------------------------------------------------------------
def _empty_package(reason: str, suggestion: str) -> AnalysisPackage:
    return AnalysisPackage(
        id="association_rules",
        analysis_type="association_rules",
        business_question="哪些商品经常被一起购买？",
        algorithm="association_rules_v1",
        dimension="商品",
        metric="关联规则",
        can_run=False,
        kpis=[],
        chart_data=[],
        tables=[],
        findings=[],
        insights=[f"分析未执行：{reason}"],
        suggestion=suggestion,
        confidence=0.0,
    )


# --------------------------------------------------------------------------
# 格式化辅助
# --------------------------------------------------------------------------
def _pct(v: float) -> str:
    return f"{v * 100:.2f}%"


def _base_table_rows(rules):
    rows = []
    for r in rules:
        row = {
            "前项": r["antecedent"],
            "后项": r["consequent"],
            "支持度": _pct(r["support"]),
            "置信度": _pct(r["confidence"]),
            "提升度": round(r["lift"], 3),
        }
        if "avg_margin" in r:
            row["平均毛利"] = round(r["avg_margin"], 2)
            row["总收入"] = round(r["total_revenue"], 2)
        rows.append(row)
    return rows


def _significant_dedup(rules, min_lift: float = 1.0):
    """从双向规则列表中按 pair 去重为单边，并过滤出显著规则(lift > min_lift)。

    返回按共现次数降序的显著单边规则（每对仅保留一次，避免 A→B 与 B→A 重复）。
    """
    seen = set()
    out = []
    for r in rules:
        key = frozenset((r["antecedent"], r["consequent"]))
        if key in seen:
            continue
        seen.add(key)
        if r["lift"] <= min_lift:
            continue
        out.append(r)
    out.sort(key=lambda r: r.get("count", 0), reverse=True)
    return out


def _cooccurrence_graph_chart(slot: str, title: str, rules, top: int = 40) -> ChartData:
    """构造关系网络图 ChartData：每行是一条商品对连线。

    数据行键：source(商品A), target(商品B), value(共现次数), lift(提升度)。
    ChartRenderer 会把 data 转成 DataFrame，列名即 source/target/value/lift，
    create_graph 直接读取这些列（无需 x/y 占位键重命名）。
    """
    selected = rules[:top]
    data = [{
        "source": r["antecedent"],
        "target": r["consequent"],
        "value": r.get("count", 0),
        "lift": round(r["lift"], 3),
    } for r in selected]
    return ChartData(slot=slot, chart_type="graph", title=title,
                     x="source", y="target", data=data)


# --------------------------------------------------------------------------
# 模型
# --------------------------------------------------------------------------
class AssociationRulesModel(AnalysisModel):
    name = "association_rules"
    display_name = "商品关联规则"
    description = "从订单明细挖掘经常一起购买的商品，计算支持度/置信度/提升度规则矩阵"
    required_columns = ["订单ID", "商品ID"]
    optional_columns = ["商品类目", "商品毛利", "商品单价", "折扣金额", "数量", "用户ID"]
    upstream_keys = ["rfm_user_segmentation"]

    def can_run(self, df: pd.DataFrame) -> bool:
        norm = _normalize_columns(df)
        return _has_cols(norm, self.required_columns)

    def compute(self, df: pd.DataFrame, upstream=None) -> AnalysisPackage:
        work = _normalize_columns(df)

        # 1) 核心列硬匹配双保险（引擎已拦一遍，这里再兜底）
        if not _has_cols(work, self.required_columns):
            return _empty_package(
                "订单明细缺少核心列（订单ID / 商品ID）",
                "请确认数据包含订单ID与商品ID两列后再进行分析。",
            )

        cols = set(work.columns)
        insights: list = []
        suggestions: list = []

        # 2) Base：构建购物篮 + 规则矩阵
        baskets = _build_baskets(work, "商品ID")
        n_baskets = len(baskets)
        if n_baskets == 0:
            return _empty_package(
                "有效购物篮数量为 0（订单ID/商品ID 清洗后无可用记录）",
                "请检查订单明细是否存在重复或空值。",
            )
        distinct_items = len({it for b in baskets for it in b})
        base_rules = _compute_rules(baskets, n_baskets, CFG.min_support, CFG.top_n)
        significant = _significant_dedup(base_rules, min_lift=1.0)
        has_significant = len(significant) > 0

        if not base_rules:
            insights.append("未发掘出显著关联规则（商品共现率普遍较低或低于最小支持度阈值）。")
        elif not has_significant:
            insights.append("未发掘出显著关联规则（所有商品组合的提升度均 ≤ 1，一起购买属于随机巧合，无真实关联）。")

        # 3) 进阶 B：毛利挂载（仅当有毛利/单价列）
        from src.analysis_engine.models import association_rules_advanced as adv
        has_margin = False
        has_revenue = False
        margin_chart = None   # 必须预置：base_rules 为空时 第336行 仍会引用，否则 UnboundLocalError
        margin_attached = False
        if base_rules:
            base_rules, margin_chart, has_margin, has_revenue = adv.compute_advanced_b(
                work, base_rules, CFG.chart_top
            )
            margin_attached = margin_chart is not None
            if margin_attached:
                parts = []
                if has_margin:
                    parts.append("平均毛利")
                if has_revenue:
                    parts.append("总收入")
                insights.append(f"已为规则挂载{'与'.join(parts)}（进阶 B）。")
            else:
                insights.append("未含毛利/单价列，未挂载利润指标（进阶 B 未触发）。")
        else:
            insights.append("未含毛利/单价列，未挂载利润指标（进阶 B 未触发）。")

        # 4) 进阶 A：跨类目粒度改写（仅当有商品类目列）
        cat_table = None
        cat_chart = None
        if "商品类目" in cols:
            cat_table, cat_chart = adv.compute_advanced_a(work, CFG)
            if cat_table is not None:
                insights.append("已按商品类目维度生成跨类目关联规则表（进阶 A）。")
            else:
                insights.append("进阶 A：已按类目重算，但当前各类目商品多独立购买，未发现跨类目显著关联规则（提升度均≤1）。")
        else:
            insights.append("未含商品类目列，未生成跨类目关联规则（进阶 A 未触发）。")

        # 5) 进阶 C：消费上游分层（仅当上游存在 且 订单含 用户ID）
        seg = None
        if upstream:
            seg = upstream.get("rfm_user_segmentation")
        has_seg = seg is not None and len(seg) > 0
        has_user_id = "用户ID" in cols
        c_triggered = has_seg and has_user_id

        seg_table = None
        seg_chart = None
        if c_triggered:
            seg_table, seg_chart = adv.compute_advanced_c(
                work, seg, CFG.min_support, CFG.top_n, CFG.chart_top
            )
            if seg_table is not None:
                insights.append("已按 RFM/K-means 客群切分重算关联规则并打 Action 标签（进阶 C）。")
            else:
                insights.append("进阶 C：已关联分层结果，但切分后未发掘出显著规则。")
                c_triggered = False
        else:
            if not has_seg:
                reason = "缺少 RFM/K-means 用户分层结果（rfm_user_segmentation 上游为空）"
            else:
                reason = "订单明细缺少 用户ID 列，无法与分层结果关联"
            insights.append(f"进阶 C 未触发：{reason}。")
            suggestions.append(f"进阶 C 未触发：{reason}，故未输出客群/Action 维度结果。")

        # 6) 组装表格 / 图表 / KPI
        base_rows = _base_table_rows(significant)
        base_columns = ["前项", "后项", "支持度", "置信度", "提升度"]
        if base_rows:
            if has_margin:
                base_columns.append("平均毛利")
            if has_revenue:
                base_columns.append("总收入")
        tables = []
        if base_rows:
            tables.append(TableData(
                title="商品关联规则（Top 提升度）",
                table_type="ar_rules",
                columns=base_columns,
                rows=base_rows,
                slot="ar_rules_lift_table",
            ))
        if cat_table is not None:
            tables.append(cat_table)
        if seg_table is not None:
            tables.append(seg_table)

        charts = []
        if has_significant:
            charts.append(_cooccurrence_graph_chart(
                "ar_network",
                "商品关联网络图（节点=商品，连线=常一起购买，线越粗=共现越多，金色=真关联）",
                significant, top=40))
        if cat_chart is not None:
            charts.append(cat_chart)
        if margin_chart is not None:
            charts.append(margin_chart)
        if seg_chart is not None:
            charts.append(seg_chart)

        max_lift = max((r["lift"] for r in base_rules), default=0.0)
        kpis = [
            KPIItem(label="订单数(篮子)", value=f"{n_baskets:,}"),
            KPIItem(label="商品数", value=f"{distinct_items:,}"),
            KPIItem(label="规则数", value=f"{len(base_rules):,}"),
            KPIItem(label="最高提升度", value=f"{max_lift:.2f}"),
        ]

        return AnalysisPackage(
            id="association_rules",
            analysis_type="association_rules",
            business_question="哪些商品经常被一起购买？",
            algorithm="association_rules_v1",
            dimension="商品",
            metric="关联规则",
            can_run=True,
            kpis=kpis,
            chart_data=charts,
            tables=tables,
            findings=[],
            insights=insights,
            suggestion="；".join(suggestions) if suggestions else "已基于订单明细完成购物篮关联分析。",
            confidence=1.0 if has_significant else 0.5,
        )


register_model(AssociationRulesModel())
