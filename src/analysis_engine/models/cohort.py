"""同期群与用户状态跃迁模型 —— 新分析引擎 AnalysisModel 实现。

三段式：HardBlock(validate_input) → Base(compute_base) → Advanced(a/b/c)。
确定性算法，无 LLM。详见 分析模型/同期群与用户状态跃迁模型拆解.md。

注意：本模块底部才 import cohort_advanced（避免与 adv 顶部的 `from .cohort import ...` 形成
模块级循环导入；adv 导入时本模块已完全定义，故安全）。
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.analysis_engine.base import AnalysisModel
from src.analysis_engine.registry import register_model
from src.analysis_templates.base import AnalysisPackage, KPIItem, ChartData
from src.domain.finding_factory import FindingFactory
from src.domain.business_finding import Severity, FindingCategory


# ==================== 配置常量（对齐文档原文附录） ====================
@dataclass
class CohortConfig:
    TZ: str = "Asia/Shanghai"
    # 中英双语「有效订单」状态白名单：
    # 中文保留 已完成/已支付/已发货 等；英文保留 delivered/shipped/invoiced/
    # processing/approved/created/paid，剔除 canceled/unavailable（取消/不可用单）。
    STATUS_WHITELIST: frozenset = frozenset({
        # 中文有效状态
        "已完成", "已支付", "已发货", "已签收", "已下单", "已创建",
        # 英文有效状态（剔除 canceled / unavailable）
        "delivered", "shipped", "invoiced", "processing",
        "approved", "created", "paid",
    })
    FUTURE_TOLERANCE_DAYS: int = 1
    FUTURE_SKIP_RATIO: float = 0.05
    MIN_OBSERVATION_MONTHS: int = 6
    WILSON_Z: float = 1.96
    REFUND_ATTR: str = "refund_month"
    SHIPPING_ATTR: str = "order_month"
    # 退化诊断阈值：所选用户键的复购率低于此值，视为「非真实用户键」并显式告警
    DEGENERATE_REPEAT_RATE: float = 0.01


CFG = CohortConfig()

# ==================== 列名归一化（兼容「原始中文名」与「映射后标准名」） ====================
# 流水线 map_dataset_columns 会把部分列重命名为标准字段名（如 订单实付金额→订单总额），
# 模型内部统一以规范中文列名计算。这里把各种别名/标准名解析回规范名，避免 can_run 误判缺失。
COLUMN_ALIASES: Dict[str, List[str]] = {
    "用户ID":       ["用户ID", "user_id", "uid", "customer_id", "customer_unique_id",
                     "user_unique_id", "member_unique_id", "member_id", "account_id",
                     "客户编号", "用户编码", "会员编号", "用户标识",
                     # 映射后标准名：上游 column_mapping_dict 把 customer_unique_id
                     # 归为独立的「客户唯一ID」而非「用户ID」，故此处显式纳入，
                     # 否则方案3选键永远扫不到真实用户键（详见下方 compute 注释）。
                     "客户唯一ID"],
    "订单时间":     ["订单时间", "order_time", "order_date", "支付时间", "购买时间",
                     "下单时间", "订单日期", "order_purchase_timestamp"],
    "订单实付金额": ["订单实付金额", "订单总额", "购买金额", "订单金额", "total_payment",
                     "payment_value", "实付金额", "付款金额", "支付金额", "total_usd"],
    "订单ID":       ["订单ID", "order_id", "订单编号", "单据ID"],
    "订单状态":     ["订单状态", "order_status", "交易状态", "订单进度"],
    "退款完成日期": ["退款完成日期", "refund_completed_date", "refund_date", "退款时间", "退款状态"],
    "退款金额":     ["退款金额", "refund_amount", "refunded_amount", "退款额", "退费金额"],
    "流量来源":     ["流量来源", "source", "channel", "来源渠道", "访问来源", "ReferralSource"],
    "商品类目":     ["商品类目", "category", "product_category", "商品分类", "产品类目"],
    "商品成本":     ["商品成本", "cost", "进货成本", "成本价", "cost_usd", "cost price"],
    "运费":         ["运费", "shipping_fee", "freight", "delivery_fee",
                     "shipping_cost", "邮费", "配送费"],
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """把各种别名/映射后标准名统一成模型内部规范中文列名。

    每个规范名只取第一个命中的来源列，避免多列冲突。
    """
    rename: Dict[str, str] = {}
    for canon, aliases in COLUMN_ALIASES.items():
        for a in aliases:
            if a in df.columns:
                rename[a] = canon
                break
    if not rename:
        return df
    return df.rename(columns=rename)


def _select_user_key(df: pd.DataFrame) -> Tuple[Optional[str], float]:
    """方案3：从原始 df 中自动挑选「真实用户键」。

    扫描所有命中 COLUMN_ALIASES['用户ID'] 的候选列，按「绑定 >1 个不同订单ID
    的用户占比」（复购率）挑最高者。关键：必须用 distinct 订单数而非行数判复购——
    合并宽表为订单-商品粒度，订单级键也会因多商品产生多行，行数无法区分
    订单级/用户级键；只有「同一用户出现 >1 个不同 order_id」才能唯一识别真实用户键。

    返回 (选中列名, 复购率)；无候选返回 (None, -1.0)。
    退化判定（复购率 < CFG.DEGENERATE_REPEAT_RATE）由 compute 注入告警。
    """
    user_aliases = set(COLUMN_ALIASES["用户ID"])
    candidates = [c for c in df.columns if c in user_aliases]
    if not candidates:
        return (None, -1.0)

    # 定位订单列（用于更可靠地判复购）
    order_aliases = set(COLUMN_ALIASES["订单ID"])
    order_col = next((c for c in df.columns if c in order_aliases), None)

    scored = []
    for c in candidates:
        n_users = df[c].nunique()
        if n_users == 0:
            continue
        if order_col is not None:
            repeat_users = int((df.groupby(c)[order_col].nunique() > 1).sum())
        else:
            # 无订单列：用「出现 >1 行」兜底（订单-商品粒度下不够准，仅作回退）
            repeat_users = int((df.groupby(c).size() > 1).sum())
        rate = repeat_users / float(n_users)
        scored.append((c, rate))

    if not scored:
        return (None, -1.0)

    # 选复购率最高者；并列时：名称含 unique/user/member/uid 优先 > 候选序靠前
    def _prefer(name: str) -> int:
        low = name.lower()
        if any(k in low for k in ("unique", "user", "member", "uid")):
            return 0
        return 1

    best = max(scored, key=lambda t: (t[1], -_prefer(t[0])))
    return (best[0], best[1])


REQUIRED_COLUMNS = ["用户ID", "订单时间", "订单实付金额"]
OPTIONAL_COLUMNS = ["订单ID", "订单状态", "退款完成日期", "退款金额",
                      "流量来源", "商品类目", "事件时间", "行为类型",
                      "商品成本", "运费"]

# 未观测格哨兵值（热力图灰显）
SENTINEL = -1.0


# ==================== 时间 / 月份工具 ====================
def _month_index(ts: pd.Series) -> pd.Series:
    """日期序列 → 整数年-月索引 (year*12 + month)。"""
    return ts.dt.year * 12 + ts.dt.month


def _mi_to_label(midx) -> str:
    """整数年-月索引 → 'YYYY-MM' 标签。"""
    y = int(midx) // 12
    m = int(midx) % 12
    if m == 0:
        y -= 1
        m = 12
    return f"{y:04d}-{m:02d}"


def _safe_dt(series: pd.Series) -> pd.Series:
    """解析为 datetime 并统一到 TZ（naive 则 localize，aware 则 convert）。"""
    dt = pd.to_datetime(series, errors="coerce")
    if dt.dt.tz is None:
        dt = dt.dt.tz_localize(CFG.TZ, ambiguous="infer", nonexistent="shift_forward")
    else:
        dt = dt.dt.tz_convert(CFG.TZ)
    return dt


def _wilson_ci(p: float, n: int, z: float) -> Tuple[float, float]:
    """比例 Wilson 95% 置信区间（小样本稳健）。"""
    if n <= 0:
        return (0.0, 0.0)
    if p < 0:
        p = 0.0
    if p > 1:
        p = 1.0
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    var = (p * (1 - p) / n) + (z * z / (4 * n * n))
    half = z * (var ** 0.5) / denom
    lo = max(0.0, center - half)
    hi = min(1.0, center + half)
    return (lo, hi)


# ==================== 第一段：HardBlock 输入校验 ====================
def validate_input(df: pd.DataFrame) -> Dict[str, Any]:
    """HardBlock 5 步。返回 {'status':'ok','df':清洗后df} 或 {'status':'skipped','reason':...}。

    注：缺失核心列由引擎 can_run 在 compute 前拦截，此处仅双保险。
    """
    # 1. 列存在性
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        return {"status": "skipped", "reason": "missing_core_columns", "missing": missing}

    work = df.copy()
    work["__dt__"] = _safe_dt(work["订单时间"])

    # 3. 未来时间过滤
    today = pd.Timestamp.now(CFG.TZ)
    tol = pd.Timedelta(days=CFG.FUTURE_TOLERANCE_DAYS)
    future_mask = work["__dt__"] > (today + tol)
    future_rows = int(future_mask.sum())
    total = len(work)
    if total > 0 and future_rows / total > CFG.FUTURE_SKIP_RATIO:
        return {"status": "skipped", "reason": "future_order_time_suspected",
                "future_rows": future_rows, "total": total}
    work = work[~future_mask].copy()

    # 4. 订单状态过滤（条件列存在才做）
    if "订单状态" in work.columns:
        valid = work[work["订单状态"].isin(CFG.STATUS_WHITELIST)]
        # 白名单命中 → 仅保留有效订单（剔除 canceled/unavailable 等无效单）
        if len(valid) > 0:
            work = valid.copy()
        # 零命中（如状态词表与白名单语言完全对不上）→ 白名单不适用，兜底保留全量

    # 5. 订单ID 控重纪律在聚合阶段处理；此处仅保证列就绪
    return {"status": "ok", "df": work, "future_rows": future_rows}


# ==================== 第二段：Base 基座计算 ====================
def compute_base(work: pd.DataFrame) -> Dict[str, Any]:
    """Base 层：cohort 锚点 + Index_j + U_ij/R_ij + 留存率/客单价 + Wilson CI + 最小观察期。

    一致性原则（数据能用 ⟺ 月份算进窗口）：三角矩阵只保留目标月 (i+j) 也在
    cohort_labels（即真实存在的首单月）里的格子；其余格子不进字典，渲染为灰块。
    """
    df = work.copy()

    # 剔除无有效订单日期的行：无法解析为日期(NaT)的记录不能归入任何 cohort，
    # 否则下方 Index_j 的强转整数会在 NaN 上抛 IntCastingNaNError。
    n_bad = int(df["__dt__"].isna().sum())
    if n_bad:
        df = df[df["__dt__"].notna()].copy()

    # cohort 锚点（每用户最早订单月）
    first_dt = df.groupby("用户ID")["__dt__"].transform("min")
    df["Cohort_Month"] = _month_index(first_dt)
    order_m = _month_index(df["__dt__"])
    # 用可空整数类型，杜绝任何残留 NaN 触发强转崩溃
    df["Index_j"] = (order_m - df["Cohort_Month"]).astype("Int64")

    # 金额按 订单ID 去重控重
    if "订单ID" in df.columns:
        agg_src = df.drop_duplicates(subset=["订单ID"], keep="first")
    else:
        agg_src = df

    agg = agg_src.groupby(["Cohort_Month", "Index_j"]).agg(
        U_ij=("用户ID", "nunique"),
        R_ij=("订单实付金额", "sum"),
    ).reset_index()

    if agg.empty:
        return {"empty": True, "agg": agg}

    now = pd.Timestamp.now(CFG.TZ)
    today_month = now.year * 12 + now.month

    # 每 cohort 总规模（j=0 的用户数）
    size = agg.loc[agg["Index_j"] == 0].set_index("Cohort_Month")["U_ij"].to_dict()

    # 仅纳入成熟 cohort（未成熟整行不进图）
    agg = agg.copy()
    agg["mature"] = (today_month - agg["Cohort_Month"]) >= CFG.MIN_OBSERVATION_MONTHS
    included = agg[agg["mature"]].copy()
    if included.empty:
        included = agg.copy()  # 无成熟 cohort 时退化为全量，避免完全空白

    included = included.copy()
    included["cohort_size"] = included["Cohort_Month"].map(size).fillna(0)
    # 整列 numpy 向量化（替代逐行 apply）：除数为 0 处填 np.nan，
    # 下游 pd.notna 判定与旧 else None 语义一致。
    included["retention"] = np.where(
        included["cohort_size"] > 0, included["U_ij"] / included["cohort_size"], np.nan)
    included["arpu"] = np.where(
        included["U_ij"] > 0, included["R_ij"] / included["U_ij"], np.nan)

    # Wilson 95% CI（仅留存率为比例，适用）
    included["ci_lower"] = None
    included["ci_upper"] = None
    for idx, r in included.iterrows():
        if pd.notna(r["retention"]) and r["cohort_size"] > 0:
            lo, hi = _wilson_ci(r["retention"], int(r["cohort_size"]), CFG.WILSON_Z)
            included.at[idx, "ci_lower"] = lo
            included.at[idx, "ci_upper"] = hi

    cohort_labels = sorted(included["Cohort_Month"].unique().tolist())
    cohort_set = set(cohort_labels)
    # 列宽锚定「最后一个真实 cohort 月」，斜边干净闭合到末 cohort 行。
    # 回退此前 A 方案（把边界拉到数据真实最新下单月）造成的悬空灰列。
    if cohort_labels:
        min_cohort = min(cohort_labels)
        last_cohort = max(cohort_labels)
        max_j = min(last_cohort - min_cohort, _SUMMARY_COHORT_WINDOW - 1)
    else:
        max_j = 0

    # 构建稀疏三角矩阵字典（仅已观测 (i,j) 有值；未观测不在此 dict 中）。
    # 一致性过滤：目标月 (i+j) 不在 cohort 窗口 → 其复购数据不能用，跳过。
    ret: Dict[Tuple[int, int], Optional[float]] = {}
    arpu: Dict[Tuple[int, int], Optional[float]] = {}
    ci: Dict[Tuple[int, int], Tuple[float, float]] = {}
    for _, r in included.iterrows():
        i = r["Cohort_Month"]
        j = int(r["Index_j"])
        if (i + j) not in cohort_set:   # 目标月没进窗口 → 数据不能用，留空
            continue
        ret[(i, j)] = r["retention"] if pd.notna(r["retention"]) else None
        arpu[(i, j)] = r["arpu"]
        if r["ci_lower"] is not None:
            ci[(i, j)] = (r["ci_lower"], r["ci_upper"])

    return {
        "empty": False,
        "agg": agg,
        "included": included,
        "size": size,
        "cohort_labels": cohort_labels,
        "cohort_label_map": {m: _mi_to_label(m) for m in cohort_labels},
        "max_j": max_j,
        "today_month": today_month,
        "retention": ret,
        "arpu": arpu,
        "ci": ci,
    }


# ==================== 三张卡片聚合（按前端热力图可视窗口，供第三方直接渲染） ====================
# 须与 src/echart_generator.py 的 _COHORT_WINDOW_MONTHS 对齐（前端画图截断口径）
_SUMMARY_COHORT_WINDOW = 12


def _compute_summary_cards(base: Dict[str, Any]) -> Dict[str, Any]:
    """按前端热力图可视窗口（最近 12 个 cohort）聚合三张卡片。

    口径遵循总原则——留存率相关去 j=0、金额类保留 j=0：
      - average_arpu / total_revenue：含 j=0（首单当月客单价纳入，反映获客质量）
      - overall_retention_rate：单独去 j=0（j=0 恒=1 会虚高整体留存率）
      - detail_rows：含 j=0（原始明细，供第三方自行重算任意口径）
      - source.aggregates：
          total_revenue / retention_user_sum 含 j=0；
          total_cohort_size = 窗口内各 cohort 初始规模去重真值（非按 j 行重复累加）；
          retention_avg = 去 j=0 留存率均值
    直接基于原始分子分母（R_ij / U_ij / cohort_size）算，不依赖比值反算，
    第三方拿到即可渲染，无需自行推算。
    """
    inc = base.get("included")
    if inc is None or len(inc) == 0:
        return {}
    labels = base["cohort_labels"]
    win_labels = labels[-_SUMMARY_COHORT_WINDOW:] if len(labels) > _SUMMARY_COHORT_WINDOW else labels
    win_set = set(win_labels)
    _W = _SUMMARY_COHORT_WINDOW
    # ARPU 类口径：含 j=0（首单当月客单价纳入，反映获客质量）
    # 一致性过滤：目标月 (i+j) 必须也在窗口内——某月的复购数据只有在其自身
    # 也是 cohort 行（算进窗口）时才能被计入，否则不能填（与热力图口径统一）。
    target_in_win = (inc["Cohort_Month"] + inc["Index_j"]).isin(win_set)
    sub_arpu = inc[(inc["Cohort_Month"].isin(win_set)) & target_in_win & (inc["Index_j"].between(0, _W - 1))].copy()
    # 留存率口径：去 j=0（j=0 恒=1 会虚高整体留存率，单独计算）
    sub_ret = inc[(inc["Cohort_Month"].isin(win_set)) & target_in_win & (inc["Index_j"].between(1, _W - 1))].copy()
    if sub_arpu.empty and sub_ret.empty:
        return {}
    sum_r = float(sub_arpu["R_ij"].sum())
    sum_u_arpu = float(sub_arpu["U_ij"].sum())
    avg_arpu = (sum_r / sum_u_arpu) if sum_u_arpu > 0 else 0.0
    sum_u_ret = float(sub_ret["U_ij"].sum())
    sum_n = float(sub_ret["cohort_size"].sum())
    overall_ret = (sum_u_ret / sum_n) if sum_n > 0 else 0.0
    # 真实总初始规模：每个 cohort 仅计一次 cohort_size（去重），
    # 避免按 sub_ret 的 j=1..11 每行重复累加导致放大约 11 倍。
    size_real = float(sub_arpu.groupby("Cohort_Month")["cohort_size"].first().sum())

    # 原始明细行（窗口内，含 j=0），供第三方自行重算任意卡片口径
    ret_series = sub_ret["retention"].dropna()
    ret_vals = [float(v) for v in ret_series.tolist()]
    detail_rows = []
    for _, r in sub_arpu.iterrows():
        raw_ret = r.get("retention")
        ret_val = (round(float(raw_ret), 4)
                   if raw_ret is not None and not (isinstance(raw_ret, float) and raw_ret != raw_ret)
                   else None)
        detail_rows.append({
            "Cohort_Month": int(r["Cohort_Month"]),
            "Index_j": int(r["Index_j"]),
            "R_ij": round(float(r["R_ij"]), 4),
            "U_ij": round(float(r["U_ij"]), 4),
            "cohort_size": round(float(r["cohort_size"]), 4),
            "retention": ret_val,
        })

    return {
        "window": {
            "cohorts": len(win_labels),
            "max_index_j": _W - 1,
            "cohort_labels": [base["cohort_label_map"][m] for m in win_labels],
        },
        "cards": [
            {"key": "average_arpu", "label": "Average ARPU",
             "value": round(avg_arpu, 2), "unit": "元"},
            {"key": "total_revenue", "label": "Total Revenue",
             "value": round(sum_r, 2), "unit": "元"},
            {"key": "overall_retention_rate", "label": "Overall Retention Rate",
             "value": round(overall_ret, 4), "unit": "ratio"},
        ],
        # 第三方重算所需的原始数据（分子/分母明细 + 聚合值）
        "source": {
            "aggregates": {
                "total_revenue": round(sum_r, 2),
                # 窗口内各期留存用户「人次」之和（含 j=0 各期累加），非去重用户数
                "retention_user_sum": round(sum_u_arpu, 2),
                # 窗口内各 cohort 初始规模之和（每 cohort 仅计一次，去重真实值）
                "total_cohort_size": round(size_real, 2),
                "retention_avg": round(float(sum(ret_vals) / len(ret_vals)), 4) if ret_vals else 0.0,
                "retention_count": len(ret_vals),
            },
            "rows": detail_rows,
        },
    }


# ==================== 基座可视化（下三角热力图） ====================
def _heatmap_chart_data(slot: str, title: str, base: Dict[str, Any],
                        value_key: str, with_ci: bool,
                        drop_j0: bool = True) -> ChartData:
    """通用下三角热力图 ChartData 构造。value_key ∈ {'retention','arpu'}。

    drop_j0：
      - False（当前基座两图均含 j=0）→ j 从 0 起：保留主对角线 j=0 列，
        留存率恒为 1（100% 基线），ARPU 为首单当月客单价。用户要求
        「各同期群留存率（下三角）」也纳入 j=0 列，与 ARPU 图口径对齐。
      - True → j 从 1 起，严格剔除 j=0 基线列（如需此口径可显式传 True）。

    截断口径：与 _compute_summary_cards / echart_generator._COHORT_WINDOW_MONTHS
    一致——最近 _SUMMARY_COHORT_WINDOW 个 cohort × Index_j ∈ [j_start, _W)。
    在打包阶段即窗口化，使 ChartData.data 与三张卡片共用同一窗口，
    第三方/前端拿到数据即已截断，无需在渲染端再次截断。
    """
    src = base[value_key]
    _W = _SUMMARY_COHORT_WINDOW
    all_labels = base["cohort_labels"]  # 升序整数月键
    win_labels = all_labels[-_W:] if len(all_labels) > _W else all_labels
    win_label_strs = [base["cohort_label_map"][m] for m in win_labels]
    max_j = base["max_j"]
    j_max = min(max_j, _W - 1)
    j_start = 0 if not drop_j0 else 1
    j_list = list(range(j_start, j_max + 1))
    ci = base["ci"] if with_ci else None
    rows = []
    for yi, m in enumerate(win_labels):
        for j in j_list:
            v = src.get((m, j), None)
            if v is None or (isinstance(v, float) and v != v):
                # 未观测 → 哨兵值（生成器用灰块渲染）
                rows.append({"Index_j": j, "首单月": win_label_strs[yi], "value": SENTINEL})
            else:
                row = {"Index_j": j, "首单月": win_label_strs[yi], "value": round(float(v), 4)}
                if with_ci:
                    c = ci.get((m, j))
                    if c:
                        row["ci_lower"] = round(float(c[0]), 4)
                        row["ci_upper"] = round(float(c[1]), 4)
                rows.append(row)
    return ChartData(slot=slot, chart_type="cohort_heatmap", title=title,
                     x="Index_j", y="首单月", data=rows)


# ==================== KPI 年同比（相同日历月对齐）辅助函数 ====================
def _paired_month_sets(avail: List[int]) -> Tuple[List[int], List[int]]:
    """相同日历月对齐年同比：返回 (cur, prev)。

    cur = [m for m in avail if (m - 12) in avail]（今年某月存在且去年同月也存在）；
    prev = [m - 12 for m in cur]（对应的去年同月）。
    数据不足的同月自动跳过；若无任何配对，cur/prev 均为空列表。
    """
    avail_set = set(avail)
    cur = sorted(m for m in avail_set if (m - 12) in avail_set)
    prev = sorted((m - 12) for m in cur)
    return cur, prev


def _window_revenue(work: pd.DataFrame, month_set: set) -> Tuple[float, float, int]:
    """按订单发生月集合聚合营收/客单价。

    口径与 _build_kpis 全表算法一致（按 订单ID 去重控重）：
      - total_revenue：窗内去重订单的 订单实付金额 合计
      - arpu：total_revenue / 去重订单数
      - order_count：窗内去重订单数
    返回 (total_revenue, arpu, order_count)。month_set 为空 → 全 0。
    """
    if not month_set:
        return 0.0, 0.0, 0
    mi = _month_index(work["__dt__"])
    sub = work[mi.isin(month_set)]
    if len(sub) == 0:
        return 0.0, 0.0, 0
    if "订单ID" in sub.columns:
        gmv_src = sub.drop_duplicates(subset=["订单ID"], keep="first")
    else:
        gmv_src = sub
    total_revenue = float(gmv_src["订单实付金额"].sum())
    order_count = len(gmv_src)
    arpu = (total_revenue / order_count) if order_count else 0.0
    return total_revenue, arpu, order_count


def _window_retention(inc: pd.DataFrame, month_set: set) -> float:
    """按用户首单月（Cohort_Month）集合聚合 M1 留存率。

    M1留存率 = ΣU_ij(Index_j==1) / ΣU_ij(Index_j==0)，口径与 _build_kpis 全表算法一致。
    month_set 为空或分母为 0 → 0.0。
    """
    if not month_set or len(inc) == 0:
        return 0.0
    sub = inc[inc["Cohort_Month"].isin(month_set)]
    u1 = float(sub[sub["Index_j"] == 1]["U_ij"].sum())
    u0 = float(sub[sub["Index_j"] == 0]["U_ij"].sum())
    return (u1 / u0) if u0 > 0 else 0.0


def _pct_change(curr: float, prev: float) -> str:
    """涨跌幅字符串：prev 为空/0 或窗空 → ""；否则 f"{(curr-prev)/prev*100:+.1f}%"。

    带显式 +/- 符号，与 package_render._infer_trend 兼容（+x%→up、-x%→down）。
    """
    if prev is None or prev == 0 or curr is None:
        return ""
    return f"{(curr - prev) / prev * 100:+.1f}%"


# ==================== KPI / 洞察 / 结论 ====================
def _build_kpis(work: pd.DataFrame, base: Dict[str, Any]) -> List[KPIItem]:
    total_users = int(work["用户ID"].nunique())
    total_cohorts = len(base["cohort_labels"])

    # 全表口径（无同月配对时回退使用，保证卡片始终有数）
    if "订单ID" in work.columns:
        gmv_src = work.drop_duplicates(subset=["订单ID"], keep="first")
    else:
        gmv_src = work
    total_gmv_full = float(gmv_src["订单实付金额"].sum())
    order_count_full = len(gmv_src)
    avg_order_full = total_gmv_full / order_count_full if order_count_full else 0.0

    # 全表 M1 留存率（基于 agg：含所有可观测 cohort，含 1 个月大的新 cohort）
    # 作为回退，保证 value 口径与窗口一致。
    agg_df = base["agg"]
    u1_full = float(agg_df[agg_df["Index_j"] == 1]["U_ij"].sum())
    u0_full = float(agg_df[agg_df["Index_j"] == 0]["U_ij"].sum())
    m1_ret_full = (u1_full / u0_full) if u0_full > 0 else 0.0

    if "退款金额" in work.columns:
        refund = float(work["退款金额"].fillna(0).sum())
        refund_rate = (refund / total_gmv_full) if total_gmv_full > 0 else 0.0
    else:
        refund_rate = 0.0

    # ---- 双轴相同日历月对齐年同比 ----
    # 营收/客单价轴：按订单发生月
    order_months = sorted(_month_index(work["__dt__"]).unique().tolist())
    cur_o, prev_o = _paired_month_sets(order_months)
    if cur_o:
        val_gmv, val_arpu, _ = _window_revenue(work, set(cur_o))
        prev_gmv, prev_arpu, _ = _window_revenue(work, set(prev_o))
    else:
        val_gmv, val_arpu, prev_gmv, prev_arpu = total_gmv_full, avg_order_full, 0.0, 0.0
    # 留存率轴：按用户首单月（Cohort_Month），用含所有可观测 cohort 的 agg
    # （cohort_labels 仅含成熟 cohort，会漏掉当年 1~5 月新 cohort，导致年同比配对失败）
    cur_c, prev_c = _paired_month_sets(sorted(agg_df["Cohort_Month"].unique().tolist()))
    val_m1 = _window_retention(agg_df, set(cur_c)) if cur_c else m1_ret_full
    prev_m1 = _window_retention(agg_df, set(prev_c)) if prev_c else 0.0

    # value 取当期窗（无配对则回退全表）；change 为年同比
    gmv_val = val_gmv if cur_o else total_gmv_full
    arpu_val = val_arpu if cur_o else avg_order_full
    m1_val = val_m1 if cur_c else m1_ret_full
    gmv_change = _pct_change(val_gmv, prev_gmv) if cur_o else ""
    arpu_change = _pct_change(val_arpu, prev_arpu) if cur_o else ""
    m1_change = _pct_change(val_m1, prev_m1) if cur_c else ""

    return [
        KPIItem(label="总同期群数", value=str(total_cohorts), kpi_type="metric"),
        KPIItem(label="总用户数", value=f"{total_users:,}", kpi_type="metric"),
        KPIItem(label="总GMV", value=f"{gmv_val:,.2f}", change=gmv_change, kpi_type="metric"),
        KPIItem(label="平均客单价", value=f"{arpu_val:,.2f}", change=arpu_change, kpi_type="metric"),
        KPIItem(label="M1留存率", value=f"{m1_val * 100:.1f}%", change=m1_change, kpi_type="metric"),
        KPIItem(label="退款率", value=f"{refund_rate * 100:.1f}%", kpi_type="metric"),
    ]


def _build_insights(base: Dict[str, Any], kpis: List[KPIItem]) -> List[str]:
    ins: List[str] = []
    n = len(base["cohort_labels"])
    ins.append(f"共识别 {n} 个成熟同期群（首单月），最小观察期 {CFG.MIN_OBSERVATION_MONTHS} 个月。")
    m1 = {m: v for (m, j), v in base["retention"].items() if j == 1 and pd.notna(v)}
    if m1:
        best = max(m1, key=lambda k: m1[k])
        worst = min(m1, key=lambda k: m1[k])
        ins.append(
            f"M1 留存率最高同期群：{base['cohort_label_map'][best]}"
            f"（{m1[best] * 100:.1f}%），最低：{base['cohort_label_map'][worst]}"
            f"（{m1[worst] * 100:.1f}%）。")
    ins.append("留存率热力图首列(j=0)为 cohort 自身基线、不计入留存衰减，请从 j=1 起观察向右下的衰减速度，可识别断崖式下跌批次。")
    return ins


def _build_conclusions(base: Dict[str, Any], kpis: List[KPIItem]) -> List[str]:
    return [
        "建议对 M1 留存率显著低于均值的同期群（疑似低质渠道/拉新活动）做渠道回查与挽留干预。",
        "客单价热力图可识别「留存还在但不再花钱」的沉默化盲区，应结合复购权益唤醒。",
    ]


# ==================== 空包（内部跳过） ====================
# 原因码 → (中文可读说明, 下一步建议)，对齐 kmeans 跳过范式
_EMPTY_REASON_MAP: Dict[str, Tuple[str, str]] = {
    # 注：missing_core_columns 分支实际不可达——
    # 引擎 run_analysis 在 model.can_run(df) 为 False（即缺核心列）时直接跳过、
    # 不调用 compute，故 _empty_package("missing_core_columns") 永不触发。
    # 引擎层已在 can_run=False 时统一返回带中文原因的占位包
    # （见 engine.run_analysis 的 can_run=False 分支内联构造）。
    # 此处保留该条，仅作防御，以防未来引擎行为变化后需要模型层兜底。
    "missing_core_columns": (
        "数据缺少同期群必需列（用户ID / 订单时间 / 订单实付金额）",
        "请确认数据集包含用户唯一标识、订单时间、订单金额三列。",
    ),
    "future_order_time_suspected": (
        "订单时间疑似含大量未来日期，已拒绝分析",
        "请检查订单时间列是否存在时区或年份错误。",
    ),
    "empty_after_filter": (
        "按订单状态过滤后无有效订单，无法构建同期群",
        "请检查订单状态列取值是否与分析模型预期一致（中文如 已完成/已支付，英文如 delivered/shipped）。",
    ),
}


def _empty_package(reason: str) -> AnalysisPackage:
    """内部跳过返回**合法 AnalysisPackage**（含 6 必填字段，绝不返回 dict）。

    同时填充 insights / suggestion，使前端 UnsupportedBlock 能展示真实原因，
    而非被通用占位文案吞掉。
    """
    ins, sug = _EMPTY_REASON_MAP.get(reason, (reason, ""))
    return AnalysisPackage(
        id="cohort",
        analysis_type="cohort",
        business_question="同期群与用户状态跃迁分析",
        algorithm="cohort_v1",
        dimension="首单月",
        metric="留存率",
        can_run=False,
        fallback_reason=reason,
        insights=[ins],
        suggestion=sug,
    )


# ==================== 模型主体 ====================
class CohortAnalysisModel(AnalysisModel):
    name = "同期群与用户状态跃迁模型"
    display_name = "同期群与用户状态跃迁"
    description = "同期群（首单月）留存率/客单价下三角矩阵 + 渠道/趋势/净毛利进阶分析"
    required_columns = REQUIRED_COLUMNS
    optional_columns = OPTIONAL_COLUMNS

    def can_run(self, df: pd.DataFrame) -> bool:
        """覆盖基类：先归一化列名再判定，避免映射后标准名导致误判缺失。"""
        if df is None or len(df.columns) == 0:
            return False
        norm = _normalize_columns(df)
        return set(self.required_columns).issubset(set(norm.columns))

    def compute(self, df: pd.DataFrame) -> AnalysisPackage:
        # 方案3：先在 raw df 上自动选最优用户键，避免把订单级键误当作用户ID
        chosen, best_rate = _select_user_key(df)
        if chosen is not None and chosen != "用户ID":
            # 防御：上游 map_dataset_columns 可能已把订单级键（如 customer_id）
            # 映射成 用户ID，而真实用户键（客户唯一ID）是另一列。直接 rename
            # 会产生两列同名 用户ID，导致下游 groupby 取到歧义列。故先丢弃
            # 旧的 用户ID 列（被选中的才是真实键），再重命名，保证唯一。
            if "用户ID" in df.columns:
                df = df.drop(columns=["用户ID"])
            df = df.rename(columns={chosen: "用户ID"})
        # 统一列名为规范中文名（兼容原始中文名与映射后标准名）
        df = _normalize_columns(df)
        # 第一段：HardBlock
        v = validate_input(df)
        if v["status"] != "ok":
            return _empty_package(v["reason"])

        work = v["df"]
        if len(work) == 0:
            return _empty_package("empty_after_filter")

        # 第二段：Base（三角斜边由 cohort 行自身决定，无需外部透传最新月）
        base = compute_base(work)
        if base.get("empty") or len(base["cohort_labels"]) == 0:
            return _empty_package("empty_after_filter")

        # 基座 2 图
        charts = [
            _heatmap_chart_data("cohort_retention", "各同期群留存率（下三角）", base, "retention", True, drop_j0=False),
            _heatmap_chart_data("cohort_arpu", "各同期群客单价 ARPU（下三角）", base, "arpu", False, drop_j0=False),
        ]

        # 第三段：Advanced A/B/C（并排，各吃 base 结果）
        from src.analysis_engine.models import cohort_advanced as adv
        charts += adv.compute_advanced_a(work, base)
        charts += adv.compute_advanced_b(base)
        charts += adv.compute_advanced_c(work, base)

        kpis = _build_kpis(work, base)
        insights = _build_insights(base, kpis)
        conclusions = _build_conclusions(base, kpis)

        # 方案5：退化诊断——复购率过低说明所选用户键可能不是真实用户，显式告警
        warn = None
        if 0.0 <= best_rate < CFG.DEGENERATE_REPEAT_RATE:
            key_label = chosen if chosen else "用户ID"
            warn = (f"同期群分析所用用户键为「{key_label}」，重复下单率仅 "
                    f"{best_rate * 100:.2f}%，未识别到明显复购行为。请确认该列是否为真实用户标识"
                    f"（一个用户应可对应多笔订单）；若数据本身无复购，下三角将退化为首单列。")
            insights = [warn] + insights

        # ===== findings：同期群 M1 留存 severity 标注（C' 改造）=====
        # 阈值写死（测试4 分布推导）：单同期群 M1 留存 <0.9% CRIT / <1.5% HIGH。
        # 方向 B「小于」语义：留存越低越严重。M1 留存 = 首单后第1月仍活跃用户占比。
        findings = []
        cohort_factory = FindingFactory("cohort")
        m1 = {m: v for (m, j), v in base["retention"].items() if j == 1 and pd.notna(v)}
        if m1:
            worst_m = min(m1, key=lambda k: m1[k])
            worst_val = m1[worst_m]
            n_low = sum(1 for v in m1.values() if v < 0.015)
            n_crit = sum(1 for v in m1.values() if v < 0.009)
            if n_crit > 0:
                sev, sev_cat = Severity.CRITICAL, FindingCategory.ANOMALY
            elif n_low > 0:
                sev, sev_cat = Severity.HIGH, FindingCategory.ANOMALY
            else:
                sev = None
            if sev is not None:
                worst_label = base["cohort_label_map"].get(worst_m, worst_m)
                findings.append(cohort_factory.create(
                    category=sev_cat,
                    title=f"存在同期群 M1 留存过低（最低 {worst_val * 100:.1f}%）",
                    metric="M1留存率",
                    entity=f"同期群 {worst_label}",
                    value=round(worst_val * 100, 2),
                    unit="%",
                    severity=sev,
                    business_meaning=(
                        f"在 {len(m1)} 个同期群中，M1 留存率最低的为 {worst_label}"
                        f"（{worst_val * 100:.1f}%），共 {n_low} 个同期群低于 1.5% 警戒线"
                        f"（其中 {n_crit} 个低于 0.9% 危急线）。首单后第1月仍活跃用户占比极低，"
                        f"反映拉新质量或首单体验问题。"
                    ),
                    business_impact=(
                        "首月留存是复购与 LTV 的基石，过低说明新客首单后迅速流失，"
                        "拉新投入回报差、增长不可持续。"
                    ),
                    recommendation=(
                        "建议对低留存同期群回溯拉新渠道与首单活动质量，"
                        "并针对首单用户设计 early-lifecycle 复购唤醒。"
                    ),
                    chart_slots=["cohort_retention"],
                ))

        return AnalysisPackage(
            id="cohort",
            analysis_type="cohort",
            business_question="同期群与用户状态跃迁分析",
            algorithm="cohort_v1",
            dimension="首单月",
            metric="留存率",
            kpis=kpis,
            chart_data=charts,
            insights=insights,
            conclusions=conclusions,
            findings=findings,
            recommendations=[],
            confidence=1.0,
            calculator_used="cohort_v1",
            template_used="cohort",
            suggestion=warn if warn else "",
            can_run=True,
            summary_cards=_compute_summary_cards(base),
        )


# 注册到分析引擎（import 本模块即注册）
register_model(CohortAnalysisModel())
