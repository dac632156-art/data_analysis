"""同期群模型 —— 进阶探测层 Advanced A/B/C。

三路并排，互不调用，各吃 Base 结果（或原始清洗 df）产出 ChartData。
确定性算法，无 LLM。详见 分析模型/同期群与用户状态跃迁模型拆解.md。
"""
from collections import defaultdict
from typing import Any, Dict, List

import pandas as pd

from src.analysis_templates.base import ChartData
from src.analysis_engine.models.cohort import (
    CFG, _month_index, _mi_to_label, _safe_dt, SENTINEL, _SUMMARY_COHORT_WINDOW,
)


# ==================== A. 横截面活跃留存用户数（健康度） ====================
def compute_advanced_a(work: pd.DataFrame, base: Dict[str, Any]) -> List[ChartData]:
    """A：月度活跃留存用户数（横截面健康度）。

    对每个统计月 m：统计「当月有订单、且首购月 < m」的老客去重人数。
    横截面口径：锚点=当月 m，无「次月」约束，与基座纵向同期群留存率（j=1）严格区分，不可混用。

    触发（文档口径）：存在 流量来源 或 商品类目 列才调用本函数；
    但函数内防御——维度列虽在但全为空时，仍产出 ALL 总览线（不会空手而归）。

    输出长表：统计月 m × 维度 k（含 'ALL' 总览）× 活跃留存用户数（量级数百）。
    公式：ActiveRetained(m,k)=|{u : ∃o s.t. Order_Month(o)=m ∧ dim_k(o)=k, 且 Cohort_Month(u)<m}|
    """
    charts: List[ChartData] = []

    # 统计月集合：全量订单月（去重升序），保证时间线连续；用标签作 X 轴类目
    order_all = _month_index(work["__dt__"])
    all_months = sorted(order_all.dropna().unique().tolist())
    if not all_months:
        return charts

    # 视觉窗口对齐基座热力图：仅展示最近 _SUMMARY_COHORT_WINDOW 个订单发生月。
    # 仅裁剪「展示哪些月」；首购锚点 cohort_mi 仍基于全量 work 计算，
    # 故「首购在窗口外、窗口内再次消费即算留存」口径不变。
    if len(all_months) > _SUMMARY_COHORT_WINDOW:
        all_months = all_months[-_SUMMARY_COHORT_WINDOW:]
    month_set = set(all_months)

    # 派生每用户首购月（base 未带则自行 groupby 算）
    first_dt = work.groupby("用户ID")["__dt__"].transform("min")
    cohort_mi = _month_index(first_dt)
    order_mi = _month_index(work["__dt__"])

    # 横截面筛选：排除当月新客（首购月 == 订单月），仅留老客
    mask = order_mi > cohort_mi
    retained = work[mask].copy()
    if retained.empty:
        return charts
    retained["__om__"] = order_mi[mask].values
    # 仅保留窗口内订单月，使 ALL 线 / 维度线 / TopN 图例选取口径与窗口一致
    retained = retained[retained["__om__"].isin(month_set)].copy()
    if retained.empty:
        return charts

    # ALL 总览线：逐月老客去重人数（同一用户当月只计一次，不论买多少维度值）
    all_series = retained.groupby("__om__")["用户ID"].nunique()
    all_rows = [{"统计月": _mi_to_label(m), "group": "ALL", "value": int(all_series.get(m, 0))}
                for m in all_months]

    # 维度探测（文档口径至少一个存在才触发；全空则仅出 ALL 总览线，防御兜底）
    dims = [d for d in ("流量来源", "商品类目") if d in work.columns]
    valid_dims = [d for d in dims if retained[d].notna().any()]

    if not valid_dims:
        charts.append(ChartData(
            slot="cohort_a_active",
            chart_type="cohort_active_line",
            title="月度活跃留存用户数（横截面健康度）",
            x="统计月", y="value", data=all_rows,
        ))
        return charts

    TOPN = {"流量来源": 6, "商品类目": 5}
    for dim in valid_dims:
        rows = list(all_rows)  # 复制 ALL 总览线
        # 逐维度：当月买该维度值的老客去重（同月买多个维度值 → 各维度线各计一次）
        dim_counts = retained.dropna(subset=[dim]).groupby(["__om__", dim])["用户ID"].nunique()
        # 维度值总活跃人数 Top N-1，其余并入「其他(合计)」（避免图例爆炸）
        tot = dim_counts.groupby(dim).sum()
        n = TOPN.get(dim, 10)
        top = set(tot.sort_values(ascending=False).head(n - 1).index.tolist())
        per_month = defaultdict(lambda: defaultdict(int))
        for (m, g), v in dim_counts.items():
            key = g if g in top else "其他(合计)"
            per_month[m][key] += int(v)
        for m in all_months:
            for g, v in per_month[m].items():
                rows.append({"统计月": _mi_to_label(m), "group": str(g), "value": v})

        dim_label = {"流量来源": "渠道", "商品类目": "商品类目"}.get(dim, dim)
        charts.append(ChartData(
            slot=f"cohort_a_{dim}",
            chart_type="cohort_active_line",
            title=f"月度活跃留存用户数 —— 按{dim_label}（横截面健康度）",
            x="统计月", y="value", data=rows,
        ))
    return charts


# ==================== B. 同期群质量趋势 ====================
def compute_advanced_b(base: Dict[str, Any]) -> List[ChartData]:
    """B：各偏移 j 的留存率随获客月变化趋势（折线 + 显著性标注）。

    触发：≥2 个 cohort。
    显著性：相邻（按时间序）成熟 cohort 在同 j 下做两比例 z 检验，|z|>1.96 标 '*'。
    """
    if len(base["cohort_labels"]) < 2:
        return []

    cohorts = base["cohort_labels"]  # 升序（最早在前）

    # j → {cohort_m: (retention, size)}
    j_map: Dict[int, Dict[int, tuple]] = {}
    for (m, j), ret in base["retention"].items():
        if ret is None:
            continue
        j_map.setdefault(j, {})[m] = (ret, base["size"].get(m, 0))

    # 选择展示的 j：优先 1/3/6，否则取前 3 个存在的 j
    want = [j for j in (1, 3, 6) if j in j_map]
    if not want:
        want = sorted(j_map.keys())[:3]
    if not want:
        return []

    rows = []
    for j in want:
        series = j_map[j]
        prev_ret = None
        prev_size = None
        for m in cohorts:
            if m not in series:
                continue
            ret, size = series[m]
            mark = ""
            if prev_ret is not None and prev_size and prev_size > 0 and size > 0:
                se = ((ret * (1 - ret) / size) + (prev_ret * (1 - prev_ret) / prev_size)) ** 0.5
                if se > 0:
                    z = (ret - prev_ret) / se
                    if abs(z) > CFG.WILSON_Z:
                        mark = "*"
            rows.append({
                "首单月": base["cohort_label_map"][m],
                "Index_j": j,
                "留存率": round(float(ret), 4),
                "mark": mark,
            })
            prev_ret, prev_size = ret, size

    if not rows:
        return []

    return [ChartData(
        slot="cohort_b_trend",
        chart_type="cohort_trend",
        title="同期群质量趋势（偏移 j 留存率）",
        x="首单月", y="留存率", data=rows,
    )]


# ==================== C. 净毛利 / 净 GMV 净化 ====================
def compute_advanced_c(work: pd.DataFrame, base: Dict[str, Any]) -> List[ChartData]:
    """C：净毛利 cohort 热力图 + 净GMV vs 净毛利 双轴图。

    触发：存在 退款完成日期/退款金额 或 商品成本/运费 任一成本类列。
    口径：
      净毛利_o = 订单实付金额 − 取到的成本类列之和（商品成本/运费/退款金额，未取到按 0）
      退款金额：有 退款完成日期 时归退款完成月，否则归订单月
      净GMV(m) = Σ实付(m) − Σ退款(m)
    """
    # 无成本/退款列时，下方会按 0 兜底（净毛利=净GMV=Σ实付），
    # 故此触发器不再要求必须存在成本列，保证纯订单表也能出净GMV/净毛利图。
    has_refund_date = "退款完成日期" in work.columns

    df = work.copy()
    # 剔除无有效订单日期的行：与基座一致，避免 Index_j 强转在 NaN 上崩
    if df["__dt__"].isna().any():
        df = df[df["__dt__"].notna()].copy()
    first_dt = df.groupby("用户ID")["__dt__"].transform("min")
    df["Cohort_Month"] = _month_index(first_dt)
    # 可空整数类型，杜绝残留 NaN 触发强转崩溃
    df["Index_j"] = (_month_index(df["__dt__"]) - df["Cohort_Month"]).astype("Int64")

    # 仅纳入成熟 cohort（与基座一致）
    today_month = base["today_month"]
    mature = (today_month - df["Cohort_Month"]) >= CFG.MIN_OBSERVATION_MONTHS
    df = df[mature].copy()
    if df.empty:
        return []

    # 每行 net 金额（订单所属 cell）
    df["amount"] = df["订单实付金额"].astype(float)
    if "商品成本" in df.columns:
        df["amount"] -= df["商品成本"].fillna(0).astype(float)
    if "运费" in df.columns:
        df["amount"] -= df["运费"].fillna(0).astype(float)

    if "退款金额" in df.columns:
        refund = df["退款金额"].fillna(0).astype(float)
        if has_refund_date:
            # 退款归退款完成月：原订单 cell 不扣退款，
            # 由下方 refund_rows（amount=-退款，落在退款完成月）单独扣减。
            rdt = _safe_dt(df["退款完成日期"])
            rmonth = _month_index(rdt)
            # NaT（空日期）回退到订单月偏移
            df["refund_j"] = (rmonth - df["Cohort_Month"]).fillna(df["Index_j"]).astype("Int64")
            # 退款行必须带唯一「订单ID」：否则 concat 后该列=NaN，下游
            # drop_duplicates(subset=["订单ID"]) 会把所有 NaN 视为相同 → 多笔退款被压缩成一行，
            # 导致净毛利少扣退款而虚高。
            refund_cols = ["Cohort_Month", "用户ID"]
            if "订单ID" in df.columns:
                refund_cols.append("订单ID")
            refund_rows = df[refund > 0][refund_cols].copy()
            refund_rows["Index_j"] = df["refund_j"][refund > 0].values
            refund_rows["amount"] = (-refund[refund > 0]).reset_index(drop=True)
            refund_rows["订单实付金额"] = 0.0
            if "订单ID" in refund_rows.columns:
                refund_rows["订单ID"] = refund_rows["订单ID"].astype(str) + "_refund"
                concat_cols = ["Cohort_Month", "用户ID", "订单ID", "Index_j", "amount", "订单实付金额"]
            else:
                concat_cols = ["Cohort_Month", "用户ID", "Index_j", "amount", "订单实付金额"]
            df = pd.concat([df, refund_rows[concat_cols]], ignore_index=True)
        else:
            df["amount"] -= refund

    if "订单ID" in df.columns:
        agg_src = df.drop_duplicates(subset=["订单ID"], keep="first")
    else:
        agg_src = df

    net_g = agg_src.groupby(["Cohort_Month", "Index_j"]).agg(
        U=("用户ID", "nunique"),
        R_net=("amount", "sum"),
    ).reset_index()

    # 每 cohort 净GMV / 净毛利
    gmv_cohort = df.groupby("Cohort_Month")["订单实付金额"].sum()
    if "退款金额" in df.columns:
        if has_refund_date:
            refund_cohort = df[df["退款金额"].fillna(0) > 0].groupby("Cohort_Month")["退款金额"].sum()
        else:
            refund_cohort = df.groupby("Cohort_Month")["退款金额"].sum()
    else:
        refund_cohort = pd.Series(dtype=float)
    net_gmv_cohort = gmv_cohort - refund_cohort.reindex(gmv_cohort.index).fillna(0)
    net_margin_cohort = net_g.groupby("Cohort_Month")["R_net"].sum()

    charts: List[ChartData] = []

    # (1) 净毛利 cohort 热力图（ARPU_net = R_net / U）
    # 与基座对齐：最近 _SUMMARY_COHORT_WINDOW 个 cohort × j∈[0, _W-1]（金额类保留 j=0）
    all_labels = base["cohort_labels"]
    win_labels = all_labels[-_SUMMARY_COHORT_WINDOW:] if len(all_labels) > _SUMMARY_COHORT_WINDOW else all_labels
    win_set = set(win_labels)  # 与基座 cohort.py 一致：仅在窗口内的 (首单月+j) 才参与计算
    cohort_labels = [m for m in win_labels if m in net_g["Cohort_Month"].unique()]
    max_j = min(int(net_g["Index_j"].max()) if len(net_g) else 0, _SUMMARY_COHORT_WINDOW - 1)
    heat_rows = []
    for m in cohort_labels:
        sub = net_g[net_g["Cohort_Month"] == m]
        for _, r in sub.iterrows():
            j = int(r["Index_j"])
            if (m + j) not in win_set:  # 目标月(首单月+j)不在窗口内 → 不参与计算/渲染，与基座留存率图对齐
                continue
            if j > max_j:
                continue
            u = r["U"]
            v = (r["R_net"] / u) if u and u > 0 else None
            if v is None or (isinstance(v, float) and v != v):
                heat_rows.append({"Index_j": j, "首单月": _mi_to_label(m), "value": SENTINEL})
            else:
                heat_rows.append({"Index_j": j, "首单月": _mi_to_label(m), "value": round(float(v), 4)})
    if heat_rows:
        charts.append(ChartData(
            slot="cohort_c_netmargin_heat",
            chart_type="cohort_heatmap",
            title="各同期群净毛利 ARPU（下三角）",
            x="Index_j", y="首单月", data=heat_rows,
        ))

    # (2) 净GMV vs 净毛利 双轴图
    dual_rows = []
    for m in cohort_labels:
        label = _mi_to_label(m)
        gmv = net_gmv_cohort.get(m, 0.0)
        margin = net_margin_cohort.get(m, 0.0)
        dual_rows.append({
            "首单月": label,
            "净GMV": round(float(gmv), 4),
            "净毛利": round(float(margin), 4),
        })
    if dual_rows:
        charts.append(ChartData(
            slot="cohort_c_dual",
            chart_type="dual_axis",
            title="净GMV vs 净毛利（按同期群）",
            x="首单月", y="净GMV", data=dual_rows,
        ))

    return charts
