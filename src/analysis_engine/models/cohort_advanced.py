"""同期群模型 —— 进阶探测层 Advanced A/B/C。

三路并排，互不调用，各吃 Base 结果（或原始清洗 df）产出 ChartData。
确定性算法，无 LLM。详见 分析模型/同期群与用户状态跃迁模型拆解.md。
"""
from typing import Any, Dict, List

import pandas as pd

from src.analysis_templates.base import ChartData
from src.analysis_engine.models.cohort import (
    CFG, _month_index, _mi_to_label, _safe_dt, SENTINEL,
)


# ==================== A. 渠道 / 类目维度升维 ====================
def compute_advanced_a(work: pd.DataFrame, base: Dict[str, Any]) -> List[ChartData]:
    """A：按 流量来源 / 商品类目 拆 M1 留存用户数（堆叠条形）。

    触发：存在 流量来源 或 商品类目 列。
    产出：每维度一张 cohort_stacked（x=首单月, stack by 维度值, y=M1 留存用户数）。
    """
    charts: List[ChartData] = []
    today_month = base["today_month"]

    for dim in ["流量来源", "商品类目"]:
        if dim not in work.columns:
            continue

        df = work.copy()
        first_dt = df.groupby("用户ID")["__dt__"].transform("min")
        df["Cohort_Month"] = _month_index(first_dt)
        df["Index_j"] = (_month_index(df["__dt__"]) - df["Cohort_Month"]).astype(int)
        mature = (today_month - df["Cohort_Month"]) >= CFG.MIN_OBSERVATION_MONTHS
        df = df[mature]
        if df.empty:
            continue

        if "订单ID" in df.columns:
            agg_src = df.drop_duplicates(subset=["订单ID"], keep="first")
        else:
            agg_src = df

        g0 = agg_src[agg_src["Index_j"] == 0].groupby(["Cohort_Month", dim])["用户ID"].nunique()
        g1 = agg_src[agg_src["Index_j"] == 1].groupby(["Cohort_Month", dim])["用户ID"].nunique()
        merged = pd.concat([g0.rename("u0"), g1.rename("u1")], axis=1).reset_index()
        if merged.empty:
            continue

        rows = []
        for _, r in merged.iterrows():
            u1 = r.get("u1", 0)
            if not u1 or (isinstance(u1, float) and u1 != u1) or u1 <= 0:
                continue
            rows.append({
                "首单月": _mi_to_label(r["Cohort_Month"]),
                "group": str(r[dim]),
                "value": int(u1),
            })
        if not rows:
            continue

        charts.append(ChartData(
            slot=f"cohort_a_{dim}",
            chart_type="cohort_stacked",
            title=f"{dim} 各渠道 M1 留存用户数（堆叠）",
            x="首单月", y="value", data=rows,
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
    first_dt = df.groupby("用户ID")["__dt__"].transform("min")
    df["Cohort_Month"] = _month_index(first_dt)
    df["Index_j"] = (_month_index(df["__dt__"]) - df["Cohort_Month"]).astype(int)

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
            df["refund_j"] = (rmonth - df["Cohort_Month"]).fillna(df["Index_j"]).astype(int)
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
    cohort_labels = [m for m in base["cohort_labels"] if m in net_g["Cohort_Month"].unique()]
    max_j = int(net_g["Index_j"].max()) if len(net_g) else 0
    heat_rows = []
    for m in cohort_labels:
        sub = net_g[net_g["Cohort_Month"] == m]
        for _, r in sub.iterrows():
            j = int(r["Index_j"])
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
