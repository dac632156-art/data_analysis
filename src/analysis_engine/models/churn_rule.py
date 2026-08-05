"""规则型用户流失预警模型（churn_rule）。

三段式算法规格（依据《规则型用户流失预警模型拆解.md》）：
  HardBlock（硬校验，非报错）→ Base（三档标签）→ Advanced E/F（探测列独立触发、平级并存）

用户铁律（已确认，严禁违反）：
  - 核心列(用户ID + 订单时间 + 至少一个互动信号)不齐 → skipped，绝不做兜底派生。
  - 进阶 E/F 所需探测列不存在 → 不触发、不派生、不猜测。
  - 时间列只做 pd.to_datetime(errors='coerce') 一次性解析，不做多格式猜测；
    coerce 后整列全 NaT 即视为该列不可用（互动信号全不可用 → skipped）。
  - 列名直接认映射词典标准化后的标准中文名，模型内部不再做别名归一化、不派生缺失列。

Advanced 层契约（文档第三段，严格平级、绝不回改主标签）：
  - E（价值分层）：探测列两级触发——CLV/总消费金额 直接消费；否则订单金额列
    （订单实付金额/订单总额/购买金额）按用户 SUM 现场计算累计消费额。
    分位基准 = 全体用户（含正常）价值分布的 Q0.7/Q0.3，绝不在流失+预警子集内重算分位；
    V≥Q0.7 高价值 / V≤Q0.3 低价值 / 其间中价值；价值 NaN 用户不分档（没数据≠没价值）。
    挽回优先级六分支（价值层 × 流失状态全展开）：高价值·已流失→紧急挽回、高价值·预警→重点防护、
    中价值·已流失→标准召回、中价值·预警→常规跟进、低价值·已流失→停止触达、低价值·预警→常规维持；
    正常用户不标记。
  - F（流失归因）：白名单维度列（文档 116-121 行清单）至少一个存在才触发；
    连续数值维度（年龄/收入/客户年限/订单送达率/客诉次数/折扣比例）先四分位分箱再对比；
    每维度独立算 流失群占比 − 正常群占比 偏移(pp)、独立排名，无显著性过滤；
    流失群或正常群任一为空 → 整段不触发（分母为空的偏移是假象）；
    产出单一图族 ChartData（slot=hbar__attr_dim_offset, chart_type=hbar_family，
    option={维度名: 子图option}），并为已流失用户贴[流失集中维度TOP]附加列。
  - E、F 各自独立判断、多支可并存，谁也不覆盖谁的标记、也不动 Base 的[流失状态]主标签。
"""

import pandas as pd

from src.analysis_templates.base import (
    AnalysisPackage,
    ChartData,
    KPIItem,
    TableData,
)
from src.analysis_engine.base import AnalysisModel
from src.analysis_engine.registry import register_model
from src.domain.finding_factory import FindingFactory
from src.domain.business_finding import Severity, FindingCategory


# ===== 标准列名（映射词典已标准化，模型直接认，不做别名转换） =====
USER_ID = "用户ID"
ORDER_TIME = "订单时间"
EVENT_TIME = "事件时间"
SESSION_START = "会话开始时间"
ACTIVITY_SIGNALS = [EVENT_TIME, SESSION_START]   # 互动信号：至少一个可用

CANCEL_TIME = "注销时间"
BAN_STATUS = "账号封禁状态"
RECENT_PURCHASE_GAP = "最近购买间隔天数"
ONLINE_DURATION = "在站时长"
REG_DATE = "注册日期"

# E 价值分层探测列（文档 105-106 行，两级触发）：
#   一级：用户级价值列，直接消费（逐用户 MAX 去重，不重算）
E_DIRECT_VALUE_COLS = ["CLV", "总消费金额"]
#   二级：订单级金额列，按用户 SUM 现场算累计消费额（优先级同序）
E_ORDER_AMOUNT_COLS = ["订单实付金额", "订单总额", "购买金额"]

# F 流失归因探测列白名单（逐字取自文档 116-121 行，按域分组；本模块不重算，只消费）
F_DIM_WHITELIST = [
    # 用户属性域
    "性别", "年龄", "教育水平", "收入", "婚姻情况", "城市", "省份", "国家",
    "会员等级", "用户状态", "客户年限", "忠诚度计划", "订阅状态",
    "设备类型", "平台", "流量来源", "广告来源", "营销计划",
    # 商品域
    "商品类目", "类目ID", "品牌", "商品规格",
    # 订单/交易域
    "订单状态", "支付方式", "优惠券", "退款状态", "承运商",
    "订单送达率", "客诉次数", "折扣比例",
    # 评价域
    "评分星级", "客户满意度",
    # 模型标签域（上游衍生，可直接当维度）
    "用户分层", "价值等级", "流失风险等级", "客户细分", "聚类标签",
    "新客标记", "复购标记", "购买状态",
    # 实验域
    "AB分组",
]
# 连续数值维度：F 跑时先按四分位分箱成离散区间再对比偏移（文档 122 行）
F_BINNED_DIMS = {"年龄", "收入", "客户年限", "订单送达率", "客诉次数", "折扣比例"}

# 气泡矩阵人数列名契约：chart_renderer 不透传 size_col，
# 必须与 echart_generator.create_bubble_matrix(size_col 默认="人数") 严格一致
BUBBLE_SIZE_COL = "人数"

# 用户级明细导出行数上限（防大文件 payload 爆炸；完整宽表由 segmentation_table 提供）
TABLE_CAP = 1000


# --------------------------------------------------------------------------
# 工具
# --------------------------------------------------------------------------
def _to_dt(series: pd.Series) -> pd.Series:
    """只做一次 coerce（用户明确上游已预处理好类型，模型不做多格式猜测兜底）。"""
    return pd.to_datetime(series, errors="coerce")


def _hard_block(df: pd.DataFrame):
    """HardBlock 硬校验：返回 (reason, suggestion) 或 (None, None)。"""
    cols = set(df.columns)
    if USER_ID not in cols:
        return (
            "缺少核心列[用户ID]（分组主键，用于产出一用户一行的流失标签）",
            "请补充[用户ID]主键列后再分析。",
        )
    if ORDER_TIME not in cols:
        return (
            "缺少核心列[订单时间]（流失阈值 R_churn = 群体平均购买间隔 × 2 的必选输入）",
            "请补充[订单时间]列后再分析。",
        )
    # 互动信号：至少一个存在且能解析出有效时间
    usable = [
        c for c in ACTIVITY_SIGNALS
        if c in cols and _to_dt(df[c]).notna().any()
    ]
    if not usable:
        return (
            "缺少可用的互动信号列（事件时间 / 会话开始时间 至少有一个且能解析为有效时间）",
            "请补充互动信号列：事件时间 / 会话开始时间（至少一个），用于计算用户最后活跃时间。",
        )
    return (None, None)


def _empty_package(reason: str, suggestion: str) -> AnalysisPackage:
    return AnalysisPackage(
        id="churn_rule",
        analysis_type="churn_rule",
        business_question="哪些用户已流失 / 处于流失预警 / 仍正常？",
        algorithm="churn_rule_v1",
        dimension="用户",
        metric="流失状态",
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
# 主算：HardBlock → Base → Advanced E（F 不改主标签、不落用户级列，放在 compute 跑）
# --------------------------------------------------------------------------
def _analyze(df: pd.DataFrame) -> dict:
    """返回 skipped 包信息 或 完整结果 dict（含 user_level / 阈值 / E 触发标记）。"""
    reason, suggestion = _hard_block(df)
    if reason:
        return {"skipped": True, "reason": reason, "suggestion": suggestion}

    cols = set(df.columns)

    # 订单时间：一次性 coerce
    order_time = _to_dt(df[ORDER_TIME])
    if order_time.notna().sum() == 0:
        return {
            "skipped": True,
            "reason": "订单时间列无法解析为有效时间（全为空/脏值），无法计算流失阈值 R_churn",
            "suggestion": "请确认[订单时间]列已被上游映射为日期时间类型且含有效时间。",
        }

    # 2.0 最后活跃时间：逐互动信号按用户取 MAX，再跨信号取最大
    last_per_user = None
    for c in ACTIVITY_SIGNALS:
        if c not in cols:
            continue
        s = _to_dt(df[c])
        if s.notna().sum() == 0:
            continue
        sig_max = df.assign(_t=s).groupby(USER_ID)["_t"].max()
        last_per_user = sig_max if last_per_user is None else \
            pd.concat([last_per_user, sig_max], axis=1).max(axis=1)

    if last_per_user is None or last_per_user.dropna().empty:
        return {
            "skipped": True,
            "reason": "互动信号列（事件时间/会话开始时间）解析后无有效时间，无法计算最后活跃时间",
            "suggestion": "请确认互动信号列已被上游映射为日期时间类型且含有效时间。",
        }

    T_ref = order_time.max()                      # 文档默认：参考时刻 = 最大订单时间
    user_active = last_per_user.dropna()          # Series: 用户ID -> 最后活跃时间
    # 距上次活跃天数；T_ref=最大订单时间，用户下单后又有互动活跃时会出现负值，
    # 语义上"参考时刻仍活跃"→ 截断为 0（避免直方图递减分箱崩溃 / 负值被 pd.cut 静默丢弃）
    r_login = (T_ref - user_active).dt.days.clip(lower=0)

    # 2.1.5 群体平均购买间隔（仅 n_u>=2 的多单用户计入）
    ot_by_user = order_time.groupby(df[USER_ID]).apply(
        lambda s: [t for t in s.dropna() if not pd.isna(t)]
    )
    gaps = []
    for times in ot_by_user:
        times = sorted(times)   # 必须按时间升序，否则跨行顺序会得到负间隔
        n = len(times)
        if n >= 2:
            diffs = [
                (times[i + 1] - times[i]).total_seconds() / 86400.0
                for i in range(n - 1)
            ]
            gaps.append(sum(diffs) / len(diffs))
    if not gaps:
        # 决策：所有用户都只下过 1 单 → 算不出阈值 → 整体跳过，绝不拍脑门给默认阈值
        return {
            "skipped": True,
            "reason": "所有用户均只下过 1 单，算不出群体平均购买间隔，无法构建流失阈值 R_churn",
            "suggestion": "当前数据下不存在可预警的流失（每人至多一单），流失模型整体跳过。",
        }

    G_bar = sum(gaps) / len(gaps)      # 群体平均购买间隔（天）
    R_churn = 2.0 * G_bar              # 流失阈值

    # 2.2 三档标签（base）—— 唯一决定[流失状态]主标签的地方
    def _base_label(r: float) -> str:
        if r > R_churn:
            return "已流失"
        if r > G_bar:
            return "流失预警"
        return "正常"

    status = r_login.apply(_base_label)
    user_level = pd.DataFrame(
        {"R_login": r_login, "流失状态": status},
        index=r_login.index,
    )
    user_level.index.name = USER_ID

    ctx = {"G_bar": G_bar, "R_churn": R_churn, "T_ref": T_ref}

    # 第三段 Advanced E（作用域=已流失+预警人群，仅贴附加列；F 在 compute 内跑）
    e = _advanced_e(df, user_level, ctx)

    return {
        "skipped": False,
        "user_level": user_level,
        "R_churn": R_churn,
        "G_bar": G_bar,
        "T_ref": T_ref,
        "e": e,
    }


# --------------------------------------------------------------------------
# Advanced E：价值分层（文档 97-111 行）
#   价值来源三选一（CLV > 总消费金额 > 订单金额列按用户 SUM 现场计算）；
#   分位基准 = 全体用户价值分布 Q0.7/Q0.3（用户拍板：绝不在流失+预警子集内重算）；
#   作用域=Base 已判「已流失 / 流失预警」人群贴标签；价值 NaN 用户不分档；
#   仅贴 [价值层] + [挽回优先级] 附加列，绝不回改主标签。
# --------------------------------------------------------------------------
def _advanced_e(df: pd.DataFrame, user_level: pd.DataFrame, ctx: dict):
    cols = set(df.columns)

    # 两级触发（文档 106 行）：先认用户级价值列，再认订单金额列现场 SUM
    direct_col = next((c for c in E_DIRECT_VALUE_COLS if c in cols), None)
    amount_col = None
    if direct_col is None:
        amount_col = next((c for c in E_ORDER_AMOUNT_COLS if c in cols), None)
        if amount_col is None:
            return None  # 两级探测列均不存在 → E skipped，不触发、不派生

    if direct_col is not None:
        # 用户级价值列：逐用户 MAX 去重（同一用户各行值应一致，MAX 仅作去重聚合）
        val = pd.to_numeric(df[direct_col], errors="coerce")
        v_by_user = df.assign(_v=val).groupby(USER_ID)["_v"].max()
    else:
        # 现场计算（文档 103 行）：累计消费额(u) = Σ 订单金额(o)，按用户 SUM
        val = pd.to_numeric(df[amount_col], errors="coerce")
        v_by_user = df.assign(_v=val).groupby(USER_ID)["_v"].sum(min_count=1)

    v_by_user = v_by_user.reindex(user_level.index)

    # 分位阈值在【全体用户】的有效价值上算（决策1）；NaN 不参与分位也不参与分档
    v_valid = v_by_user.dropna()
    if v_valid.empty:
        return None  # 价值列存在但全为脏值 → 无法分层，E 不触发
    q_hi = float(v_valid.quantile(0.7))
    q_lo = float(v_valid.quantile(0.3))

    def _tier(v) -> str:
        if pd.isna(v):
            return "—"          # 没数据 ≠ 没价值：不分档
        if v >= q_hi:
            return "高价值"
        if v <= q_lo:
            return "低价值"
        return "中价值"

    # 挽回优先级六分支（文档 109 行）：价值层 × 流失状态 全展开，每格动作互斥清晰
    _PRIORITY_MAP = {
        ("已流失", "高价值"): "紧急挽回",
        ("流失预警", "高价值"): "重点防护",
        ("已流失", "中价值"): "标准召回",
        ("流失预警", "中价值"): "常规跟进",
        ("已流失", "低价值"): "停止触达",
        ("流失预警", "低价值"): "常规维持",
    }

    def _priority(status: str, tier: str) -> str:
        if status not in ("已流失", "流失预警") or tier == "—":
            return "—"
        return _PRIORITY_MAP.get((status, tier), "—")

    scope_mask = user_level["流失状态"].isin(["已流失", "流失预警"])
    tier_scope = v_by_user[scope_mask].map(_tier)
    user_level["价值层"] = tier_scope.reindex(user_level.index).fillna("—")
    user_level["挽回优先级"] = [
        _priority(s, t)
        for s, t in zip(user_level["流失状态"], user_level["价值层"])
    ]
    return True


# --------------------------------------------------------------------------
# Advanced F：流失归因（文档 113-128 行）
#   探测列 = F_DIM_WHITELIST 白名单，至少一个存在才触发（排除法已废弃）；
#   连续数值维度（F_BINNED_DIMS）先四分位分箱成离散区间再对比；
#   每维度独立算 偏移 = P(取值|已流失) − P(取值|正常)，独立排名，无显著性过滤；
#   流失群或正常群任一为空 → 整段不触发（单侧分母为空的偏移是假结论）；
#   产出：单一图族 ChartData（hbar_family，option 由 echart_generator 按维度分组生成）
#        + 已流失用户的 [流失集中维度TOP] 附加列（Series，正常/预警用户为 "—"）。
# --------------------------------------------------------------------------
def _advanced_f(df: pd.DataFrame, user_level: pd.DataFrame) -> dict:
    dim_cols = [c for c in F_DIM_WHITELIST if c in df.columns]
    if not dim_cols:
        return {"triggered": False, "chart": None, "dim_count": 0, "top_flag": None,
                "note": "进阶 F 未触发：白名单维度列均不存在，无法做流失归因。"}

    churn_idx = user_level.index[user_level["流失状态"] == "已流失"]
    normal_idx = user_level.index[user_level["流失状态"] == "正常"]
    # bug3 修复：任一对比群为空 → 偏移无意义（0−p 或 p−0 是分母为空造出的幻觉）
    if len(churn_idx) == 0 or len(normal_idx) == 0:
        empty_side = "已流失" if len(churn_idx) == 0 else "正常"
        return {"triggered": False, "chart": None, "dim_count": 0, "top_flag": None,
                "note": f"进阶 F 未触发：[{empty_side}]群为空，流失群 vs 正常群的占比偏移无意义。"}

    # 每用户取维度列主要取值（mode），对齐 user_level 索引；
    # 连续数值维度先在全体用户上四分位分箱（qcut, duplicates='drop'）再对比
    def _user_dim(dim_col: str) -> pd.Series:
        if dim_col in F_BINNED_DIMS:
            num = pd.to_numeric(df[dim_col], errors="coerce")
            per_user = num.groupby(df[USER_ID]).mean()
            valid = per_user.dropna()
            if valid.nunique() < 2:
                return pd.Series(index=user_level.index, dtype=object)
            try:
                binned = pd.qcut(per_user, q=4, duplicates="drop")
                # qcut 的 duplicates="drop" 会在数据集中时把分位边界塌缩成 1 个 bin，
                # 此时 churn vs normal 占比必相等、偏移恒为 0，图不可见。
                # 与上方 nunique<2 守卫互补：那个守的是原始均值，这个守的是分箱结果。
                if binned.dropna().nunique() < 2:
                    return pd.Series(index=user_level.index, dtype=object)
            except ValueError:
                return pd.Series(index=user_level.index, dtype=object)
            return binned.astype(str).where(per_user.notna()).reindex(user_level.index)

        def _mode(s: pd.Series):
            s = s.dropna()
            return s.value_counts().index[0] if len(s) else None
        return df.groupby(USER_ID)[dim_col].apply(_mode).reindex(user_level.index)

    all_rows = []                 # 打平的图族数据行：[维度, 维度取值, 偏移值]
    offset_lookup = {}            # {(维度, 取值): 偏移值}，供 TOP 列查询
    user_dim_values = {}          # {维度: 用户级取值 Series}
    dim_count = 0
    for dim in dim_cols:
        dim_user = _user_dim(dim)
        churn_dim = dim_user.loc[churn_idx].dropna()
        normal_dim = dim_user.loc[normal_idx].dropna()
        values = set(churn_dim.unique()) | set(normal_dim.unique())
        if not values:
            continue
        p_churn = churn_dim.value_counts(normalize=True)
        p_norm = normal_dim.value_counts(normalize=True)
        rows = []
        for v in values:
            p_c = round(float(p_churn.get(v, 0.0)) * 100, 1)
            p_n = round(float(p_norm.get(v, 0.0)) * 100, 1)
            offset = round(p_c - p_n, 1)
            rows.append({"维度": dim, "维度取值": str(v),
                          "流失占比": p_c, "正常占比": p_n, "偏移值": offset})
            offset_lookup[(dim, str(v))] = offset
        rows.sort(key=lambda r: r["偏移值"], reverse=True)   # 每维度独立降序排名
        # 截断：正(易流失)top3 + 负(稳定)top3，每维度最多6条
        pos_top = [r for r in rows if r["偏移值"] > 0][:3]
        neg_top = [r for r in rows if r["偏移值"] < 0][:3]
        zero_rows = [r for r in rows if r["偏移值"] == 0]  # 持平的保留（通常很少）
        all_rows.extend(pos_top + neg_top + zero_rows)
        user_dim_values[dim] = dim_user
        dim_count += 1



    if dim_count == 0:
        return {"triggered": False, "charts": [], "dim_count": 0, "top_flag": None,
                "note": "进阶 F 未触发：白名单维度列存在但均无有效取值。"}

    # [流失集中维度TOP]（文档 128 行）：每个已流失用户，标注其各维度取值中偏移最大的
    # "维度=取值"；正常/预警用户不标记（F 只归因流失群）
    def _top_flag_for(uid) -> str:
        best_key, best_off = None, None
        for dim, series in user_dim_values.items():
            v = series.get(uid)
            if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
                continue
            off = offset_lookup.get((dim, str(v)))
            if off is None:
                continue
            if best_off is None or off > best_off:
                best_key, best_off = f"{dim}={v}", off
        return best_key if best_key is not None else "—"

    top_flag = pd.Series("—", index=user_level.index, dtype=object)
    for uid in churn_idx:
        top_flag.loc[uid] = _top_flag_for(uid)

    # 维度偏移图：每个维度一张独立 hbar 图（chart_type="hbar"，前端走标准水平条形图渲染）
    # 仅选取总偏移绝对值最大的前 3 个维度出图；每维度内部全量不截断
    dim_abs = {}
    for r in all_rows:
        dim_abs[r["维度"]] = dim_abs.get(r["维度"], 0.0) + abs(r["偏移值"])
    top3_dims = sorted(dim_abs, key=dim_abs.get, reverse=True)[:3]
    charts = []
    for dim in top3_dims:
        dim_data = [r for r in all_rows if r["维度"] == dim]
        # 每维度内部按偏移值降序排列，便于阅读
        dim_data.sort(key=lambda r: r["偏移值"], reverse=True)
        charts.append(ChartData(
            slot="hbar__attr_dim_offset", chart_type="hbar",
            title=f"流失归因 · {dim}：维度偏移（pp）",
            x="维度取值", y="偏移值", color="维度", data=dim_data,
        ))
    return {"triggered": True, "charts": charts, "dim_count": dim_count,
            "top_flag": top_flag, "note": ""}


# --------------------------------------------------------------------------
# 模型
# --------------------------------------------------------------------------
class ChurnRuleModel(AnalysisModel):
    name = "churn_rule"
    display_name = "规则型用户流失预警"
    description = "基于最后活跃时间(R_login)、群体平均购买间隔与价值分层/流失归因，判定用户已流失/流失预警/正常"
    required_columns = [USER_ID, ORDER_TIME]   # 硬门槛；互动信号「至少一个」由 can_run 额外校验
    optional_columns = [
        EVENT_TIME, SESSION_START,
        *E_DIRECT_VALUE_COLS, *E_ORDER_AMOUNT_COLS,
        *F_DIM_WHITELIST,
    ]
    upstream_keys = []   # 生产者，不消费上游

    def can_run(self, df: pd.DataFrame) -> bool:
        # 基类门槛：required_columns 必须全在
        if df is None or len(df.columns) == 0:
            return False
        cols = set(df.columns)
        if not all(req in cols for req in self.required_columns):
            return False
        # 额外门槛：互动信号至少一个存在（coerce 可用性由 compute 内 HardBlock 再校验）
        if not any(c in cols for c in ACTIVITY_SIGNALS):
            return False
        return True

    def compute(self, df: pd.DataFrame) -> AnalysisPackage:
        res = _analyze(df)
        if res.get("skipped"):
            return _empty_package(res["reason"], res["suggestion"])

        user_level = res["user_level"]
        R_churn = res["R_churn"]
        G_bar = res["G_bar"]
        e = res["e"]

        status = user_level["流失状态"]
        N = len(user_level)
        N_churned = int((status == "已流失").sum())
        N_warned = int((status == "流失预警").sum())
        N_normal = int((status == "正常").sum())
        churn_rate = (N_churned / N) if N else 0.0
        health_rate = (N_normal / N) if N else 0.0

        # ===== KPI =====
        kpis = [
            KPIItem(label="用户总数", value=f"{N:,}"),
            KPIItem(label="已流失", value=f"{N_churned:,}"),
            KPIItem(label="流失预警", value=f"{N_warned:,}"),
            KPIItem(label="正常", value=f"{N_normal:,}"),
            KPIItem(label="流失率", value=f"{churn_rate:.1%}"),
            KPIItem(label="健康率", value=f"{health_rate:.1%}"),
            KPIItem(label="流失阈值 R_churn(天)", value=f"{R_churn:.2f}"),
            KPIItem(label="群体平均间隔(天)", value=f"{G_bar:.2f}"),
        ]

        # ===== 图表 =====
        charts = []

        # ① 三档人数对比（bar）
        tier_data = [
            {"档位": "已流失", "人数": N_churned},
            {"档位": "流失预警", "人数": N_warned},
            {"档位": "正常", "人数": N_normal},
        ]
        charts.append(ChartData(
            slot="churn_tier_bar", chart_type="bar",
            title="三档用户人数对比（已流失 / 流失预警 / 正常）",
            x="档位", y="人数", data=tier_data,
        ))
        # ①' 三档占比（pie）
        charts.append(ChartData(
            slot="churn_tier_pie", chart_type="pie",
            title="三档用户占比",
            x="档位", y="人数", data=tier_data,
        ))

        # ② R_login 分布（自适应分箱 bar，避免 histogram 类型重算原始列）
        # R_login 已在 _analyze 内 clip(lower=0)，此处 edges 再做严格递增保护双保险
        r_vals = user_level["R_login"].astype(float)
        max_r = float(r_vals.max()) if len(r_vals) else 0.0
        # 柱数自适应：按数据跨度与目标柱数挂钩，避免大跨度时 30+ 根柱子挤成一团
        TARGET_BINS = 15
        bin_w = max(15.0, round(max_r / TARGET_BINS))
        edges = list(range(0, int(max_r) + int(bin_w) + 1, int(bin_w)))
        edges = sorted(set(edges))                      # 去重 + 升序（pd.cut 要求严格递增）
        if len(edges) < 2:
            edges = [0, max(int(max_r), 0) + 1]
        bins = pd.cut(r_vals, bins=edges, right=False, include_lowest=True)
        dist = bins.value_counts().sort_index()
        # 长尾合并：超过流失阈值 R_churn 的尾部区间合并为一根 "≥X天" 尾巴桶，
        # 既压柱数又突出"流失危险区"整体体量
        tail_label = f"≥{R_churn:.2f}天"
        merged_tail = 0
        rows: list = []
        for iv, cnt in dist.items():
            if iv.left >= R_churn:
                merged_tail += int(cnt)
            else:
                rows.append({"距上次活跃天数区间(天)": f"{int(iv.left):g}", "人数": int(cnt)})
        if merged_tail > 0:
            rows.append({"距上次活跃天数区间(天)": tail_label, "人数": merged_tail})
        charts.append(ChartData(
            slot="r_login_dist", chart_type="bar",
            title="用户距上次活跃天数分布",
            x="距上次活跃天数区间(天)", y="人数", data=rows,
            chart_config={"threshold": float(R_churn), "threshold_label": "流失阈值"},
        ))

        insights = []

        # ⑥ 进阶 E：价值分层气泡矩阵
        if e:
            # 仅在已流失/流失预警人群上做气泡矩阵（正常用户不进 E，无气泡）
            e_scope = user_level[user_level["流失状态"].isin(["已流失", "流失预警"])].copy()
            # 价值缺失（"—"）用户既无分档也无挽回优先级，进气泡图纯属占位噪音；
            # 仅排除出图，仍保留在用户级明细表的"—"标签（诚实标注"没数据"）。
            e_scope = e_scope[e_scope["价值层"] != "—"]
            if "价值层" in e_scope.columns and len(e_scope) > 0:
                grp = e_scope.groupby(
                    ["价值层", "流失状态", "挽回优先级"]
                ).size().reset_index(name="人数")
                e_data = [
                    {"价值层": str(r["价值层"]), "流失状态": str(r["流失状态"]),
                     "挽回优先级": str(r["挽回优先级"]), BUBBLE_SIZE_COL: int(r["人数"])}
                    for _, r in grp.iterrows()
                ]
                # 列名契约：chart_renderer 不透传 size_col，create_bubble_matrix
                # 默认读"人数"列——契约破裂时立刻显式失败，绝不让图"无声消失"
                assert e_data and BUBBLE_SIZE_COL in e_data[0], \
                    f"气泡矩阵数据缺少「{BUBBLE_SIZE_COL}」列，与 create_bubble_matrix 契约不符"
                charts.append(ChartData(
                    slot="bubble_matrix__retention_priority", chart_type="bubble_matrix",
                    title="挽回优先级气泡矩阵（价值层 × 流失状态，气泡大小=人数）",
                    x="价值层", y="流失状态", data=e_data, color="挽回优先级",
                ))
            insights.append(
                "进阶 E 已触发：按全体用户价值分布 Q0.7/Q0.3 分位切高/中/低价值，"
                "对已流失/预警人群贴挽回优先级（紧急挽回/重点防护/标准召回/常规跟进/停止触达/常规维持），"
                "价值缺失用户不分档，仅贴附加列、不回改主标签。"
                "气泡矩阵图只展示有真实分档（高/中/低价值）的用户，"
                "价值缺失（—）用户已从图中剔除、仍保留在用户级明细表。")
        else:
            insights.append(
                "进阶 E 未触发：缺少价值列（CLV / 总消费金额，或可现场计算的"
                "订单实付金额 / 订单总额 / 购买金额）。")

        # ⑦ 进阶 F：流失归因（单一图族：每维度一张横向偏移图）
        f_result = _advanced_f(df, user_level)
        if f_result["triggered"]:
            charts.extend(f_result["charts"])
            if f_result.get("top_flag") is not None:
                user_level["流失集中维度TOP"] = f_result["top_flag"]
            insights.append(
                f"进阶 F 已触发：{f_result['dim_count']} 个白名单维度列完成流失归因，"
                "每维度独立产出偏移排名（正偏移=流失集中、负偏移=流失少），"
                "已为已流失用户标注[流失集中维度TOP]。")
        else:
            insights.append(f_result.get("note", "进阶 F 未触发：无可用白名单维度列。"))

        # ===== 用户级明细表（导出给用户；超上限截断，完整宽表见 segmentation_table）=====
        export_cols = ["用户ID", "R_login", "流失状态"]
        for extra in ("价值层", "挽回优先级", "流失集中维度TOP"):
            if extra in user_level.columns:
                export_cols.append(extra)
        ul_reset = user_level.reset_index()  # 用户ID 成为列
        rows_all = []
        for _, row in ul_reset.iterrows():
            rows_all.append({col: _jsonable(row[col]) for col in export_cols})
        rows = rows_all[:TABLE_CAP]
        if len(rows_all) > TABLE_CAP:
            insights.append(
                f"用户级明细表已截断展示前 {TABLE_CAP} 行（共 {len(rows_all)} 名用户）；"
                f"完整 {len(rows_all)} 行宽表可通过 segmentation_table 获取。"
            )
        tables = [TableData(
            title="用户级流失标签明细",
            table_type="user_churn",
            columns=export_cols,
            rows=rows,
            slot="churn_user_table",
        )]

        # ===== insights（覆盖核心结论 + 阈值依据 + 分支触发情况）=====
        insights.insert(0,
            f"参考时刻取最大订单时间；流失阈值 R_churn = 2 × 群体平均购买间隔 = {R_churn:.1f} 天"
            f"（仅 {G_bar:.1f} 天/单的多单用户计入均值）。")
        insights.insert(1,
            f"在 {N} 名用户中，{N_churned} 人已流失（流失率 {churn_rate:.1%}），"
            f"{N_warned} 人处于流失预警，{N_normal} 人正常（健康率 {health_rate:.1%}）。")

        # ===== findings：整体流失率 severity 标注（C' 改造）=====
        # 阈值写死：行业基准 >30% HIGH / >40% CRIT（流失率% 非天数）。
        findings = []
        churn_factory = FindingFactory("churn_rule")
        if churn_rate > 0.40:
            sev, sev_cat = Severity.CRITICAL, FindingCategory.RISK
        elif churn_rate > 0.30:
            sev, sev_cat = Severity.HIGH, FindingCategory.RISK
        else:
            sev = None
        if sev is not None:
            # bubble_matrix 仅在进阶 E（有金额/价值列）触发时产出；缺价值列则不产图，
            # 故 chart_slots 必须按实际产出条件引用，避免悬空（图不存在却声明为证据）。
            bubble_produced = any(
                getattr(c, "slot", None) == "bubble_matrix__retention_priority" for c in charts
            )
            churn_chart_slots = ["churn_tier_pie"]
            if bubble_produced:
                churn_chart_slots.append("bubble_matrix__retention_priority")
            findings.append(churn_factory.create(
                category=sev_cat,
                title=f"整体流失率 {churn_rate:.1%} 偏高",
                metric="流失率",
                entity="全量客户",
                value=round(churn_rate * 100, 1),
                unit="%",
                severity=sev,
                business_meaning=(
                    f"在 {N} 名用户中，{N_churned} 人已流失（流失率 {churn_rate:.1%}），"
                    f"{N_warned} 人处于流失预警，健康率仅 {health_rate:.1%}。"
                ),
                business_impact=(
                    "流失率超过电商行业基准（30% 警戒 / 40% 危急），存量客户价值正加速流失，"
                    "召回成本显著高于留存成本。"
                ),
                recommendation=(
                    f"建议对 {N_warned} 名流失预警用户启动定向召回，"
                    "对已流失的高价值人群优先紧急挽回，并复盘流失集中维度（见进阶 F）。"
                ),
                chart_slots=churn_chart_slots,
            ))

        return AnalysisPackage(
            id="churn_rule",
            analysis_type="churn_rule",
            business_question="哪些用户已流失 / 处于流失预警 / 仍正常？",
            algorithm="churn_rule_v1",
            dimension="用户",
            metric="流失状态",
            can_run=True,
            kpis=kpis,
            chart_data=charts,
            tables=tables,
            findings=findings,
            insights=insights,
            suggestion="可将用户级流失标签宽表导出用于定向召回；进阶分支已依据可用列自动触发。",
            confidence=1.0,
        )

    def segmentation_table(self, df: pd.DataFrame = None) -> pd.DataFrame | None:
        """返回每用户流失宽表（用户ID, R_login, 流失状态, [价值层/挽回优先级]…）供下游消费。

        隔离契约：重新走 _analyze 计算（不缓存 self 状态）；不原地修改 df。
        """
        if df is None:
            return None
        res = _analyze(df)
        if res.get("skipped"):
            return None
        ul = res["user_level"].reset_index()   # 用户ID 成为列
        return ul


def _jsonable(v):
    """把 numpy / pandas / bool 等转成 JSON 友好值。"""
    if isinstance(v, (pd.Timestamp,)):
        return str(v)
    if isinstance(v, (bool,)):
        return bool(v)
    try:
        if hasattr(v, "item"):
            return v.item()
    except Exception:
        pass
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    return v


register_model(ChurnRuleModel())
