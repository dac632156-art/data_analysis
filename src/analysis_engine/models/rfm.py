"""RFM 用户分层模型 —— 新分析引擎 AnalysisModel 实现。

三段式：HardBlock(列校验) → Base(8 分层打分) → Advanced(A 结构 / B 动态 / C 价值)。
确定性算法，无 LLM。详见 分析模型/RFM用户分层模型拆解.md。

8 群体映射规则（经文档两个示例校验）：
  重要/一般 ← M（M 高 = 重要）
  价值/保持/发展/挽留 ← (R, F)：
    价值 = R高 F高；保持 = R高 F低；发展 = R低 F高；挽留 = R低 F低
  校验：用户甲 (R高,F高,M高) → 高价值核心客户；用户乙 (R低,F低,M高) → 流失预警高价值客户。
"""
from typing import Any, Dict, List, Optional, Tuple
import bisect
import math
import pandas as pd
import numpy as np

from src.analysis_engine.base import AnalysisModel
from src.analysis_engine.registry import register_model
from src.analysis_templates.base import AnalysisPackage, KPIItem, ChartData, TableData


# ==================== 列名归一化 ====================
# 支持两种输入形态（canon 名 = 映射词典 column_mapping_dict.yaml 标准名）：
#  · 交易级（流水）：用户ID + 订单时间(算R) + 订单实付金额(算M) + 订单ID(算F=去重订单数)
#  · 用户级预聚合：用户ID + 距上次登录天数(已算好的近度) + 订单实付金额(M，如 Total_Spending) + 订单ID(购买频率值)
#    例：测试1 的 User_ID / Last_Login_Days_Ago / Total_Spending / Purchase_Frequency / Location
COLUMN_ALIASES: Dict[str, List[str]] = {
    "用户ID":   ["用户ID", "User_ID", "user_id", "uid", "customer_id",
                  "Customer ID", "member_id", "account_id", "客户编号",
                  "用户编码", "会员编号", "用户标识"],
    # 交易级 R 来源：订单时间（明细）→ 算近度；预聚合形态用「距上次登录天数」直接作 R 值
    "订单时间": ["订单时间", "消费日期", "最近消费日期", "order_time", "order_date",
                  "支付时间", "购买时间", "下单时间", "订单日期", "last_order_date"],
    # 预聚合形态：R 已算成「距今天数」（近度，越大越久未购）
    "距上次登录天数": ["距上次登录天数", "R天数", "Last_Login_Days_Ago", "最近购买间隔天数",
                  "Recency", "R", "recency", "最近消费间隔", "最近登录天数",
                  "days_ago", "last_login_days_ago", "recency_days"],
    # 订单实付金额(M)：交易级 Σ；「总金额类」别名前置、「平均客单价类」后置——
    # 二者并存（如同批含 总消费金额 + 平均客单价）时优先选总金额，
    # 避免把平均值误当总消费。别名同时覆盖「列名映射词典」产出的标准词。
    "订单实付金额": ["订单实付金额", "消费金额", "净毛利", "总消费金额", "Total_Spending", "total_spending",
                  "总金额", "累计消费", "用户GMV", "用户终身价值", "ltv", "gmv_user",
                  "total_amount", "订单总额", "购买金额", "订单金额", "total_payment",
                  "payment_value", "实付金额", "付款金额", "支付金额", "amount",
                  "profit", "M", "Monetary",
                  "Average_Order_Value", "平均客单价", "aov", "average_order_value"],
    # F = 去重订单数（交易级）；预聚合形态「购买频率/消费次数」归一成 订单ID 后直接取
    "订单ID":   ["订单ID", "order_id", "订单编号", "单据ID",
                  "消费次数", "购买次数", "Purchase_Frequency", "购买频率", "频率", "频次",
                  "F", "frequency", "purchase_count", "order_count", "次数"],
    # 进阶 A 渠道/类目细分（RFM md 进阶列，作识别用）
    "流量来源": ["流量来源", "traffic_source", "source", "渠道", "channel", "流量渠道"],
    "商品类目": ["商品类目", "category", "类目", "商品分类", "产品类目", "category_name"],
    # 进阶 B 时间动态（模型内部自推导月份，列作识别用）
    "订单年月": ["订单年月", "order_month", "年月", "ym", "year_month"],
    "住址":     ["住址", "地域", "省份", "省", "城市", "地区", "region", "province",
                  "city", "area", "地区名称", "所在地区", "Location", "location"],
    "商品成本": ["商品成本", "cost", "进货成本", "成本价", "cost_usd", "cost_price"],
    "退款金额": ["退款金额", "refund_amount", "refunded_amount", "退款额", "退费金额"],
    "运费":     ["运费", "shipping_fee", "freight", "delivery_fee", "shipping_cost", "邮费", "配送费"],
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename: Dict[str, str] = {}
    for canon, aliases in COLUMN_ALIASES.items():
        for a in aliases:
            if a in df.columns:
                rename[a] = canon
                break
    if not rename:
        return df
    return df.rename(columns=rename)


# RFM 严格列（含订单ID）：满足则跑 RFM 8 群
_RFM_STRICT = {"用户ID", "订单实付金额", "订单时间", "订单ID"}
# USER_SEG 降级列（无订单ID）：满足则降级到 K-means 用户分层聚类（仅 M+R 两维）
_RFM_USERSEG = {"用户ID", "订单实付金额", "订单时间"}
_RFM_PREAGG = {"用户ID", "订单实付金额", "订单ID", "距上次登录天数"}
_R_SOURCES = ["订单时间", "距上次登录天数"]

# 文档 8 个标准群体名（顺序固定，便于占比折线/热力图对齐）
SEGMENTS = [
    "高价值核心客户", "潜力高价值客户", "沉睡高价值客户", "流失预警高价值客户",
    "稳定普通客户", "潜力普通客户", "沉睡普通客户", "流失预警普通客户",
]

# 8 群体 通用运营策略（标准 RFM 领域知识；可后续按业务细化）
SEGMENT_INFO: Dict[str, Dict[str, str]] = {
    "高价值核心客户": {"定义": "R 近、F 高、M 高：近期高频高额消费的核心用户。",
                  "含义": "最优质客户，贡献主要营收，忠诚度高。",
                  "策略": "VIP 专属权益 + 新品优先体验 + 会员等级维系，防流失。",
                  "转化路径": "潜力高价值客户/沉睡高价值客户 → 高价值核心客户（升舱重点对象）。"},
    "潜力高价值客户": {"定义": "R 近、F 低、M 高：近期消费、客单高但频次偏低。",
                  "含义": "高价值但互动不频繁，有沉睡倾向。",
                  "策略": "提升复购：订阅/周期购、凑单券、关联推荐。",
                  "转化路径": "潜力高价值客户 → 高价值核心客户（拉频次）。"},
    "沉睡高价值客户": {"定义": "R 远、F 高、M 低：频次高但客单低、已有一阵没来。",
                  "含义": "活跃度下降的潜力客户。",
                  "策略": "客单提升 + 召回唤醒（push/短信），防滑向挽留。",
                  "转化路径": "沉睡高价值客户 → 高价值核心客户（提客单 + 拉回近度）。"},
    "流失预警高价值客户": {"定义": "R 远、F 低、M 高：高消费但很久没来、也不常来，流失风险最高。",
                  "含义": "高价值流失预警群体。",
                  "策略": "高力度召回（专属优惠/客户经理）、赢回 campaign。",
                  "转化路径": "流失预警高价值客户 → 沉睡高价值客户/高价值核心客户（紧急赢回）。"},
    "稳定普通客户": {"定义": "R 远、F 高、M 高（一般侧高价值）：远期高频高额，规模盘基本盘。",
                  "含义": "潜力价值客户，沉淀的优质长尾。",
                  "策略": "标准化会员运营 + 向上销售，逐步跨重要门槛。",
                  "转化路径": "稳定普通客户 → 高价值核心客户（跨重要门槛）。"},
    "潜力普通客户": {"定义": "R 近、F 低、M 低：近期来过但消费清淡。",
                  "含义": "低活跃低价值新客/散客。",
                  "策略": "培育：首单礼、小额满减引导复购。",
                  "转化路径": "潜力普通客户 → 沉睡普通客户/稳定普通客户（养熟）。"},
    "沉睡普通客户": {"定义": "R 远、F 高、M 低：频次尚可但客单低且疏远。",
                  "含义": "价格敏感型老客。",
                  "策略": "组合装/升档引导提升客单，温和召回。",
                  "转化路径": "沉睡普通客户 → 稳定普通客户（提客单）。"},
    "流失预警普通客户": {"定义": "R 远、F 低、M 低：全低，沉默低质客。",
                  "含义": "最小投入群体。",
                  "策略": "低成本批量唤醒或自然流失，不投入重资源。",
                  "转化路径": "流失预警普通客户 → 沉睡普通客户（低成本试探）。"},
}


# ==================== 安全工具（本地，不依赖 analysis_templates） ====================
def _safe(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def _safe_div(a: Any, b: Any, default: float = 0.0) -> float:
    try:
        if b is None or b == 0:
            return default
        r = a / b
        if isinstance(r, float) and (math.isnan(r) or math.isinf(r)):
            return default
        return r
    except (TypeError, ValueError, ZeroDivisionError):
        return default


def _bin_score(s: pd.Series, ascending: bool, q: int = 5) -> pd.Series:
    """等频分箱为 1~q 分；ascending=True 时小值→低分。"""
    r = s.rank(method="first", pct=True, ascending=ascending)
    score = np.ceil(r * q)
    return score.clip(1, q).astype(int)


def _score_edges(s: pd.Series, edges: Optional[np.ndarray], descending: bool) -> pd.Series:
    """用给定分箱边界打分；边界不可用（数据无方差）时统一给 3 分。"""
    if edges is None or len(edges) < 2:
        return pd.Series([3] * len(s), index=s.index)
    cut = pd.cut(s, bins=edges, include_lowest=True, labels=False).fillna(0).astype(int)
    k = len(edges) - 1
    if descending:
        return (k - cut)  # 大值→低分
    return (cut + 1)


def _segment_of(r_hi: bool, f_hi: bool, m_hi: bool) -> str:
    """8 群体映射（M 决定高价值/普通，R/F 决定核心/潜力/沉睡/流失预警）。"""
    if m_hi:  # 高价值
        if r_hi and f_hi:
            return "高价值核心客户"
        if r_hi and not f_hi:
            return "潜力高价值客户"
        if not r_hi and f_hi:
            return "沉睡高价值客户"
        return "流失预警高价值客户"
    else:  # 普通
        if r_hi and f_hi:
            return "稳定普通客户"
        if r_hi and not f_hi:
            return "潜力普通客户"
        if not r_hi and f_hi:
            return "沉睡普通客户"
        return "流失预警普通客户"


def _empty_package(reason: str) -> AnalysisPackage:
    return AnalysisPackage(
        id="rfm_user_segmentation",
        analysis_type="rfm",
        business_question="RFM 用户分层分析",
        algorithm="rfm_v1",
        dimension="用户分层",
        metric="RFM",
        kpis=[], chart_data=[], tables=[],
        insights=[f"RFM 分析未生成结果：{reason}"],
        conclusions=[], recommendations=[],
        confidence=0.0, calculator_used="rfm_v1",
        template_used="rfm", can_run=False,
    )


# ==================== B 动态演化辅助 ====================
def _build_b(df: pd.DataFrame, months: List[Any], theta_r: int, theta_f: int, theta_m: int) \
        -> Tuple[List[Dict], List[Dict], float]:
    """按订单年月滑动窗口重算每用户每月分层，产出桑基迁移 + 占比折线数据。

    返回 (sankey_rows, line_rows, stable_total)。
    """
    work = df.copy()
    work["_uid"] = work["用户ID"].astype(str)
    work["_dt"] = pd.to_datetime(work["订单时间"], errors="coerce")
    work = work.dropna(subset=["_dt"])
    if work.empty:
        return [], [], 0.0
    work["_month"] = work["_dt"].dt.to_period("M")

    # F 计数：订单ID 去重（消费次数已归一成 订单ID，此处统一用 nunique）
    if "订单ID" in work.columns:
        fcount = work.groupby(["_uid", "_month"])["订单ID"].nunique().rename("cnt").reset_index()
    else:
        fcount = work.groupby(["_uid", "_month"]).size().rename("cnt").reset_index()
    msum = work.groupby(["_uid", "_month"])["订单实付金额"].sum().rename("msum").reset_index()
    maxdt = work.groupby(["_uid", "_month"])["_dt"].max().rename("maxdt").reset_index()
    um = fcount.merge(msum, on=["_uid", "_month"]).merge(maxdt, on=["_uid", "_month"])
    um = um.sort_values(["_uid", "_month"])
    um["cum_cnt"] = um.groupby("_uid")["cnt"].cumsum()
    um["cum_msum"] = um.groupby("_uid")["msum"].cumsum()
    um["cum_maxdt"] = um.groupby("_uid")["maxdt"].cummax()

    # B 自身分布算分箱边界（自洽）
    month_end = pd.to_datetime(um["_month"].astype(str) + "-01") + pd.offsets.MonthEnd(1)
    r_b = (month_end - um["cum_maxdt"]).dt.days.clip(lower=0)
    f_b = um["cum_cnt"]
    m_b = um["cum_msum"]
    r_edges = pd.qcut(r_b, 5, duplicates="drop", retbins=True)[1] if r_b.nunique() > 1 else None
    f_edges = pd.qcut(f_b, 5, duplicates="drop", retbins=True)[1] if f_b.nunique() > 1 else None
    m_edges = pd.qcut(m_b, 5, duplicates="drop", retbins=True)[1] if m_b.nunique() > 1 else None
    um["R_s"] = _score_edges(r_b, r_edges, descending=True)
    um["F_s"] = _score_edges(f_b, f_edges, descending=False)
    um["M_s"] = _score_edges(m_b, m_edges, descending=False)
    um["R_hi"] = um["R_s"] >= theta_r
    um["F_hi"] = um["F_s"] >= theta_f
    um["M_hi"] = um["M_s"] >= theta_m
    M_hi = um["M_hi"].astype(bool)
    R_hi = um["R_hi"].astype(bool)
    F_hi = um["F_hi"].astype(bool)
    um["seg"] = np.select(
        [M_hi & R_hi & F_hi, M_hi & R_hi & ~F_hi, M_hi & ~R_hi & F_hi, M_hi & ~R_hi & ~F_hi,
         ~M_hi & R_hi & F_hi, ~M_hi & R_hi & ~F_hi, ~M_hi & ~R_hi & F_hi, ~M_hi & ~R_hi & ~F_hi],
        ["高价值核心客户", "潜力高价值客户", "沉睡高价值客户", "流失预警高价值客户",
         "稳定普通客户", "潜力普通客户", "沉睡普通客户", "流失预警普通客户"],
        default="流失预警普通客户",
    )

    # 每月各 segment 人数
    month_seg_counts: Dict[Any, Dict[str, int]] = {}
    for (_u, _m), g in um.groupby(["_uid", "_month"]):
        seg = g["seg"].iloc[0]
        month_seg_counts.setdefault(_m, {})
        month_seg_counts[_m][seg] = month_seg_counts[_m].get(seg, 0) + 1

    # 相邻月迁移（按用户排序）
    sankey_rows: List[Dict] = []
    stable_total = 0.0
    for _u, g in um.sort_values(["_uid", "_month"]).groupby("_uid"):
        g = g.sort_values("_month")
        prev = None
        for _, row in g.iterrows():
            cur = row["seg"]
            if prev is not None:
                sankey_rows.append({"source": prev, "target": cur, "value": 1.0})
                if prev == cur:
                    stable_total += 1.0
            prev = cur

    # 折线：每月各 segment 占比
    line_rows: List[Dict] = []
    for _m, segcnt in month_seg_counts.items():
        mtotal = sum(segcnt.values())
        mlabel = str(_m)
        for s in SEGMENTS:
            line_rows.append({"x": mlabel, "y": _safe_div(segcnt.get(s, 0), mtotal), "series": s})

    return sankey_rows, line_rows, stable_total


# ==================== 模型主体 ====================
class RFMModel(AnalysisModel):
    name = "rfm_user_segmentation"
    display_name = "RFM 用户分层"
    description = "RFM 三维打分 → 8 用户分层 + 结构/动态/价值三维度分析"
    # 严格必需列（含订单ID）；缺失订单ID 时降级到 USER_SEG（K-means）
    required_columns = ["用户ID", "订单实付金额", "订单时间", "订单ID"]

    def can_run(self, df: pd.DataFrame) -> bool:
        if df is None or len(df.columns) == 0:
            return False
        norm = _normalize_columns(df)
        # RFM 严格（含订单ID）或 USER_SEG 降级列（无订单ID）满足其一即可
        if _RFM_STRICT.issubset(norm.columns):
            return True
        if _RFM_USERSEG.issubset(norm.columns):
            return True
        if _RFM_PREAGG.issubset(norm.columns):
            return True
        return False

    def compute(self, df: pd.DataFrame) -> AnalysisPackage:
        self._seg_table = None  # 防单例跨请求残留
        if df is None or len(df) == 0:
            return _empty_package("数据为空")
        norm = _normalize_columns(df)
        # 降级链路：RFM 严格列齐（含订单ID）→ 原 RFM 8 群；
        # 仅 USER_SEG 列齐（无订单ID）→ 延迟调 K-means run_user_seg 降级
        if _RFM_STRICT.issubset(norm.columns):
            return self._compute_rfm(norm)
        if _RFM_PREAGG.issubset(norm.columns):
            return self._compute_rfm(norm)
        from src.analysis_engine.models.kmeans import run_user_seg, user_seg_label_users
        self._seg_table = user_seg_label_users(norm)
        return run_user_seg(norm)

    def segmentation_table(self, df: pd.DataFrame = None) -> Optional[pd.DataFrame]:
        """每用户分群宽表（瞬态），供下游用户画像消费；未挂出时为 None。"""
        return getattr(self, "_seg_table", None)

    def _compute_rfm(self, df: pd.DataFrame) -> AnalysisPackage:
        users = df["用户ID"].astype(str)

        # ---- 输入形态判定：交易级（消费日期）/ 用户级预聚合（R天数） ----
        tx_mode = "订单时间" in df.columns
        preagg_mode = (not tx_mode) and ("距上次登录天数" in df.columns)
        if not (tx_mode or preagg_mode):
            return _empty_package("缺少 R 来源（订单时间 或 距上次登录天数/Recency）")

        if tx_mode:
            # F：订单ID 去重（消费次数/购买频率已归一成 订单ID）；RFM 严格路径订单ID 必存在
            f_series = df.groupby(users)["订单ID"].nunique()
            m_series = df.groupby(users)["订单实付金额"].sum()
            cost_cols = [c for c in ("商品成本", "退款金额", "运费") if c in df.columns]
            if cost_cols:
                tmp = df.assign(_u=users)
                cost = tmp.groupby("_u")[cost_cols].sum().sum(axis=1)
                profit = m_series.reindex(cost.index) - cost
            else:
                profit = m_series
            # R：距今天（快照日）
            t_ref = pd.Timestamp.now().normalize()
            last_dt = pd.to_datetime(df["订单时间"], errors="coerce").groupby(users).max()
            r_raw = (t_ref - last_dt).dt.days.clip(lower=0)
            user_df = pd.DataFrame({
                "用户ID": f_series.index,
                "R_raw": r_raw.reindex(f_series.index).values,
                "F_raw": f_series.values,
                "M_raw": m_series.reindex(f_series.index).values,
                "profit": profit.reindex(f_series.index).values,
            })
        else:
            # 预聚合用户级：R/F/M 已逐列给出（如 测试1）；订单ID 必存在
            r_raw = pd.to_numeric(df["距上次登录天数"], errors="coerce")
            f_raw = pd.to_numeric(df["订单ID"], errors="coerce")
            m_raw = pd.to_numeric(df["订单实付金额"], errors="coerce")
            cost_cols = [c for c in ("商品成本", "退款金额", "运费") if c in df.columns]
            if cost_cols:
                profit = m_raw - df[cost_cols].sum(axis=1)
            else:
                profit = m_raw
            user_df = pd.DataFrame({
                "用户ID": users.values,
                "R_raw": r_raw.values,
                "F_raw": f_raw.values,
                "M_raw": m_raw.values,
                "profit": profit.values,
            })

        user_df = user_df.dropna(subset=["R_raw", "F_raw", "M_raw"]).copy()
        for c in ("R_raw", "F_raw", "M_raw", "profit"):
            user_df[c] = pd.to_numeric(user_df[c], errors="coerce").fillna(0.0)

        # 分箱打分
        user_df["R_score"] = _bin_score(user_df["R_raw"], ascending=False)
        user_df["F_score"] = _bin_score(user_df["F_raw"], ascending=True)
        user_df["M_score"] = _bin_score(user_df["M_raw"], ascending=True)
        theta_r = int(np.median(user_df["R_score"]))
        theta_f = int(np.median(user_df["F_score"]))
        theta_m = int(np.median(user_df["M_score"]))
        user_df["R_hi"] = user_df["R_score"] >= theta_r
        user_df["F_hi"] = user_df["F_score"] >= theta_f
        user_df["M_hi"] = user_df["M_score"] >= theta_m
        M_hi = user_df["M_hi"].astype(bool)
        R_hi = user_df["R_hi"].astype(bool)
        F_hi = user_df["F_hi"].astype(bool)
        user_df["Segment"] = np.select(
            [M_hi & R_hi & F_hi, M_hi & R_hi & ~F_hi, M_hi & ~R_hi & F_hi, M_hi & ~R_hi & ~F_hi,
             ~M_hi & R_hi & F_hi, ~M_hi & R_hi & ~F_hi, ~M_hi & ~R_hi & F_hi, ~M_hi & ~R_hi & ~F_hi],
            ["高价值核心客户", "潜力高价值客户", "沉睡高价值客户", "流失预警高价值客户",
             "稳定普通客户", "潜力普通客户", "沉睡普通客户", "流失预警普通客户"],
            default="流失预警普通客户",
        )

        total = len(user_df)
        if total == 0:
            return _empty_package("未解析出有效用户")
        counts = user_df["Segment"].value_counts().to_dict()
        seg_counts = {s: int(counts.get(s, 0)) for s in SEGMENTS}

        # KPI
        m_high = sum(v for s, v in seg_counts.items() if s.startswith("高价值"))
        important_value = seg_counts["高价值核心客户"]
        repurchase = int((user_df["F_raw"] >= 2).sum())
        avg_profit = _safe_div(user_df["profit"].sum(), total)
        max_seg = max(seg_counts, key=seg_counts.get)

        kpis = [
            KPIItem(label="总用户数", value=f"{total:,}", kpi_type="metric"),
            KPIItem(label="高价值人群占比(M高)", value=f"{_safe_div(m_high, total) * 100:.1f}%", kpi_type="metric"),
            KPIItem(label="高价值核心客户用户数", value=f"{important_value:,}", kpi_type="metric"),
            KPIItem(label="人均净毛利", value=f"{avg_profit:,.2f}", kpi_type="metric"),
            KPIItem(label="复购率(F≥2)", value=f"{_safe_div(repurchase, total) * 100:.1f}%", kpi_type="metric"),
            KPIItem(label="最大分层", value=f"{max_seg}（{seg_counts[max_seg]:,}人）", kpi_type="metric"),
        ]

        # A 结构
        bar_rows = [{"分层": s, "人数": seg_counts[s]} for s in SEGMENTS]
        charts: List[ChartData] = [
            ChartData(slot="rfm_pie", chart_type="pie", title="RFM 8 大群体占比",
                      x="分层", y="人数", data=bar_rows),
        ]

        insights: List[str] = [
            f"共 {total:,} 名用户，按 RFM 三维打分归入 8 大标准群体（快照日 = 今天）。",
            f"高价值人群（M 高：高价值核心/沉睡/潜力/流失预警 四群）合计 {m_high:,} 人，"
            f"占比 {_safe_div(m_high, total) * 100:.1f}%。",
            f"最大群体为「{max_seg}」（{seg_counts[max_seg]:,} 人，"
            f"{_safe_div(seg_counts[max_seg], total) * 100:.1f}%）；"
            f"流失风险群体「流失预警高价值客户+流失预警普通客户」合计 {seg_counts['流失预警高价值客户'] + seg_counts['流失预警普通客户']:,} 人。",
        ]

        # B 动态演化：仅「交易级（有订单时间）」且至少 1 名用户在 ≥2 个不同月份有消费。
        # 预聚合用户级（无订单时间）无逐月历史，直接跳过，不进入 B。
        has_dyn = False
        if "订单时间" in df.columns:
            try:
                _u_series = df["用户ID"].astype(str)
                _m_series = pd.to_datetime(df["订单时间"], errors="coerce").dt.to_period("M")
                dyn = df.assign(_u=_u_series, _m=_m_series).dropna(subset=["_m"]) \
                         .groupby("_u")["_m"].nunique()
                has_dyn = bool(dyn.gt(1).any())
            except Exception:
                has_dyn = False

        if has_dyn:
            months = sorted(pd.to_datetime(df["订单时间"], errors="coerce").dt.to_period("M").dropna().unique().tolist())
            sankey_rows, line_rows, stable_total = _build_b(df, months, theta_r, theta_f, theta_m)
            total_trans = len(sankey_rows)
            stable_ratio = _safe_div(stable_total, total_trans)
            # 仅保留真实迁移（相邻月换层），自环（停留原层）不计入：
            # 若全员停留则无有效迁移，静默跳过桑基图/KPI/洞察（不弹提示）。
            migration_rows = [r for r in sankey_rows if r["source"] != r["target"]]
            if migration_rows:
                charts.append(ChartData(slot="rfm_sankey", chart_type="sankey",
                                        title="群体流转桑基图（相邻月迁移）", x="", y="", data=migration_rows))
                kpis.append(KPIItem(label="稳定用户占比(相邻月维持原层)",
                                    value=f"{stable_ratio * 100:.1f}%", kpi_type="metric"))
                insights.append(
                    f"动态演化：相邻月流转中约 {stable_ratio * 100:.1f}% 维持原层（稳定用户），"
                    f"约 {(1 - stable_ratio) * 100:.1f}% 发生群体迁移；桑基图展示各群体间的流转方向与人数。")
            if line_rows:
                charts.append(ChartData(slot="rfm_line", chart_type="rfm_line",
                                        title="各群体占比随月份变化趋势", x="", y="", data=line_rows))
        else:
            insights.append("数据为单月快照或用户级聚合表（无逐月明细），无法计算动态演化（B：群体流转/占比趋势）。")

        # C 价值深挖：分层 × 住址 人均净毛利矩阵表
        # 用表格替代热力图：决策者可横向对比「同种用户在各地区的人均净毛利」，
        # 后端对每类用户找出人均净毛利最高的地区并高亮标记（小样本护栏防偶然值误导）。
        region_best_table: Optional[TableData] = None
        if "住址" in df.columns:
            region_map = df.assign(_u=df["用户ID"].astype(str)).groupby("_u")["住址"] \
                .agg(lambda xs: xs.dropna().iloc[0] if xs.dropna().size else None)
            u2 = user_df.copy()
            u2["住址"] = u2["用户ID"].map(region_map)
            u2 = u2.dropna(subset=["住址"])
            if len(u2) > 0:
                MIN_COUNT = 5  # 小样本护栏：不足 5 人不参与"最赚钱地区"评选，防 2 人偶然值被误标最佳
                agg = u2.groupby(["Segment", "住址"]).agg(
                    人均净利=("profit", "mean"), 客户数=("profit", "size")).reset_index()
                # 地区按总客户数降序，最值得关注的区域排最前
                region_order = (
                    agg.groupby("住址")["客户数"].sum()
                    .sort_values(ascending=False).index.tolist())
                # 每类用户：在 客户数>=MIN_COUNT 的地区里找 人均净毛利 最高者
                best_region: Dict[str, str] = {}
                for seg in SEGMENTS:
                    sub = agg[(agg["Segment"] == seg) & (agg["客户数"] >= MIN_COUNT)]
                    if len(sub) > 0:
                        best_region[seg] = str(sub.loc[sub["人均净利"].idxmax(), "住址"])
                # 构建矩阵表：每行=1 类用户，列=各地区；缺失组合留空（前端显示 —）
                rows = []
                for seg in SEGMENTS:
                    row: Dict[str, Any] = {"分层": seg}
                    for region in region_order:
                        g = agg[(agg["Segment"] == seg) & (agg["住址"] == region)]
                        if len(g) == 0:
                            row[region] = None
                        else:
                            r = g.iloc[0]
                            row[region] = {
                                "value": round(float(r["人均净利"]), 2),
                                "count": int(r["客户数"]),
                                "highlight": best_region.get(seg) == str(region),
                                "cell_type": "number",
                            }
                    rows.append(row)
                region_best_table = TableData(
                    slot="rfm_region_best",
                    title="各分层在各地区的净毛利均值（高亮=该类用户净毛利最高的地区）",
                    table_type="region_best",
                    columns=["分层"] + region_order,
                    rows=rows,
                )
            else:
                insights.append("数据未含有效住址映射，未生成分层×地区净毛利矩阵表。")
        else:
            insights.append("数据未含住址列，未生成分层×地区净毛利矩阵表（建议补充住址维度深挖区域价值结构）。")

        # 双轴：分层 vs 人数 vs 人均净毛利
        # 字段口径（A2 修复）：
        #   人数  = 该分层用户数（左轴）
        #   净GMV = 该分层 Σ订单实付金额（M_raw 之和，真实总消费）
        #   净毛利 = 该分层 Σ净毛利（profit 之和，已扣成本/退款）
        # 注：原实现把「净GMV」错填成人数、「净毛利」错填成人均值，前端再按 金额÷金额
        #     算 Avg.Profit Margin 导致万倍率。这里改为真实金额，前端公式无需变动。
        seg_agg = user_df.groupby("Segment")[["M_raw", "profit"]].sum()
        dual_rows: List[Dict] = []
        for s in SEGMENTS:
            sub = user_df[user_df["Segment"] == s]
            cnt = int(len(sub))
            gmv = float(seg_agg["M_raw"].get(s, 0.0))
            margin = float(seg_agg["profit"].get(s, 0.0))
            dual_rows.append({
                "分层": s,
                "人数": cnt,
                "净GMV": round(gmv, 4),
                "净毛利": round(margin, 4),
            })
        charts.append(ChartData(slot="rfm_dual", chart_type="dual_axis",
                                title="分层 vs 人数 vs 人均净毛利", x="分层", y="净GMV", right_col="净毛利", data=dual_rows))

        # 明细表
        table_rows: List[Dict] = []

        # 消费力(M)：复用基层 _compute_rfm 算出的 M_raw（群内用户均值），
        # 表达方式与用户画像模型完全一致（结构化 cell：value/direction/rank）
        def _cell_num_m(val: float, series: List[float], higher: bool = True) -> dict:
            vals = [v for v in series if v is not None and pd.notna(v)]
            if not vals:
                return {"value": val, "type": "number", "direction": "equal", "rank": 0.0}
            asc = sorted(vals)
            cnt = len(asc)
            pos = bisect.bisect_right(asc, val)
            rank = pos / cnt if higher else (cnt - pos) / cnt
            mean = sum(vals) / cnt
            if mean == 0:
                direction = "equal"
            else:
                d = (val - mean) / abs(mean)
                if d > 0.05:
                    direction = "good" if higher else "bad"
                elif d < -0.05:
                    direction = "bad" if higher else "good"
                else:
                    direction = "equal"
            return {"value": val, "type": "number", "direction": direction, "rank": round(rank, 3)}

        m_raw_by_seg: Dict[str, float] = {}
        for s in SEGMENTS:
            d = user_df[user_df["Segment"] == s]
            m_raw_by_seg[s] = float(d["M_raw"].mean()) if len(d) else 0.0
        m_raw_series = [m_raw_by_seg[s] for s in SEGMENTS]

        for s in SEGMENTS:
            sub = user_df[user_df["Segment"] == s]
            cnt = len(sub)
            rep_rate = _safe_div(int((sub["F_raw"] >= 2).sum()), cnt) if cnt else 0.0
            m_val = m_raw_by_seg[s]
            table_rows.append({
                "分层": s,
                "人数": cnt,
                "占比": f"{_safe_div(cnt, total) * 100:.1f}%",
                "消费力(M)": _cell_num_m(m_val, m_raw_series, higher=True),
                "人均净毛利": f"{_safe_div(sub['profit'].sum(), cnt):,.2f}" if cnt else "0.00",
                "复购率": f"{rep_rate * 100:.1f}%",
            })
        tables: List[TableData] = []
        if region_best_table is not None:
            tables.append(region_best_table)
        tables.append(TableData(title="RFM 8 群体汇总", table_type="summary",
                                columns=["分层", "人数", "占比", "消费力(M)", "人均净毛利", "复购率"],
                                rows=table_rows, slot="rfm_segment_summary_table"))

        # 结论 / 建议
        conclusions: List[str] = []
        recommendations: List[str] = []
        for s in SEGMENTS:
            info = SEGMENT_INFO[s]
            conclusions.append(f"【{s}】{info['定义']} {info['含义']}")
            recommendations.append(f"【{s}】运营策略：{info['策略']}（转化路径：{info['转化路径']}）")

        # 纯加法：把每用户分群宽表挂出供下游用户画像消费（RFM 自身逻辑零改动）
        self._seg_table = user_df[["用户ID", "R_raw", "F_raw", "M_raw", "profit", "Segment"]].copy()

        return AnalysisPackage(
            id="rfm_user_segmentation",
            analysis_type="rfm",
            business_question="RFM 用户分层分析",
            algorithm="rfm_v1",
            dimension="用户分层",
            metric="RFM",
            kpis=kpis,
            chart_data=charts,
            tables=tables,
            insights=insights,
            conclusions=conclusions,
            recommendations=recommendations,
            confidence=1.0,
            calculator_used="rfm_v1",
            template_used="rfm",
            can_run=True,
        )


# 注册到分析引擎
register_model(RFMModel())
