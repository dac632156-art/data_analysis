"""CLV 模型 —— 进阶探测层 Advanced A/B/C。

三路并排，互不调用，各吃 Base 结果（或原始清洗 df）产出 ChartData。
确定性算法，无 LLM。详见 分析模型/CLV客户生命周期价值模型拆解.md。

触发（入口契约）：每个分支仅当自身探测列存在于输入、且依赖的 Base 步已跑通时才调用。
基座不变，进阶只在其上叠加维度 / 换指标 / 换口径。
"""
from typing import Any, Dict, List

import pandas as pd

from src.analysis_templates.base import ChartData

# TopN 截断：避免维度过多时图例爆炸（与 cohort_a 一致思路）
ADV_A_TOPN = {"流量来源": 6, "商品类目": 8}


# ==================== A. 渠道 / 类目细分 CLV ====================
def compute_advanced_a(work: pd.DataFrame, base: Dict[str, Any]) -> List[ChartData]:
    """A：按 流量来源 / 商品类目 对各客 CLV 取均值（方法②：逐客均值）。

    触发：存在 流量来源 或 商品类目 列。
    产出：每维度一张分组条形图（x=维度值, y=平均 CLV）。
    """
    charts: List[ChartData] = []
    users = base["users"]
    clv_map = dict(zip(users["用户ID"], users["CLV"]))

    w = work.copy()
    w["__clv"] = w["用户ID"].map(clv_map)
    w["__amt"] = pd.to_numeric(w["订单实付金额"], errors="coerce").fillna(0)

    for dim in ["流量来源", "商品类目"]:
        if dim not in w.columns:
            continue
        # 订单级维度：每用户主归属 = 消费金额占比最高的维度值
        grp = w.groupby(["用户ID", dim])["__amt"].sum().reset_index()
        idx = grp.groupby("用户ID")["__amt"].idxmax()
        user_dim = grp.loc[idx].set_index("用户ID")[dim].rename("k").reset_index()

        md = user_dim.merge(users[["用户ID", "CLV"]], on="用户ID", how="left")
        mean_clv = md.groupby("k")["CLV"].mean().sort_values(ascending=False)

        rows = [{"维度": str(k), "平均客户生命周期价值": round(float(v), 4)} for k, v in mean_clv.items()]
        n = ADV_A_TOPN.get(dim, 8)
        if len(rows) > n:                       # 长尾截断：仅保留均值最高的前 n 个
            rows = rows[:n]

        label = {"流量来源": "渠道", "商品类目": "商品类目"}.get(dim, dim)
        charts.append(ChartData(
            slot=f"clv_a_{dim}", chart_type="bar",
            title=f"各{label}平均客户生命周期价值", x="维度", y="平均客户生命周期价值", data=rows,
        ))
    return charts


# ==================== B. 净 CLV 净化 ====================
def compute_advanced_b(work: pd.DataFrame, base: Dict[str, Any]) -> List[ChartData]:
    """B：净 CLV = 订单实付金额 − 取到的成本类列之和。

    触发：存在 商品成本 / 运费 / 退款金额 任一列。
    产出：总 CLV vs 净 CLV 双轴图（柱=总 CLV, 线=净 CLV）。
    """
    cost_cols = [c for c in ["商品成本", "运费", "退款金额"] if c in work.columns]
    if not cost_cols:
        return []

    users = base["users"]
    w = work.copy()
    amt = pd.to_numeric(w["订单实付金额"], errors="coerce").fillna(0)
    for c in cost_cols:
        amt = amt - pd.to_numeric(w[c], errors="coerce").fillna(0)
    w["__net"] = amt

    m_net = w.groupby("用户ID")["__net"].sum()
    fn = users.set_index("用户ID")
    fn["M_net"] = m_net
    fn["AOV_net"] = fn["M_net"] / fn["F"].clip(lower=1)

    c_eff = base["c_hat_eff"]
    fn["CLV_net"] = fn["AOV_net"] * fn["F_yearly"] * (1.0 - c_eff) / c_eff

    top = fn.sort_values("CLV", ascending=False).head(5).reset_index()
    rows = [{
        "用户ID": str(r["用户ID"]),
        "总客户生命周期价值": round(float(r["CLV"]), 4),
        "净客户生命周期价值": round(float(r["CLV_net"]), 4),
    } for _, r in top.iterrows() if pd.notna(r["CLV"])]

    if not rows:
        return []

    return [ChartData(
        slot="clv_b_net", chart_type="dual_axis",
        title="总客户生命周期价值 vs 净客户生命周期价值（Top-5）", x="用户ID", y="总客户生命周期价值",
        right_col="净客户生命周期价值", data=rows,
    )]


# ==================== C. 流失率精算 ====================
def compute_advanced_c(work: pd.DataFrame, base: Dict[str, Any]) -> List[ChartData]:
    """C：改 R(u) 口径与 c_hat 粒度，回代 2.4 重算 CLV。

    触发：存在 注册日期 或 最后活跃时间 列。
      - 注册日期：按客龄分层（新客/成长期/成熟期）算分层流失率 → 折线 + 修正 CLV 条形
      - 最后活跃时间：用活跃信号替代末次下单算 R → 分组条形对比原 CLV vs 活跃修正 CLV
    """
    charts: List[ChartData] = []
    users = base["users"].copy()
    T_ref = base["T_ref"]
    thresh = base["churn_thresh"]

    if "注册日期" in work.columns:
        reg = pd.to_datetime(work.groupby("用户ID")["注册日期"].min(), errors="coerce")
        users = users.set_index("用户ID")
        users["注册日期"] = reg
        users = users.reset_index()

        age_years = (T_ref - users["注册日期"]).dt.days / 365.0
        def _age_tier(a):
            if pd.isna(a):
                return "2-成长期"
            if a < 1:
                return "1-新客"
            if a < 2:
                return "2-成长期"
            return "3-成熟期"
        users["客龄层"] = age_years.apply(_age_tier)

        # users 已含 R / AOV / F_yearly / 客龄层，无需再 merge（避免重复列 R_x/R_y）
        churn_rows, clv_rows = [], []
        for t in ["1-新客", "2-成长期", "3-成熟期"]:
            sub = users[users["客龄层"] == t]
            n = len(sub)
            if n == 0:
                continue
            c_age = float((sub["R"] > thresh).mean())
            c_age_eff = max(c_age, 1.0 / n)
            mean_corr = float((sub["AOV"] * sub["F_yearly"] * (1.0 - c_age_eff) / c_age_eff).mean())
            churn_rows.append({"客龄层": t, "流失率": round(c_age, 4)})
            clv_rows.append({"客龄层": t, "平均修正客户生命周期价值": round(mean_corr, 4)})

        if churn_rows:
            charts.append(ChartData(
                slot="clv_c_churn", chart_type="line",
                title="各客龄层流失率", x="客龄层", y="流失率", data=churn_rows,
            ))
            charts.append(ChartData(
                slot="clv_c_clv", chart_type="bar",
                title="各客龄层修正后平均客户生命周期价值", x="客龄层", y="平均修正客户生命周期价值", data=clv_rows,
            ))

    if "最后活跃时间" in work.columns:
        active = pd.to_datetime(work.groupby("用户ID")["最后活跃时间"].max(), errors="coerce")
        users = users.set_index("用户ID")
        users["active"] = active
        users = users.reset_index()

        users["R_active"] = (T_ref - users["active"]).dt.days
        N = len(users)
        c_active = float((users["R_active"] > thresh).mean())
        c_active_eff = max(c_active, 1.0 / N) if N > 0 else c_active
        users["CLV_active"] = users["AOV"] * users["F_yearly"] * (1.0 - c_active_eff) / c_active_eff

        top = users.sort_values("CLV", ascending=False).head(5)
        rows = []
        for _, r in top.iterrows():
            if pd.isna(r["CLV"]):
                continue
            rows.append({"用户ID": str(r["用户ID"]), "口径": "原客户生命周期价值",
                        "客户生命周期价值": round(float(r["CLV"]), 4)})
            rows.append({"用户ID": str(r["用户ID"]), "口径": "活跃修正客户生命周期价值",
                        "客户生命周期价值": round(float(r["CLV_active"]), 4)})
        if rows:
            charts.append(ChartData(
                slot="clv_c_active", chart_type="bar",
                title="活跃口径修正客户生命周期价值（Top-5）", x="用户ID", y="客户生命周期价值",
                color="口径", data=rows,
            ))
        return charts

    return charts
