"""CLV 客户生命周期价值模型 —— 新分析引擎 AnalysisModel 实现。

三段式：HardBlock(validate_input) → Base(compute_base) → Advanced(a/b/c)。
确定性算法，无 LLM。详见 分析模型/CLV客户生命周期价值模型拆解.md。

结构严格镜像 cohort：核心在 clv.py（validate_input + compute_base + CLVAnalysisModel），
进阶在 clv_advanced.py（compute_advanced_a/b/c），三者独立触发、图全进同一个 AnalysisPackage。
"""
import logging
import math
import numpy as np
import pandas as pd

from src.analysis_engine.base import AnalysisModel
from src.analysis_engine.registry import register_model
from src.analysis_templates.base import AnalysisPackage, KPIItem, ChartData, TableData

logger = logging.getLogger("analysis.clv")

# ==================== 配置常量（对齐文档原文） ====================
CHURN_THRESHOLD_DAYS = 180   # R_churn：超过此天数未购买/未活跃视为流失
DISCOUNT_RATE = 0.0           # d：折现率，默认 0（不折现）
TOPN_RANK = 5                 # Top-N 排行榜条数
TIER_Q_LOW = 0.20             # 分层：低价值 < Q20
TIER_Q_HIGH = 0.80            # 分层：高价值 >= Q80
FUTURE_TOLERANCE_DAYS = 1     # 未来日期容忍窗口
FUTURE_SKIP_RATIO = 0.05      # 超过 5% 订单是未来日期 → 跳过


# ==================== 列名归一化（兼容「原始中文名」与「映射后标准名」） ====================
# 键=归一化后的标准列名；值=可被识别的别名（含中文/英文/常见变体）。
COLUMN_ALIASES = {
    "用户ID": ["用户ID", "用户 id", "userid", "user_id", "用户", "客户ID", "客户 id",
              "客户", "顾客ID", "顾客", "会员ID", "会员", "买家id", "买家"],
    "订单时间": ["订单时间", "下单时间", "支付时间", "成交时间", "order_time", "order_date",
              "purchase_time", "purchase_date", "date", "时间"],
    "订单实付金额": ["订单实付金额", "实付金额", "成交金额", "支付金额", "订单金额", "amount",
                "pay_amount", "paid_amount", "total_amount", "销售额", "实付", "支付额"],
    "订单ID": ["订单ID", "订单 id", "order_id", "orderid", "订单号", "交易号", "单据号"],
    # 进阶探测列
    "流量来源": ["流量来源", "来源", "渠道", "来源渠道", "获客渠道", "channel", "source",
              "utm_source", "注册渠道"],
    "商品类目": ["商品类目", "类目", "品类", "商品品类", "category", "product_category",
              "cat", "商品分类"],
    "商品成本": ["商品成本", "成本", "采购成本", "进货成本", "cost", "cost_amount", "商品采购成本"],
    "运费": ["运费", "邮费", "shipping_fee", "freight", "postage", "物流费"],
    "退款金额": ["退款金额", "退款", "refund", "refund_amount", "退款额"],
    "最后活跃时间": ["最后活跃时间", "最近活跃", "last_active", "last_login", "最近登录", "活跃时间"],
    "注册日期": ["注册日期", "注册时间", "注册日", "signup_date", "register_date",
              "register_time", "reg_date", "注册"],
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """把别名列重命名为标准列名（首个命中别名→标准名，标准名已存在则跳过）。"""
    out = df.copy()
    for std, aliases in COLUMN_ALIASES.items():
        if std in out.columns:
            continue
        for a in aliases:
            if a in out.columns:
                out = out.rename(columns={a: std})
                break
    return out


def _to_dt(s: pd.Series) -> pd.Series:
    """解析时间列：先按真实时间，失败回退网易/苏宁式 'YYYYMMDD' 整数。"""
    dt = pd.to_datetime(s, errors="coerce")
    if dt.isna().all():
        num = pd.to_numeric(s, errors="coerce")
        if num.notna().any():
            cand = pd.to_datetime(num.astype("Int64").astype(str), format="%Y%m%d", errors="coerce")
            if cand.notna().any():
                dt = cand
    return dt


# ==================== 第一段：硬性阻断层（HardBlock） ====================
def validate_input(df: pd.DataFrame):
    """校验必备 4 列 + 解析订单时间 + 过滤未来日期。"""
    if df is None or len(df.columns) == 0:
        return {"status": "skipped", "reason": "空数据", "suggestion": "请上传包含订单流水的数据表。"}
    # 处理重复列名，避免 df[col] 返回 DataFrame
    if df.columns.duplicated().any():
        df = df.loc[:, ~df.columns.duplicated()]

    work = _normalize_columns(df)

    required = ["用户ID", "订单时间", "订单实付金额", "订单ID"]
    missing = [c for c in required if c not in work.columns]
    if missing:
        return {
            "status": "skipped",
            "reason": f"缺少必备列：{missing}",
            "suggestion": "CLV 需要 4 个原始列：用户ID、订单时间、订单实付金额、订单ID。",
        }

    # 解析时间
    dt = _to_dt(work["订单时间"])
    if dt.isna().all():
        return {"status": "skipped", "reason": "订单时间无法解析为日期",
                "suggestion": "请确认「订单时间」列为标准日期格式（如 2025-01-21）。"}
    bad_ratio = dt.isna().mean()
    if bad_ratio > FUTURE_SKIP_RATIO:
        return {"status": "skipped", "reason": f"订单时间解析失败比例过高（{bad_ratio:.0%}）",
                "suggestion": "请检查「订单时间」列格式。"}
    work = work.assign(__dt__=dt)

    # 过滤未来日期
    today = pd.Timestamp.now().normalize()
    max_dt = work["__dt__"].max()
    if pd.notna(max_dt) and (max_dt - today).days > FUTURE_TOLERANCE_DAYS:
        fut = (work["__dt__"] > today + pd.Timedelta(days=FUTURE_TOLERANCE_DAYS))
        if fut.mean() > FUTURE_SKIP_RATIO:
            return {"status": "skipped", "reason": "存在大量未来日期订单",
                    "suggestion": "请确认数据时间范围是否正确。"}
        work = work[~fut].copy()

    work["订单实付金额"] = pd.to_numeric(work["订单实付金额"], errors="coerce")
    work = work.dropna(subset=["__dt__", "订单实付金额"])
    work = work[work["订单实付金额"].notna()]
    if work.empty:
        return {"status": "skipped", "reason": "有效订单行为 0", "suggestion": "请检查数据与列名。"}

    return {"status": "ok", "df": work}


# ==================== 第二段：基座计算层（Base） ====================
def compute_base(work: pd.DataFrame) -> dict:
    """2.1–2.4：流水订单表 → 每用户一行 CLV。

    返回 base 字典：user 级宽表 + 全局标量（c_hat / c_hat_eff / T_ref 等）。
    """
    T_ref = work["__dt__"].max()

    g = work.groupby("用户ID")
    M = g["订单实付金额"].sum()
    F = g["订单ID"].nunique().clip(lower=1)   # 防除零：至少 1 单
    first = g["__dt__"].min()
    last = g["__dt__"].max()

    users = pd.DataFrame({"M": M, "F": F, "first": first, "last": last})

    # 2.2 客单价 & 年购买频次
    users["AOV"] = users["M"] / users["F"]
    tenure_days = (T_ref - users["first"]).dt.days.clip(lower=1)
    users["tenure_years"] = tenure_days / 365.0
    users["F_yearly"] = users["F"] / users["tenure_years"]

    # 2.3 群体流失率（截面，近似年化）
    R = (T_ref - users["last"]).dt.days
    users["R"] = R
    N = len(users)
    churn_mask = R > CHURN_THRESHOLD_DAYS
    c_hat = float(churn_mask.sum()) / N if N > 0 else 0.0
    # 防 CLV 除零：c_hat=0 时 E[T]=1/c 发散，floor 到 1/N（最长约 N 年）
    c_hat_eff = max(c_hat, 1.0 / N) if N > 0 else c_hat

    # 2.4 单客 CLV（d=0 闭合式：AOV*F_yearly*(1-c_hat_eff)/c_hat_eff）
    r_eff = 1.0 - c_hat_eff
    denom = 1.0 + DISCOUNT_RATE - r_eff   # d=0 → = c_hat_eff
    users["CLV"] = users["AOV"] * users["F_yearly"] * (r_eff / denom)
    users = users.reset_index()  # 用户ID 复位为列

    # 2.5 分层（高/中/低，按分位切）
    if N > 0 and users["CLV"].nunique() > 1:
        q_low = users["CLV"].quantile(TIER_Q_LOW)
        q_high = users["CLV"].quantile(TIER_Q_HIGH)
        def _tier(v):
            if v >= q_high:
                return "高价值"
            if v < q_low:
                return "低价值"
            return "中价值"
        users["分层"] = np.select(
            [users["CLV"] >= q_high, users["CLV"] < q_low],
            ["高价值", "低价值"],
            default="中价值",
        )
    else:
        users["分层"] = "中价值"

    base = {
        "T_ref": T_ref,
        "c_hat": c_hat,
        "c_hat_eff": c_hat_eff,
        "churn_thresh": CHURN_THRESHOLD_DAYS,
        "d_rate": DISCOUNT_RATE,
        "N": N,
        "users": users,
    }
    return base


# ==================== 基座可视化产出（2.5） ====================
def _build_charts_base(base: dict) -> list:
    users = base["users"]
    charts = []

    # (1) 客户生命周期价值 分布直方图（等宽分箱，Y 轴对数：稀疏长尾可见）
    clv_vals = users["CLV"].dropna()
    if len(clv_vals) >= 2:
        cuts = pd.cut(clv_vals, bins=20)          # 等宽分箱（暴露真实右偏长尾）
        cnt = clv_vals.groupby(cuts, observed=True).size()
        cnt = cnt[cnt > 0]                         # 剔除空箱
        # X 轴标签改为「千元单位」短格式：5006.636~10013.139 元 → 5~10（千元），整数、去符号
        def _fmt_bin(iv):
            try:
                return f"{int(round(iv.left / 1000))}~{int(round(iv.right / 1000))}"
            except Exception:
                return str(iv)
        hist_rows = [{"客户生命周期价值（千元）": _fmt_bin(iv), "客户数（人）": int(v)} for iv, v in cnt.items()]
        charts.append(ChartData(
            slot="clv_hist", chart_type="bar",
            title="客户生命周期价值 分布直方图（等宽分箱）",
            x="客户生命周期价值（千元）", y="客户数（人）", data=hist_rows,
            chart_config={"log_y": True},          # 用户选对数，保留不变
        ))

    # (2) 客户生命周期价值 Top5 排行（水平条形图，按价值降序）
    sorted_all = users.sort_values("CLV", ascending=False).reset_index(drop=True)
    TOPN_RANK_CHART = 5
    top = sorted_all.head(TOPN_RANK_CHART)
    if len(top) > 0:
        rank_rows = []
        for i, (_, r) in enumerate(top.iterrows()):
            rank_rows.append({
                "排名": f"TOP{i + 1}",
                "用户ID": str(r["用户ID"]),
                "价值": round(float(r["CLV"]), 2),
            })
        if rank_rows:
            charts.append(ChartData(
                slot="clv_pareto", chart_type="ranking",
                title="客户生命周期价值 Top5 排行（按价值降序）",
                x="排名", y="价值", data=rank_rows,
            ))

    # (3) 客户生命周期价值 分层条形图（按分位 高/中/低）
    tier_mean = users.groupby("分层")["CLV"].mean()
    order = [t for t in ["高价值", "中价值", "低价值"] if t in tier_mean.index]
    tier_rows = [{"分层": t, "平均客户生命周期价值": round(float(tier_mean[t]), 4)} for t in order]
    if tier_rows:
        charts.append(ChartData(
            slot="clv_tier", chart_type="bar",
            title="客户生命周期价值 分层（高/中/低 平均价值）", x="分层", y="平均客户生命周期价值", data=tier_rows,
        ))

    return charts


def _build_tables_base(base: dict) -> list:
    users = base["users"].copy()
    users = users.sort_values("CLV", ascending=False).head(50)
    columns = ["用户ID", "总消费金额", "累计订单数", "平均订单金额", "年购买频次", "客户生命周期价值", "客户分层"]
    rows = []
    for _, r in users.iterrows():
        rows.append({
            "用户ID": str(r["用户ID"]),
            "总消费金额": round(float(r["M"]), 2) if pd.notna(r["M"]) else "",
            "累计订单数": int(r["F"]) if pd.notna(r["F"]) else "",
            "平均订单金额": round(float(r["AOV"]), 2) if pd.notna(r["AOV"]) else "",
            "年购买频次": round(float(r["F_yearly"]), 3) if pd.notna(r["F_yearly"]) else "",
            "客户生命周期价值": round(float(r["CLV"]), 2) if pd.notna(r["CLV"]) else "",
            "客户分层": r["分层"],
        })
    return [TableData(
        title="用户级 客户生命周期价值 明细（Top 50）",
        table_type="sort",
        columns=columns, rows=rows, slot="clv_user_detail_table",
    )]


def _build_kpis_base(base: dict) -> list:
    users = base["users"]
    N = base["N"]
    avg_clv = float(users["CLV"].mean()) if N > 0 else 0.0
    hi_cnt = int((users["分层"] == "高价值").sum())
    hi_ratio = (hi_cnt / N) if N > 0 else 0.0
    return [
        KPIItem(label="总客户数", value=f"{N:,}"),
        KPIItem(label="平均客户生命周期价值", value=f"¥{avg_clv:,.0f}"),
        KPIItem(label="群体流失率", value=f"{base['c_hat'] * 100:.1f}%"),
        KPIItem(label="高价值客户占比", value=f"{hi_ratio * 100:.1f}%",
                kpi_type="highlight"),
    ]


def _build_insights_base(base: dict) -> tuple:
    users = base["users"]
    N = base["N"]
    total_clv = float(users["CLV"].sum())
    # 长尾：Top20% 客户贡献的 CLV 占比
    if N > 0:
        sorted_clv = users["CLV"].sort_values(ascending=False).reset_index(drop=True)
        k = max(1, int(N * 0.2))
        top_share = float(sorted_clv.head(k).sum()) / total_clv if total_clv else 0.0
    else:
        top_share = 0.0
    max_clv = float(users["CLV"].max()) if N else 0.0
    min_clv = float(users["CLV"].min()) if N else 0.0

    insights = [
        f"全量 {N} 名客户平均客户生命周期价值约 ¥{float(users['CLV'].mean()):,.0f}，"
        f"区间 ¥{min_clv:,.0f} ~ ¥{max_clv:,.0f}。",
        f"头部 20% 客户贡献了约 {top_share * 100:.0f}% 的总客户生命周期价值，价值高度长尾集中。",
        f"截面群体流失率 {base['c_hat'] * 100:.1f}%（{CHURN_THRESHOLD_DAYS} 天未购买/未活跃口径）。",
    ]
    if base["c_hat_eff"] > base["c_hat"]:
        insights.append("注：因无流失样本，流失率已 floor 到 1/N 以保证 CLV 有限可算。")

    conclusions = [
        "高价值客户应重点维护（VIP/1v1），低价值客户控制投入、以自动化运营为主。",
        "CLV 基于历史客单价、年购买频次与群体流失率估算，宜结合进阶维度（渠道/类目/净毛利/客龄）细化运营策略。",
    ]
    return insights, conclusions


def _status_pkg(model, status: str, reason: str, suggestion: str) -> AnalysisPackage:
    return AnalysisPackage(
        id="", analysis_type="CLV",
        business_question="客户生命周期价值（CLV）估算",
        algorithm="CLV 三段式（Base + Advanced A/B/C）",
        dimension=None, metric="CLV",
        kpis=[KPIItem(label="状态", value=status)],
        chart_data=[], tables=[],
        insights=[reason], conclusions=[], recommendations=[],
        confidence=0.0, calculator_used="clv", template_used="CLV",
        can_run=False, fallback_reason=reason, suggestion=suggestion,
    )


# ==================== 模型类 ====================
class CLVAnalysisModel(AnalysisModel):
    name = "CLV"
    display_name = "客户生命周期价值 CLV"
    description = "用历史客单价、购买频次、流失率估算单客全生命周期总营收（Base + 进阶 A/B/C）。"
    required_columns = ["用户ID", "订单时间", "订单实付金额", "订单ID"]
    optional_columns = ["流量来源", "商品类目", "商品成本", "运费", "退款金额",
                        "最后活跃时间", "注册日期"]
    supports_advanced = True

    def can_run(self, df: pd.DataFrame) -> bool:
        if df is None or len(df.columns) == 0:
            return False
        cols = set(_normalize_columns(df).columns)
        return all(req in cols for req in self.required_columns)

    def compute(self, df: pd.DataFrame) -> AnalysisPackage:
        res = validate_input(df)
        if res["status"] != "ok":
            return _status_pkg(self, res["status"], res["reason"], res["suggestion"])

        work = res["df"]
        base = compute_base(work)

        charts = _build_charts_base(base)
        kpis = _build_kpis_base(base)
        tables = _build_tables_base(base)
        insights, conclusions = _build_insights_base(base)

        # 第三段：进阶探测层（各支独立触发）
        if self.supports_advanced:
            # 延迟 import，避免与 clv_advanced 顶部 `from .clv import ...` 形成循环导入
            from src.analysis_engine.models.clv_advanced import (
                compute_advanced_a, compute_advanced_b, compute_advanced_c,
            )
            for fn in (compute_advanced_a, compute_advanced_b, compute_advanced_c):
                try:
                    charts += fn(work, base)
                except Exception as e:  # 进阶失败不影响核心产出
                    logger.warning("[CLV] advanced %s 失败: %s", fn.__name__, e)

        return AnalysisPackage(
            id="", analysis_type="CLV",
            business_question="客户生命周期价值（CLV）估算",
            algorithm="CLV 三段式（Base + Advanced A/B/C）",
            dimension=None, metric="CLV",
            kpis=kpis, chart_data=charts, tables=tables,
            insights=insights, conclusions=conclusions, recommendations=[],
            confidence=1.0, calculator_used="clv", template_used="CLV",
            can_run=True,
            metadata={
                "version": "1.0", "display_name": self.display_name,
                "T_ref": str(base["T_ref"]),
                "c_hat": base["c_hat"], "N": base["N"],
            },
        )


register_model(CLVAnalysisModel())
