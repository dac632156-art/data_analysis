"""同期群与用户状态跃迁模型 —— 新分析引擎 AnalysisModel 实现。

三段式：HardBlock(validate_input) → Base(compute_base) → Advanced(a/b/c)。
确定性算法，无 LLM。详见 分析模型/同期群与用户状态跃迁模型拆解.md。

注意：本模块底部才 import cohort_advanced（避免与 adv 顶部的 `from .cohort import ...` 形成
模块级循环导入；adv 导入时本模块已完全定义，故安全）。
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from src.analysis_engine.base import AnalysisModel
from src.analysis_engine.registry import register_model
from src.analysis_templates.base import AnalysisPackage, KPIItem, ChartData


# ==================== 配置常量（对齐文档原文附录） ====================
@dataclass
class CohortConfig:
    TZ: str = "Asia/Shanghai"
    STATUS_WHITELIST: frozenset = frozenset({"已完成", "已支付"})
    FUTURE_TOLERANCE_DAYS: int = 1
    FUTURE_SKIP_RATIO: float = 0.05
    MIN_OBSERVATION_MONTHS: int = 6
    WILSON_Z: float = 1.96
    REFUND_ATTR: str = "refund_month"
    SHIPPING_ATTR: str = "order_month"


CFG = CohortConfig()

# ==================== 列名归一化（兼容「原始中文名」与「映射后标准名」） ====================
# 流水线 map_dataset_columns 会把部分列重命名为标准字段名（如 订单实付金额→订单总额），
# 模型内部统一以规范中文列名计算。这里把各种别名/标准名解析回规范名，避免 can_run 误判缺失。
COLUMN_ALIASES: Dict[str, List[str]] = {
    "用户ID":       ["用户ID", "user_id", "uid", "customer_id", "member_id",
                     "account_id", "客户编号", "用户编码", "会员编号", "用户标识"],
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
        work = work[work["订单状态"].isin(CFG.STATUS_WHITELIST)].copy()

    # 5. 订单ID 控重纪律在聚合阶段处理；此处仅保证列就绪
    return {"status": "ok", "df": work, "future_rows": future_rows}


# ==================== 第二段：Base 基座计算 ====================
def compute_base(work: pd.DataFrame) -> Dict[str, Any]:
    """Base 层：cohort 锚点 + Index_j + U_ij/R_ij + 留存率/客单价 + Wilson CI + 最小观察期。"""
    df = work.copy()

    # cohort 锚点（每用户最早订单月）
    first_dt = df.groupby("用户ID")["__dt__"].transform("min")
    df["Cohort_Month"] = _month_index(first_dt)
    order_m = _month_index(df["__dt__"])
    df["Index_j"] = (order_m - df["Cohort_Month"]).astype(int)

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
    included["retention"] = included.apply(
        lambda r: (r["U_ij"] / r["cohort_size"]) if r["cohort_size"] > 0 else None, axis=1)
    included["arpu"] = included.apply(
        lambda r: (r["R_ij"] / r["U_ij"]) if r["U_ij"] > 0 else None, axis=1)

    # Wilson 95% CI（仅留存率为比例，适用）
    included["ci_lower"] = None
    included["ci_upper"] = None
    for idx, r in included.iterrows():
        if r["retention"] is not None and r["cohort_size"] > 0:
            lo, hi = _wilson_ci(r["retention"], int(r["cohort_size"]), CFG.WILSON_Z)
            included.at[idx, "ci_lower"] = lo
            included.at[idx, "ci_upper"] = hi

    cohort_labels = sorted(included["Cohort_Month"].unique().tolist())
    max_j = int(included["Index_j"].max()) if len(included) else 0

    # 构建稀疏三角矩阵字典（仅已观测 (i,j) 有值；未观测不在此 dict 中）
    ret: Dict[Tuple[int, int], Optional[float]] = {}
    arpu: Dict[Tuple[int, int], Optional[float]] = {}
    ci: Dict[Tuple[int, int], Tuple[float, float]] = {}
    for _, r in included.iterrows():
        i = r["Cohort_Month"]
        j = int(r["Index_j"])
        ret[(i, j)] = r["retention"]
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


# ==================== 基座可视化（下三角热力图） ====================
def _heatmap_chart_data(slot: str, title: str, base: Dict[str, Any],
                        value_key: str, with_ci: bool) -> ChartData:
    """通用下三角热力图 ChartData 构造。value_key ∈ {'retention','arpu'}。"""
    src = base[value_key]
    cohort_labels = [base["cohort_label_map"][m] for m in base["cohort_labels"]]
    max_j = base["max_j"]
    j_list = list(range(max_j + 1))
    ci = base["ci"] if with_ci else None
    rows = []
    for yi, m in enumerate(base["cohort_labels"]):
        for j in j_list:
            v = src.get((m, j), None)
            if v is None or (isinstance(v, float) and v != v):
                # 未观测 → 哨兵值（生成器用灰块渲染）
                rows.append({"Index_j": j, "首单月": cohort_labels[yi], "value": SENTINEL})
            else:
                row = {"Index_j": j, "首单月": cohort_labels[yi], "value": round(float(v), 4)}
                if with_ci:
                    c = ci.get((m, j))
                    if c:
                        row["ci_lower"] = round(float(c[0]), 4)
                        row["ci_upper"] = round(float(c[1]), 4)
                rows.append(row)
    return ChartData(slot=slot, chart_type="cohort_heatmap", title=title,
                     x="Index_j", y="首单月", data=rows)


# ==================== KPI / 洞察 / 结论 ====================
def _build_kpis(work: pd.DataFrame, base: Dict[str, Any]) -> List[KPIItem]:
    total_users = int(work["用户ID"].nunique())
    total_cohorts = len(base["cohort_labels"])

    if "订单ID" in work.columns:
        gmv_src = work.drop_duplicates(subset=["订单ID"], keep="first")
    else:
        gmv_src = work
    total_gmv = float(gmv_src["订单实付金额"].sum())
    order_count = len(gmv_src)
    avg_order = total_gmv / order_count if order_count else 0.0

    inc = base["included"]
    m1 = inc[inc["Index_j"] == 1]
    u1 = float(m1["U_ij"].sum())
    u0 = float(inc[inc["Index_j"] == 0]["U_ij"].sum())
    m1_ret = (u1 / u0) if u0 > 0 else 0.0

    if "退款金额" in work.columns:
        refund = float(work["退款金额"].fillna(0).sum())
        refund_rate = (refund / total_gmv) if total_gmv > 0 else 0.0
    else:
        refund_rate = 0.0

    return [
        KPIItem(label="总同期群数", value=str(total_cohorts), kpi_type="metric"),
        KPIItem(label="总用户数", value=f"{total_users:,}", kpi_type="metric"),
        KPIItem(label="总GMV", value=f"{total_gmv:,.2f}", kpi_type="metric"),
        KPIItem(label="平均客单价", value=f"{avg_order:,.2f}", kpi_type="metric"),
        KPIItem(label="M1留存率", value=f"{m1_ret * 100:.1f}%", kpi_type="metric"),
        KPIItem(label="退款率", value=f"{refund_rate * 100:.1f}%", kpi_type="metric"),
    ]


def _build_insights(base: Dict[str, Any], kpis: List[KPIItem]) -> List[str]:
    ins: List[str] = []
    n = len(base["cohort_labels"])
    ins.append(f"共识别 {n} 个成熟同期群（首单月），最小观察期 {CFG.MIN_OBSERVATION_MONTHS} 个月。")
    m1 = {m: v for (m, j), v in base["retention"].items() if j == 1 and v is not None}
    if m1:
        best = max(m1, key=lambda k: m1[k])
        worst = min(m1, key=lambda k: m1[k])
        ins.append(
            f"M1 留存率最高同期群：{base['cohort_label_map'][best]}"
            f"（{m1[best] * 100:.1f}%），最低：{base['cohort_label_map'][worst]}"
            f"（{m1[worst] * 100:.1f}%）。")
    ins.append("留存率热力图对角线恒为 1（首单当月），向右下观察衰减速度可识别断崖式下跌批次。")
    return ins


def _build_conclusions(base: Dict[str, Any], kpis: List[KPIItem]) -> List[str]:
    return [
        "建议对 M1 留存率显著低于均值的同期群（疑似低质渠道/拉新活动）做渠道回查与挽留干预。",
        "客单价热力图可识别「留存还在但不再花钱」的沉默化盲区，应结合复购权益唤醒。",
    ]


# ==================== 空包（内部跳过） ====================
def _empty_package(reason: str) -> AnalysisPackage:
    """内部跳过返回**合法 AnalysisPackage**（含 6 必填字段，绝不返回 dict）。"""
    return AnalysisPackage(
        id="cohort",
        analysis_type="cohort",
        business_question="同期群与用户状态跃迁分析",
        algorithm="cohort_v1",
        dimension="首单月",
        metric="留存率",
        can_run=False,
        fallback_reason=reason,
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
        # 统一列名为规范中文名（兼容原始中文名与映射后标准名）
        df = _normalize_columns(df)
        # 第一段：HardBlock
        v = validate_input(df)
        if v["status"] != "ok":
            return _empty_package(v["reason"])

        work = v["df"]
        if len(work) == 0:
            return _empty_package("empty_after_filter")

        # 第二段：Base
        base = compute_base(work)
        if base.get("empty") or len(base["cohort_labels"]) == 0:
            return _empty_package("empty_after_filter")

        # 基座 2 图
        charts = [
            _heatmap_chart_data("cohort_retention", "各同期群留存率（下三角）", base, "retention", True),
            _heatmap_chart_data("cohort_arpu", "各同期群客单价 ARPU（下三角）", base, "arpu", False),
        ]

        # 第三段：Advanced A/B/C（并排，各吃 base 结果）
        from src.analysis_engine.models import cohort_advanced as adv
        charts += adv.compute_advanced_a(work, base)
        charts += adv.compute_advanced_b(base)
        charts += adv.compute_advanced_c(work, base)

        kpis = _build_kpis(work, base)
        insights = _build_insights(base, kpis)
        conclusions = _build_conclusions(base, kpis)

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
            recommendations=[],
            confidence=1.0,
            calculator_used="cohort_v1",
            template_used="cohort",
            can_run=True,
        )


# 注册到分析引擎（import 本模块即注册）
register_model(CohortAnalysisModel())
