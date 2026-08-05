"""商品关联规则模型的三个可选进阶计算。

- compute_advanced_a：跨类目粒度改写（有商品类目列时）
- compute_advanced_b：毛利挂载（有毛利/单价列时）
- compute_advanced_c：消费上游 RFM/K-means 分层，按用户ID join 后按客群切分重算并打 Action 标签

复用 association_rules 的基础函数（_build_baskets / _compute_rules / _pct）。
"""

from collections import Counter
from itertools import combinations

import pandas as pd

from src.analysis_templates.base import ChartData, TableData
from src.analysis_engine.models.association_rules import (
    CFG,
    _build_baskets,
    _compute_rules,
    _pct,
    _significant_dedup,
)


# --------------------------------------------------------------------------
# 进阶 A：跨类目粒度改写
# --------------------------------------------------------------------------
def compute_advanced_a(work: pd.DataFrame, cfg: CFG):
    """把粒度从具体商品改写为商品类目，重算类目级关联规则，产出跨类目关联网络图。

    仅当存在 lift>1 的显著类目级关联时才出图+表；否则返回 (None, None)。
    图只展示"哪些类目常一起买"（节点=类目、连线=共现、线粗=共现次数），
    提升度等指标全部进表，图上不标指标数字。
    """
    if "商品类目" not in work.columns:
        return None, None
    baskets = _build_baskets(work, "商品类目")
    n = len(baskets)
    if n == 0:
        return None, None
    rules = _compute_rules(baskets, n, cfg.min_support, cfg.top_n)
    if not rules:
        return None, None
    significant = _significant_dedup(rules, min_lift=1.0)
    if not significant:
        return None, None

    rows = [{
        "前项(类目)": r["antecedent"],
        "后项(类目)": r["consequent"],
        "支持度": _pct(r["support"]),
        "置信度": _pct(r["confidence"]),
        "提升度": round(r["lift"], 3),
    } for r in significant]
    table = TableData(
        title="跨类目关联规则（进阶 A）",
        table_type="ar_rules_category",
        columns=["前项(类目)", "后项(类目)", "支持度", "置信度", "提升度"],
        rows=rows,
        slot="ar_category_table",
    )
    # 进阶 A 仅以表格呈现（不再绘制网络图）
    return table, None


# --------------------------------------------------------------------------
# 进阶 B：毛利挂载
# --------------------------------------------------------------------------
def _pick(col_set, candidates):
    for c in candidates:
        if c in col_set:
            return c
    return None


def compute_advanced_b(work: pd.DataFrame, base_rules: list, chart_top: int = 15):
    """给 base 规则挂载平均毛利与总收入。

    返回 (更新后的 rules, 毛利图表或 None)。无毛利/单价列则返回原 rules + None。
    """
    cols = set(work.columns)
    margin_col = _pick(cols, ["商品毛利", "毛利", "margin", "profit"])
    price_col = _pick(cols, ["商品单价", "单价", "price", "unit_price"])
    qty_col = _pick(cols, ["数量", "qty", "quantity", "count", "num"])

    has_margin = margin_col is not None
    has_revenue = price_col is not None and qty_col is not None
    if not has_margin and not has_revenue:
        return base_rules, None, False, False

    # 预构建：每个商品 -> 包含它的订单ID集合（用于快速求共现订单）
    item_orders: dict = {}
    grouped = work.groupby("订单ID")["商品ID"].apply(
        lambda s: frozenset(str(v) for v in s.dropna())
    )
    for oid, items in grouped.items():
        for it in items:
            item_orders.setdefault(it, set()).add(oid)

    out = []
    for r in base_rules:
        ant, con = r["antecedent"], r["consequent"]
        oids = item_orders.get(ant, set()) & item_orders.get(con, set())
        r2 = dict(r)
        if not oids:
            r2["avg_margin"] = 0.0
            r2["total_revenue"] = 0.0
            out.append(r2)
            continue
        sub = work[work["订单ID"].isin(oids)]
        if has_margin:
            tot_m = pd.to_numeric(sub[margin_col], errors="coerce").fillna(0).sum()
            avg_m = (tot_m / len(oids)) if len(oids) else 0.0
        else:
            tot_m = 0.0
            avg_m = 0.0
        if has_revenue:
            rev = (pd.to_numeric(sub[price_col], errors="coerce").fillna(0)
                   * pd.to_numeric(sub[qty_col], errors="coerce").fillna(0)).sum()
        else:
            rev = 0.0
        r2["avg_margin"] = float(avg_m)
        r2["total_revenue"] = float(rev)
        out.append(r2)

    # 毛利图表：有收入列(单价+数量)则按总收入 Top，否则按平均毛利 Top
    if has_revenue:
        metric = "total_revenue"
        ylabel = "总收入"
        title = "Top 总收入关联规则（进阶 B）"
    else:
        metric = "avg_margin"
        ylabel = "平均毛利"
        title = "Top 平均毛利关联规则（进阶 B）"
    rs = sorted(out, key=lambda r: r.get(metric, 0), reverse=True)[:chart_top]
    data = [{"x": f"{r['antecedent']}→{r['consequent']}",
             "y": round(r.get(metric, 0), 2)} for r in rs]
    chart = ChartData(slot="ar_margin_top", chart_type="ranking",
                      title=title, x="规则", y=ylabel, data=data)
    return out, chart, has_margin, has_revenue


# --------------------------------------------------------------------------
# 进阶 C：消费上游分层，按用户ID join 切分重算并打 Action 标签
# --------------------------------------------------------------------------
def _action_for(segment: str, lift: float) -> str:
    """默认 Action 映射：高价值客群 → 定向捆绑；其余 → 常规捆绑。

    高价值判定：客群名以「重要」开头，或含「价值」「VIP」（覆盖 RFM 8 群与
    降级 K-means 簇命名）。
    """
    s = str(segment)
    high_tier = s.startswith("重要") or "价值" in s or "VIP" in s.upper()
    if high_tier:
        return "VIP_Targeted_Bundle"
    return "Standard_Bundle"


def compute_advanced_c(work: pd.DataFrame, seg: pd.DataFrame,
                       min_support: float, top_n: int, chart_top: int = 15):
    """消费上游分层宽表，按用户ID inner join 订单明细，按客群切分重算关联规则。

    返回 (分客群规则表或 None, 分客群图表或 None)。
    segment/group 列名兼容 RFM 的 `Segment` 与降级 K-means 的 `簇`。
    """
    if seg is None or len(seg) == 0:
        return None, None
    if "用户ID" not in work.columns:
        return None, None

    # 确定分组列（与 user_profile 一致）
    if "Segment" in seg.columns:
        gcol = "Segment"
    elif "簇" in seg.columns:
        gcol = "簇"
    else:
        return None, None

    seg2 = seg.copy()
    seg2["用户ID"] = seg2["用户ID"].astype(str)
    merged = work.merge(seg2[["用户ID", gcol]], on="用户ID", how="inner")
    if len(merged) == 0:
        return None, None

    segments = [s for s in merged[gcol].dropna().unique().tolist() if str(s) != ""]
    if not segments:
        return None, None

    all_rules = []
    for s in segments:
        sub = merged[merged[gcol] == s]
        baskets = _build_baskets(sub, "商品ID")
        n = len(baskets)
        if n == 0:
            continue
        rules = _compute_rules(baskets, n, min_support, top_n)
        for r in rules:
            r2 = dict(r)
            r2["segment"] = s
            r2["action"] = _action_for(s, r2["lift"])
            all_rules.append(r2)

    if not all_rules:
        return None, None

    # 表：跨客群按 lift 降序统一截断（提升度仅在此表展示，图不放提升度）
    all_rules.sort(key=lambda r: r["lift"], reverse=True)
    rows = [{
        "客群": r["segment"],
        "前项": r["antecedent"],
        "后项": r["consequent"],
        "支持度": _pct(r["support"]),
        "置信度": _pct(r["confidence"]),
        "提升度": round(r["lift"], 3),
        "Action": r["action"],
    } for r in all_rules[:top_n]]
    table = TableData(
        title="分客群关联规则（进阶 C）",
        table_type="ar_rules_segment",
        columns=["客群", "前项", "后项", "支持度", "置信度", "提升度", "Action"],
        rows=rows,
        slot="ar_segment_table",
    )

    # 图：各客群常买组合的共现次数（分组柱状图）。x=组合、series=客群、y=共现次数，
    # 图上不出现任何指标数字；不同客群组合不同，x 轴取全局 Top 组合并集避免稀疏。
    seg_combos = {}
    for r in all_rules:
        seg = r["segment"]
        label = f"{r['antecedent']}→{r['consequent']}"
        seg_combos.setdefault(seg, []).append((label, r.get("count", 0)))
    combo_total = {}
    for seg, lst in seg_combos.items():
        for label, c in lst:
            combo_total[label] = combo_total.get(label, 0) + c
    top_combos = [c for c, _ in sorted(combo_total.items(),
                                      key=lambda kv: kv[1], reverse=True)[:chart_top]]
    seg_count = {seg: {label: c for label, c in lst} for seg, lst in seg_combos.items()}
    chart_data = []
    for seg in seg_combos:
        for combo in top_combos:
            chart_data.append({
                "x": combo,
                "y": seg_count[seg].get(combo, 0),
                "series": seg,
            })
    chart = ChartData(slot="ar_c_count_top", chart_type="ranking",
                      title="各客群常买组合（共现次数，进阶 C）",
                      x="组合", y="共现次数", data=chart_data)
    return table, chart
