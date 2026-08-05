"""K-means 通用聚类引擎（配置驱动）。

设计（见《K-means聚类引擎拆解.md》）：
- 共享管道：白名单校验 → 特征工程（实体级宽表 df_feat）→ 编码器（按 主键/数值/无序/日期 四类标签分派）→
  选 K（肘部+轮廓）→ KMeans 聚类 → 簇画像 → B 方案描述性命名 → 4 类可视化。
- 编码器函数体不出现任何业务列名，只认类型标签（三层职责分离）。
- USER_SEG 仅作 RFM 降级函数 run_user_seg(df)，不注册为独立模型；
  其余 5 个模块各自注册为 AnalysisModel，引擎逐表 can_run 命中即跑。
- 标准列名严格取自 column_mapping_dict.yaml 的规范字段（别名表覆盖之），不造新词。
"""
from __future__ import annotations

import bisect
import logging
import math
import random
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from src.analysis_engine.base import AnalysisModel
from src.analysis_templates.base import (
    AnalysisPackage,
    BusinessFinding,
    ChartData,
    Direction,
    EvidenceRef,
    FindingCategory,
    KPIItem,
    Severity,
    TableData,
)

logger = logging.getLogger(__name__)

# ============================================================
# 常量
# ============================================================
MAX_CARDINALITY = 20          # 无序列 nunique 超过此值整列剔除（高基数不进距离）
SIL_SAMPLE_SIZE = 10000       # 轮廓系数 O(n²)，n 超过则抽样
MIN_GROUP_N = 30               # GEO 单省最小实体数（过少聚合不稳则剔除）
K_MIN, K_MAX = 2, 7          # 选 K 遍历范围
RANDOM_STATE = 42             # 复现种子


# ============================================================
# 列名归一化（别名表，规范名取自 column_mapping_dict.yaml）
# ============================================================
COLUMN_ALIASES: Dict[str, List[str]] = {
    "用户ID": ["user_id", "userid", "uid", "客户ID", "会员ID", "买家ID"],
    "订单实付金额": ["paid_amount", "actual_paid", "order_amount", "实付金额", "成交金额", "支付金额", "订单金额"],
    "订单时间": ["order_time", "order_date", "paid_time", "下单时间", "成交时间"],
    "订单ID": ["order_id", "orderid", "oid", "交易ID"],
    "商品ID": ["product_id", "productid", "pid", "sku_id", "货品ID"],
    "商品单价": ["price", "unit_price", "单价", "售价"],
    "购买数量": ["quantity", "qty", "buy_count", "数量", "件数"],
    "商品成本": ["cost", "cost_price", "成本价"],
    "商品类目": ["category", "cat_name", "类目名称", "产品类目", "品类"],
    "类目ID": ["category_id", "cat_id", "cid"],
    "类目编码": ["category_code", "cat_code", "类目编码"],
    "品牌": ["brand", "brand_name"],
    "商品规格": ["spec", "specification", "规格"],
    "库存": ["stock", "inventory", "库存量"],
    "原价": ["original_price", "list_price", "标价"],
    "运费": ["shipping_fee", "freight", "邮费", "物流费"],
    "省份": ["province", "state", "省", "省区"],
    "城市": ["city", "城市名"],
    "邮编": ["zip", "postal_code", "邮政编码"],
    "事件时间": ["event_time", "action_time", "行为时间", "时间"],
    "行为类型": ["event_type", "action_type", "行为", "动作类型"],
    "在站时长": ["duration", "stay_time", "停留时长", "在线时长"],
    "浏览页面数": ["page_views", "pv", "浏览数", "页面数"],
    "访问次数": ["visit_count", "visits", "访问数"],
    "设备类型": ["device", "device_type", "终端"],
    "会话开始时间": ["session_start", "session_time", "会话时间"],
    "平台": ["platform", "plat"],
    "流量来源": ["traffic_source", "source", "渠道"],
    "最后活跃时间": ["last_active", "last_active_time", "最近活跃时间"],
    "注册日期": ["register_date", "signup_date", "注册时间", "入驻日期"],
    "退订状态": ["unsubscribe", "is_unsub", "退订"],
    "客诉次数": ["complaints", "complaint_count", "投诉数"],
    "注销时间": ["cancel_time", "close_time", "销户时间"],
    "退款金额": ["refund_amount", "refund", "退款"],
    "折扣金额": ["discount_amount", "discount", "折扣"],
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """将原始列名按别名表重命名为规范标准字段名（列名小写匹配）。"""
    if df is None or len(df.columns) == 0:
        return df
    df = df.copy()
    lower_map = {c: c.strip().lower() for c in df.columns}
    rename = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        alias_set = {a.lower() for a in aliases}
        alias_set.add(canonical.lower())
        for orig, low in lower_map.items():
            if low in alias_set and orig not in rename:
                rename[orig] = canonical
                break
    if rename:
        df = df.rename(columns=rename)
    return df


def _to_dt(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce")


def _mode(s: pd.Series):
    """返回出现频率最高的值（字符串化兜底），空则返回 '缺失'。"""
    s = s.dropna()
    if len(s) == 0:
        return "缺失"
    m = s.mode()
    return str(m.iloc[0]) if len(m) else "缺失"


def _safe_div(a, b, default=0.0):
    try:
        if b is None or b == 0 or (isinstance(b, float) and math.isnan(b)):
            return default
        return a / b
    except Exception:
        return default


# ============================================================
# 模块配置
# ============================================================
@dataclass
class KMeansModuleConfig:
    name: str
    display_name: str
    description: str
    primary_key: str                 # 实体分组键（用户ID/商品ID/省份）
    group_by: str                    # 聚合键（通常=primary_key；GEO=省份）
    core: Dict[str, str]            # 必需原生列 -> 类型标签(数值/无序/日期)
    optional: Dict[str, str]        # 可选原生列 -> 类型标签
    feature_fn: Callable             # (df, cfg) -> (df_feat, col_types)
    feature_labels: Dict[str, Dict[str, str]]   # 派生特征 -> {高,中,低} 中文词
    scatter: List[str]              # 二维散点默认 [x, y] 特征
    name_features: List[str]        # 用于命名/雷达的核心标量化特征
    entity_word: str                # 命名后缀（客/品/省/户）
    min_group_n: int = 0           # GEO 单省最小实体数（0=不限制）
    feature_display: Dict[str, str] = field(default_factory=dict)   # name_features 键 -> 展示名(含单位)
    feature_polarity: Dict[str, bool] = field(default_factory=dict) # name_features 键 -> 越高越好?(默认 True；负向量纲特征 False)


# ============================================================
# 特征工程（按模块，6 个 builder）
# ============================================================
def _ref_date(df: pd.DataFrame, *cols: str) -> pd.Timestamp:
    """参考日期 T_ref = 给定日期列的最大值；全缺则取当前日期。"""
    maxes = []
    for c in cols:
        if c in df.columns:
            mx = _to_dt(df[c]).max()
            if pd.notna(mx):
                maxes.append(mx)
    if maxes:
        return max(maxes)
    return pd.Timestamp.now().normalize()


def _build_user_seg(df: pd.DataFrame, cfg: KMeansModuleConfig):
    key = cfg.primary_key
    g = df.groupby(key)
    feat = pd.DataFrame(index=g.size().index)
    feat.index.name = key
    t_ref = _ref_date(df, "订单时间", "注册日期")
    feat["M"] = g["订单实付金额"].sum()
    # 每个用户的最近订单时间
    last = _to_dt(df.groupby(key)["订单时间"].max())
    feat["R"] = (t_ref - last).dt.days
    col_types = {"M": "数值", "R": "数值"}
    if "注册日期" in df.columns:
        first = _to_dt(df.groupby(key)["注册日期"].min())
        feat["客户年限"] = (t_ref - first).dt.days
        col_types["客户年限"] = "数值"
    if "退款金额" in df.columns:
        refunds = df.groupby(key)["退款金额"].sum()
        feat["退款率"] = feat["M"].map(refunds).fillna(0)
        den = feat["M"]
        den_valid = den.notna() & (den != 0)
        feat["退款率"] = (feat["退款率"] / den).where(den_valid, 0).replace([np.inf, -np.inf], 0)
        col_types["退款率"] = "数值"
    if "商品单价" in df.columns:
        feat["商品单价"] = g["商品单价"].mean()
        col_types["商品单价"] = "数值"
    for c in ("商品类目", "城市", "性别"):
        if c in df.columns:
            feat[c] = df.groupby(key)[c].apply(_mode)
            col_types[c] = "无序"
    feat = feat.reset_index()
    return feat, col_types


def _build_sku_seg(df: pd.DataFrame, cfg: KMeansModuleConfig):
    key = cfg.primary_key
    # 每个商品一行；若 商品ID 重复则聚合
    if df[key].duplicated().any():
        g = df.groupby(key)
        agg = {}
        for c in ("商品单价", "购买数量", "商品成本", "库存", "原价", "运费"):
            if c in df.columns:
                agg[c] = g[c].mean()
        for c in ("商品类目", "类目ID", "类目编码", "品牌", "商品规格"):
            if c in df.columns:
                agg[c] = df.groupby(key)[c].apply(_mode)
        feat = pd.DataFrame(agg).reset_index()
    else:
        feat = df.copy()
    num = feat["商品单价"] - feat["商品成本"]
    den = feat["商品单价"]
    den_valid = den.notna() & (den != 0)
    feat["毛利率"] = (num / den).where(den_valid, 0).replace([np.inf, -np.inf], 0)
    feat["销售额"] = feat["商品单价"] * feat["购买数量"]
    col_types = {c: "数值" for c in ("商品单价", "购买数量", "商品成本", "毛利率", "销售额")}
    if "库存" in feat.columns:
        col_types["库存"] = "数值"
    if "原价" in feat.columns:
        col_types["原价"] = "数值"
    if "运费" in feat.columns:
        col_types["运费"] = "数值"
    for c in ("商品类目", "类目ID", "类目编码", "品牌", "商品规格"):
        if c in feat.columns:
            col_types[c] = "无序"
    return feat, col_types


def _build_geo_seg(df: pd.DataFrame, cfg: KMeansModuleConfig):
    key = cfg.primary_key            # 用户ID（用于计数）
    gb = cfg.group_by              # 省份
    if "订单ID" in df.columns:
        orders = df.groupby(gb)["订单ID"].nunique()
    else:
        orders = df.groupby(gb).size()
    users = df.groupby(gb)[key].nunique()
    pay = df.groupby(gb)["订单实付金额"].sum()
    prov = pd.DataFrame({
        "地域ARPU": pay / users.replace(0, np.nan),
        "地域客单价": pay / orders.replace(0, np.nan),
        "地域订单密度": orders / users.replace(0, np.nan),
    })
    if "运费" in df.columns:
        prov["运费"] = df.groupby(gb)["运费"].mean()
    for c in ("城市", "邮编", "商品类目"):
        if c in df.columns:
            prov[c] = df.groupby(gb)[c].apply(_mode)
    prov = prov.reset_index()
    if cfg.min_group_n and cfg.min_group_n > 0:
        keep = users[users >= cfg.min_group_n].index
        prov = prov[prov[gb].isin(keep)].reset_index(drop=True)
    col_types = {"地域ARPU": "数值", "地域客单价": "数值", "地域订单密度": "数值"}
    if "运费" in prov.columns:
        col_types["运费"] = "数值"
    for c in ("城市", "邮编", "商品类目"):
        if c in prov.columns:
            col_types[c] = "无序"
    return prov, col_types


def _build_activity_seg(df: pd.DataFrame, cfg: KMeansModuleConfig):
    key = cfg.primary_key
    g = df.groupby(key)
    feat = pd.DataFrame(index=g.size().index)
    feat.index.name = key
    if "事件时间" in df.columns:
        dt = _to_dt(df["事件时间"])
        active_days = df.assign(_d=dt.dt.date).groupby(key)["_d"].nunique()
        feat["日活频次"] = g.size() / active_days.replace(0, np.nan)
        hours = dt.dt.hour
        bins = pd.cut(hours, [0, 6, 12, 18, 24], labels=["深夜", "上午", "下午", "晚间"], include_lowest=True)
        dist = df.assign(_u=df[key], _b=bins).groupby(["_u", "_b"]).size().unstack(fill_value=0)
        total = dist.sum(axis=1)
        for b in ("深夜", "上午", "下午", "晚间"):
            if b in dist.columns:
                feat[f"时段_{b}"] = (dist[b] / total.replace(0, np.nan)).fillna(0)
    if "行为类型" in df.columns:
        # 漏斗：下单数 / 加购数（缺加购则用总事件数）
        def _ratio(sub):
            n_order = (sub["行为类型"].astype(str).str.contains("下单|支付|购买", na=False)).sum()
            n_cart = (sub["行为类型"].astype(str).str.contains("加购|加购", na=False)).sum()
            denom = n_cart if n_cart > 0 else len(sub)
            return _safe_div(n_order, denom)
        feat["行为漏斗转化比"] = df.groupby(key).apply(_ratio)
    for c in ("在站时长", "浏览页面数", "访问次数"):
        if c in df.columns:
            feat[c] = g[c].mean() if c != "访问次数" else g[c].sum()
    if "会话开始时间" in df.columns:
        st = _to_dt(df["会话开始时间"])
        sess = df.assign(_u=df[key], _t=st).groupby("_u")["_t"].agg(lambda s: (s.max() - s.min()).total_seconds() / 3600.0)
        feat["会话时长"] = sess
    for c in ("设备类型", "平台", "流量来源", "行为类型"):
        if c in df.columns:
            feat[c] = df.groupby(key)[c].apply(_mode)
    col_types = {}
    for c in ("日活频次", "时段_深夜", "时段_上午", "时段_下午", "时段_晚间",
              "行为漏斗转化比", "在站时长", "浏览页面数", "访问次数", "会话时长"):
        if c in feat.columns:
            col_types[c] = "数值"
    for c in ("设备类型", "平台", "流量来源", "行为类型"):
        if c in feat.columns:
            col_types[c] = "无序"
    feat = feat.reset_index()
    return feat, col_types


def _build_category_seg(df: pd.DataFrame, cfg: KMeansModuleConfig):
    key = cfg.primary_key
    g = df.groupby(key)
    feat = pd.DataFrame(index=g.size().index)
    feat.index.name = key
    t_ref = _ref_date(df, "订单时间")
    feat["购买数量"] = g["购买数量"].sum()
    if "商品类目" in df.columns:
        cat = df.groupby(key)["商品类目"].apply(_mode)
        feat["商品类目"] = cat
        # 各类目消费/数量占比：取全局出现最多的 8 个类目（金额优先，退回数量/计数）
        valcol = "订单实付金额" if "订单实付金额" in df.columns else ("购买数量" if "购买数量" in df.columns else None)
        if valcol:
            pay = df.assign(_p=df[valcol]).groupby([key, "商品类目"])["_p"].sum()
            total = g[valcol].sum()
            top_cats = df["商品类目"].value_counts().head(8).index.tolist()
            for c in top_cats:
                share = pay.xs(c, level="商品类目") if c in pay.index.get_level_values("商品类目") else pd.Series(dtype=float)
                feat[f"占比_{c}"] = share.reindex(feat.index).fillna(0) / total.replace(0, np.nan)
    if "类目ID" in df.columns:
        feat["跨类目广度"] = df.groupby(key)["类目ID"].nunique()
    if "订单时间" in df.columns:
        last = _to_dt(df.groupby(key)["订单时间"].max())
        feat["最近购买间隔"] = (t_ref - last).dt.days
    if "折扣金额" in df.columns:
        feat["折扣金额"] = g["折扣金额"].sum()
    if "商品单价" in df.columns:
        feat["商品单价"] = g["商品单价"].mean()
    col_types = {"购买数量": "数值"}
    if "跨类目广度" in feat.columns:
        col_types["跨类目广度"] = "数值"
    if "最近购买间隔" in feat.columns:
        col_types["最近购买间隔"] = "数值"
    if "折扣金额" in feat.columns:
        col_types["折扣金额"] = "数值"
    if "商品单价" in feat.columns:
        col_types["商品单价"] = "数值"
    for c in feat.columns:
        if c.startswith("占比_"):
            col_types[c] = "数值"
    if "商品类目" in feat.columns:
        col_types["商品类目"] = "无序"
    feat = feat.reset_index()
    return feat, col_types


def _build_churn_seg(df: pd.DataFrame, cfg: KMeansModuleConfig):
    key = cfg.primary_key
    g = df.groupby(key)
    feat = pd.DataFrame(index=g.size().index)
    feat.index.name = key
    t_ref = _ref_date(df, "最后活跃时间", "订单时间", "注销时间")
    if "最后活跃时间" in df.columns:
        last = _to_dt(df.groupby(key)["最后活跃时间"].max())
        feat["静默天数"] = (t_ref - last).dt.days
    if "订单实付金额" in df.columns:
        feat["历史消费"] = g["订单实付金额"].sum()
    if "客诉次数" in df.columns:
        comp = df.groupby(key)["客诉次数"].sum()
        if "订单ID" in df.columns:
            denom = df.groupby(key)["订单ID"].nunique()
        else:
            denom = g.size()
        feat["投诉率"] = comp / denom.replace(0, np.nan)
    if "订单时间" in df.columns:
        last_o = _to_dt(df.groupby(key)["订单时间"].max())
        feat["最近购买"] = (t_ref - last_o).dt.days
    if "注册日期" in df.columns:
        first = _to_dt(df.groupby(key)["注册日期"].min())
        feat["客户年限"] = (t_ref - first).dt.days
    if "退订状态" in df.columns:
        feat["退订状态"] = df.groupby(key)["退订状态"].apply(_mode)
    if "客诉次数" in df.columns:
        feat["客诉次数"] = g["客诉次数"].sum()
    if "退款金额" in df.columns:
        feat["退款金额"] = g["退款金额"].sum()
    if "注销时间" in df.columns:
        cn = _to_dt(df.groupby(key)["注销时间"].max())
        feat["是否已注销"] = cn.notna().astype(int)
    col_types = {}
    for c in ("静默天数", "历史消费", "投诉率", "最近购买", "客户年限", "客诉次数", "退款金额", "是否已注销"):
        if c in feat.columns:
            col_types[c] = "数值"
    if "退订状态" in feat.columns:
        col_types["退订状态"] = "无序"
    feat = feat.reset_index()
    return feat, col_types


# ============================================================
# 编码器（通用，只认类型标签；函数体不含业务列名）
# ============================================================
def _encode(df_feat: pd.DataFrame, col_types: Dict[str, str]):
    """返回 (X, feat_cols, valid_mask)。X 已对数值列做 StandardScaler，无序列做 OneHot。"""
    num_blocks, nom_blocks = [], []
    num_cols, nom_cols = [], []
    for col, tag in col_types.items():
        if col not in df_feat.columns:
            continue
        if tag in ("主键",):
            continue
        s = df_feat[col]
        if tag in ("数值", "日期"):
            v = pd.to_numeric(s, errors="coerce").fillna(0.0).values.reshape(-1, 1)
            num_blocks.append(v)
            num_cols.append(col)
        elif tag == "无序":
            if s.nunique(dropna=True) > MAX_CARDINALITY:
                continue  # 高基数剔除
            d = pd.get_dummies(s.fillna("缺失").astype(str), prefix=col)
            if d.shape[1] == 0:
                continue
            nom_blocks.append(d.values)
            nom_cols.extend(d.columns.tolist())
    Xnum = StandardScaler().fit_transform(np.hstack(num_blocks)) if num_blocks else np.empty((len(df_feat), 0))
    Xnom = np.hstack(nom_blocks) if nom_blocks else np.empty((len(df_feat), 0))
    if Xnum.size == 0 and Xnom.size == 0:
        return np.empty((len(df_feat), 0)), [], np.ones(len(df_feat), dtype=bool)
    X = np.hstack([Xnum, Xnom])
    valid = ~np.isnan(X).any(axis=1)
    feat_cols = num_cols + nom_cols
    return X, feat_cols, valid


# ============================================================
# 选 K（肘部 Inertia + 轮廓系数 Silhouette）
# ============================================================
def _elbow_k(inertia_pts: List[Tuple[float, float]]) -> float:
    """肘部拐点：Inertia 曲线上「最陡弯折角」(最大曲率) 对应的 K。

    与「点到首末连线垂直距离」法相比，曲率法更贴合人眼对肘部拐角的判断
    （后者在缓降曲线上会把拐点算偏 1 位）。inertia_pts 已按 K 升序排列。
    """
    if len(inertia_pts) < 3:
        # 不足 3 个点无法判断肘部，回退到最小 K（或唯一 K）
        return inertia_pts[0][0] if inertia_pts else 2
    ks = [p[0] for p in inertia_pts]
    y = np.array([p[1] for p in inertia_pts], dtype=float)
    # 归一化：让 K 间距与 Inertia 量级可比
    x = np.arange(len(y), dtype=float)
    if x.max() > 0:
        x = x / x.max()
    ymin, ymax = float(y.min()), float(y.max())
    yn = (y - ymin) / (ymax - ymin) if ymax > ymin else np.zeros_like(y)
    # 二阶差分最大（最正）处即最陡的弯折角 = 肘部
    diff2 = np.diff(yn, n=2)
    idx = int(np.argmax(diff2)) + 1  # diff2[0] 对应原序列 index 1
    return ks[idx]


def _select_k(X: np.ndarray, k_min: int = K_MIN, k_max: int = K_MAX, _depth: int = 0):
    """选 K（两法融合，见《K-means聚类引擎拆解.md》）：

    - 肘部(Inertia 拐点) K₁ 与 轮廓系数(Silhouette 峰值) K₂ 吻合 → 直接取；
    - 不一致 → 缩小搜索区间复验一次（至多一层）；
    - 复验仍不一致 → 按业务偏好取轮廓系数峰值 K（其更反映簇分离质量），
      并标记 method='silhouette_override' 以便上层提示用户确认。
    返回 (best_k, inertia_pts, sil_pts, method)。
    """
    random.seed(RANDOM_STATE)
    n = X.shape[0]
    ks = list(range(k_min, min(k_max, n) + 1))
    if not ks:
        ks = [2]
    inertia_pts, sil_pts = [], []
    for k in ks:
        km = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE)
        labels = km.fit_predict(X)
        inertia_pts.append((k, float(km.inertia_)))
        if len(set(labels)) < 2:
            sil_pts.append((k, float("nan")))
            continue
        try:
            if n > SIL_SAMPLE_SIZE:
                idx = random.sample(range(n), SIL_SAMPLE_SIZE)
                s = silhouette_score(X[idx], labels[idx])
            else:
                s = silhouette_score(X, labels)
        except Exception:
            s = float("nan")
        sil_pts.append((k, s))
    k_elbow = _elbow_k(inertia_pts)
    valid = [(k, s) for k, s in sil_pts if not (isinstance(s, float) and math.isnan(s))]
    k_sil = max(valid, key=lambda x: x[1])[0] if valid else ks[0]
    if k_elbow == k_sil:
        best_k, method = k_elbow, "agreed"
    else:
        # 两法不一致：缩小搜索区间复验（至多一层）
        if _depth < 1:
            lo = max(k_min, min(k_elbow, k_sil) - 1)
            hi = min(min(k_max, n), max(k_elbow, k_sil) + 1)
            if hi - lo >= 1:
                return _select_k(X, lo, hi, _depth + 1)
        # 复验仍不一致 → 按业务偏好取轮廓系数峰值 K
        best_k, method = k_sil, "silhouette_override"
    return best_k, inertia_pts, sil_pts, method


# ============================================================
# 可分性早退（严格档）：肘部/轮廓曲线任一过平 → 数据不适合聚类
# ============================================================
SEP_INERTIA_DROP_MIN = 0.10   # 肘部首尾降幅 <10% → 视为无起伏
SEP_SIL_RANGE_MIN = 0.08       # 轮廓有效跨度 <0.08 → 视为无起伏

def _is_separable(inertia_pts, sil_pts):
    """判断数据是否可分：两曲线至少一条有明显起伏才继续。

    返回 (可分?, 原因)。严格档：任一曲线过平即判不可分（用户原话「或」）。
    - 肘部 Inertia 随 K 单调递减，drop=(首-末)/首 越小越平；
    - 轮廓 Silhouette 取有效(非 nan)跨度，span=max-min 越小越平。
    边界：K 范围退化（仅 1 点 / 轮廓全 nan）跳过对应项，避免误退。
    """
    reasons = []
    if len(inertia_pts) >= 2:
        all_i = [v for _, v in inertia_pts]
        i_first = inertia_pts[0][1]
        i_last = inertia_pts[-1][1]
        # 全同质：inertia 全为 0 或各 K 完全相等 → 数据无结构，直接判不可分
        # （避免 i_first==0 时 `if i_first` 漏判、及除零）
        if i_first == 0 or (max(all_i) - min(all_i)) <= 1e-9:
            reasons.append("肘部曲线完全无变化（数据高度同质，无结构）")
        elif not (isinstance(i_first, float) and math.isnan(i_first)):
            drop = (i_first - i_last) / i_first
            if drop < SEP_INERTIA_DROP_MIN:
                reasons.append(f"肘部曲线首尾仅下降 {drop:.0%}，几乎无起伏")
    valid_sil = [s for _, s in sil_pts if not (isinstance(s, float) and math.isnan(s))]
    if len(valid_sil) >= 2:
        span = max(valid_sil) - min(valid_sil)
        if span < SEP_SIL_RANGE_MIN:
            reasons.append(f"轮廓系数跨度仅 {span:.3f}，各 K 区分度极低")
    if reasons:
        return False, "；".join(reasons)
    return True, ""


# ============================================================
# 聚类 + 画像 + B 方案命名
# ============================================================
def _cluster(X: np.ndarray, k: int):
    km = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE)
    labels = km.fit_predict(X)
    return labels, km


def _profile(df_feat: pd.DataFrame, labels: np.ndarray, feat_cols: List[str]):
    prof: Dict[int, Dict[str, Any]] = {}
    for c in sorted(set(labels)):
        sub = df_feat[labels == c]
        means = {col: float(sub[col].mean()) if col in df_feat.columns else 0.0 for col in feat_cols}
        prof[c] = {"size": int((labels == c).sum()), "means": means}
    return prof


def _name_clusters(df_feat: pd.DataFrame, labels: np.ndarray, cfg: KMeansModuleConfig,
                   prof: Dict[int, Dict[str, Any]]):
    name_feats = [f for f in cfg.name_features if f in df_feat.columns]
    if not name_feats:
        name_feats = [c for c in df_feat.columns if pd.api.types.is_numeric_dtype(df_feat[c])][:2]
    global_means = {f: float(df_feat[f].mean()) if f in df_feat.columns else 0.0 for f in name_feats}
    names: Dict[int, str] = {}
    for c, p in prof.items():
        sig = {}
        for f in name_feats:
            gm = global_means[f]
            gv = p["means"].get(f, 0.0)
            if gm == 0:
                sig[f] = "中"
            else:
                ratio = gv / gm if gm != 0 else 1.0
                sig[f] = "高" if ratio > 1.15 else ("低" if ratio < 0.85 else "中")
        dev = [f for f in name_feats if sig[f] != "中"]
        dev.sort(key=lambda f: abs(p["means"].get(f, 0.0) - global_means[f]), reverse=True)
        top = dev[:2] if len(dev) >= 2 else dev[:]
        words = []
        for f in top:
            lab = cfg.feature_labels.get(f, {})
            words.append(lab.get(sig[f], sig[f]))
        name = ("".join(words) + cfg.entity_word) if words else f"均衡{cfg.entity_word}"
        names[c] = name
    return names


# ============================================================
# 4 类可视化
# ============================================================
def _feat_col(cfg: KMeansModuleConfig, f: str) -> str:
    """统一列名：name_features 键 -> 展示名(含单位)，保证后端表/雷达与前端的列名一致。"""
    return cfg.feature_display.get(f, f)


def _cluster_cell(val: float, vals: List[float], higher_is_better: bool):
    """簇画像总览表的颜色元数据：rank(0~1 簇间相对排名) + direction(good/bad/equal)。

    基准 = 各簇均值的平均（与 user_profile._cell_num 对齐，做簇间对比）；
    极性按特征高/低好坏翻转：负向量纲(如静默天数) 越高越差，比值>均值时判为 bad(红)。
    """
    if val is None or not vals:
        return {"value": val, "cell_type": "neutral", "direction": "neutral", "rank": 0.0}
    asc = sorted(vals)
    cnt = len(asc)
    if higher_is_better:
        rank = bisect.bisect_right(asc, val) / cnt          # 最好=1，最差=1/cnt
    else:
        rank = (cnt - bisect.bisect_left(asc, val)) / cnt   # 最好(最小值)=1，最差=1/cnt，与正向对称
    mean = sum(asc) / cnt
    if mean == 0:
        direction = "equal"
    else:
        d = (val - mean) / abs(mean)
        if d > 0.05:
            direction = "good" if higher_is_better else "bad"
        elif d < -0.05:
            direction = "bad" if higher_is_better else "good"
        else:
            direction = "equal"
    return {"value": val, "cell_type": "number", "direction": direction, "rank": round(rank, 3)}


def _build_charts(df_feat, labels, names, cfg):
    """仅产出【簇画像雷达图】作为业务主图。

    每簇一条 series（series.name = B方案业务描述，仅作辅助标注）；
    indicator = 本模块特征（展示名含单位），动态取不写死；
    用途是业务一眼看各自然群特征形态差异，不在图内做好坏判断。
    选K折线 / 簇规模 / 散点 三图已删除（其背后的 _select_k / _is_separable 早退仍保留在 run_kmeans）。
    """
    charts: List[ChartData] = []
    # 流失风险聚类不产出雷达图（业务主图）
    if cfg.name == "churn_seg":
        return charts
    radar_feats = [f for f in cfg.name_features if f in df_feat.columns]
    if len(radar_feats) >= 2:
        radar_rows = []
        for c in sorted(set(labels)):
            row = {"簇": names[c]}
            for f in radar_feats:
                sub = df_feat[labels == c]
                col = _feat_col(cfg, f)
                row[col] = round(float(sub[f].mean()), 4) if f in df_feat.columns else 0.0
            radar_rows.append(row)
        charts.append(ChartData(
            slot="cluster_radar", chart_type="radar",
            title="各簇特征差异画像（业务主图）",
            x="簇", y="", data=radar_rows,
            chart_config={"kind": "cluster_radar"}))
    return charts


def _profile_one(df_feat, labels, c):
    sub = df_feat[labels == c]
    return {"size": int(len(sub))}


# ============================================================
# 表 / KPI / 发现 / 洞察
# ============================================================
def _build_tables(df_feat, labels, names, cfg):
    """【簇画像总览表】(profile_overview)：行=簇，列分三区块。

    规模区(人数/占比) / 核心特征区(各特征均值，动态) / 业务动作建议区。
    特征均值单元格携带 direction(好/持平/差) 与 rank(簇间相对排名) 颜色元数据，
    由后端算好随数据下发（前端禁止重算）。业务动作建议列后端仅占位，由前端按
    chart_config.module + feature_cols 的写死规则填充。
    """
    feats = [f for f in cfg.name_features if f in df_feat.columns]
    feats_shown = [_feat_col(cfg, f) for f in feats]
    total = len(df_feat)
    clusters = sorted(set(labels))
    # 各簇均值（用于簇间排名与基准）
    cluster_means = {c: {f: float(df_feat[labels == c][f].mean()) if f in df_feat.columns else 0.0
                     for f in feats} for c in clusters}
    # 每特征：各簇均值集合（基准 + 排名）
    feat_vals = {f: [cluster_means[c][f] for c in clusters] for f in feats}

    columns = ["簇", "人数", "占比"] + feats_shown + ["业务动作建议"]
    rows = []
    for c in clusters:
        size = int((labels == c).sum())
        row: dict = {}
        row["簇"] = {"value": names[c], "cell_type": "category"}
        row["人数"] = {"value": size, "cell_type": "neutral"}
        row["占比"] = {"value": round(size / total, 4) if total else 0.0,
                        "cell_type": "percentage", "direction": "neutral"}
        for f, shown in zip(feats, feats_shown):
            higher = cfg.feature_polarity.get(f, True)
            cell = _cluster_cell(cluster_means[c][f], feat_vals[f], higher)
            cell["value"] = round(cell["value"], 4) if cell["value"] is not None else None
            row[shown] = cell
        # 业务动作建议：后端占位，前端 ACTION_RULES 按 direction 填充
        row["业务动作建议"] = {"value": "", "cell_type": "category"}
        rows.append(row)

    blocks = [
        {"title": "规模区", "keys": ["簇", "人数", "占比"]},
        {"title": "核心特征区", "keys": feats_shown},
        {"title": "业务建议区", "keys": ["业务动作建议"]},
    ]
    return [TableData(
        title=f"{cfg.display_name} 簇画像总览",
        table_type="profile_overview",
        columns=columns,
        rows=rows,
        chart_config={
            "kind": "seg_profile_overview",
            "module": cfg.name,
            "feature_cols": feats_shown,
            "blocks": blocks,
        },
        slot="kmeans_cluster_overview_table",
    )]


def _build_kpis(df_feat, labels, names, cfg, best_k, sil_score):
    total = len(df_feat)
    sizes = [int((labels == c).sum()) for c in sorted(set(labels))]
    largest = max(sizes) if sizes else 0
    kpis = [
        KPIItem(label="聚类实体数", value=f"{total}", kpi_type="count"),
        KPIItem(label="最佳簇数 K", value=f"{best_k}", kpi_type="count"),
        KPIItem(label="最大簇占比", value=f"{round(largest / total, 4) if total else 0:.0%}", kpi_type="ratio"),
        KPIItem(label="轮廓系数", value=f"{round(float(sil_score), 3) if not (isinstance(sil_score, float) and math.isnan(sil_score)) else 0.0:.3f}", kpi_type="score"),
    ]
    return kpis


def _build_findings(df_feat, labels, names, cfg, best_k):
    findings: List[BusinessFinding] = []
    total = len(df_feat)
    name_feats = [f for f in cfg.name_features if f in df_feat.columns]
    global_means = {f: float(df_feat[f].mean()) for f in name_feats}
    insights: List[str] = []
    for c in sorted(set(labels)):
        sub = df_feat[labels == c]
        size = len(sub)
        dev_desc = []
        for f in name_feats:
            gv = float(sub[f].mean()) if f in df_feat.columns else 0.0
            gm = global_means.get(f, 0.0)
            if gm != 0:
                ratio = gv / gm
                if ratio > 1.15:
                    dev_desc.append(f"{cfg.feature_labels.get(f, {}).get('高', '高')}（{f}≈{gv:.1f}，全局≈{gm:.1f}）")
                elif ratio < 0.85:
                    dev_desc.append(f"{cfg.feature_labels.get(f, {}).get('低', '低')}（{f}≈{gv:.1f}，全局≈{gm:.1f}）")
        desc = "；".join(dev_desc) if dev_desc else "各项特征接近全局均值"
        title = f"簇 {names[c]}：{size} 个{cfg.entity_word}（占比 {size / total:.0%}）"
        f = BusinessFinding(
            id=str(uuid.uuid4()),
            analysis_type=cfg.name,
            category=FindingCategory.STRUCTURE,
            title=title,
            description=f"该簇画像特征：{desc}。",
            metric="簇规模",
            dimension=cfg.name,
            entity=names[c],
            value=float(size),
            unit=cfg.entity_word,
            severity=Severity.MEDIUM,
            confidence=0.8,
            business_meaning=f"该群体在{cfg.display_name}中表现为{desc}。",
            recommendation="可针对该群体制定差异化运营策略。",
        ).link_evidence(chart_slots=["cluster_radar"])
        findings.append(f)
        insights.append(f"{names[c]}（{size} 个{cfg.entity_word}，{size / total:.0%}）：{desc}。")
    return findings, insights


# ============================================================
# 跳过 / 降级包
# ============================================================
def _skipped(cfg: KMeansModuleConfig, reason: str, suggestion: str) -> AnalysisPackage:
    return AnalysisPackage(
        id=cfg.name, analysis_type=cfg.name, business_question=cfg.description,
        algorithm="KMeans", dimension=cfg.name, metric=cfg.name,
        can_run=False, suggestion=suggestion,
        findings=[], insights=[f"未执行：{reason}"], conclusions=[], recommendations=[],
        chart_data=[], tables=[], kpis=[],
        metadata={"reason": reason},
    )


# ============================================================
# 共享管道
# ============================================================
def run_kmeans(df: pd.DataFrame, cfg: KMeansModuleConfig) -> AnalysisPackage:
    """配置驱动的共享 K-means 聚类管道。"""
    try:
        norm = _normalize_columns(df)
        if not set(cfg.core).issubset(norm.columns):
            missing = [c for c in cfg.core if c not in norm.columns]
            return _skipped(cfg, "缺少必需列", f"需要列：{', '.join(cfg.core)}；缺失：{', '.join(missing)}")
        df_feat, col_types = cfg.feature_fn(norm, cfg)
        if df_feat is None or len(df_feat) == 0:
            return _skipped(cfg, "无有效实体", "表中没有可聚合的实体记录。")
        X, feat_cols, valid = _encode(df_feat, col_types)
        if X.size == 0 or X.shape[1] < 1:
            return _skipped(cfg, "无可聚类特征", "缺少数值或低基数类别特征，无法计算距离。")
        df_feat = df_feat[valid].reset_index(drop=True)
        X = X[valid]
        if len(df_feat) < 2:
            return _skipped(cfg, "有效实体不足2个", "有效实体过少，无法聚成多个簇。")
        best_k, inertia_pts, sil_pts, k_method = _select_k(X)
        # ★ 可分性早退：肘部/轮廓任一过平 → 数据不适合聚类，直接退出
        sep_ok, sep_reason = _is_separable(inertia_pts, sil_pts)
        if not sep_ok:
            return _skipped(cfg, "数据不适合聚类",
                           f"{sep_reason}。K-means 难以分出有效簇，建议检查特征选择或数据质量后再试。")
        labels, _ = _cluster(X, best_k)
        if len(set(labels)) < 2:
            return _skipped(cfg, "无法区分出多个簇", "样本特征过于同质，聚类后仅 1 个簇。")
        prof = _profile(df_feat, labels, feat_cols)
        names = _name_clusters(df_feat, labels, cfg, prof)
        charts = _build_charts(df_feat, labels, names, cfg)
        tables = _build_tables(df_feat, labels, names, cfg)
        kpis = _build_kpis(df_feat, labels, names, cfg, best_k,
                           dict(sil_pts).get(best_k, float("nan")))
        findings, insights = _build_findings(df_feat, labels, names, cfg, best_k)
        total = len(df_feat)
        sizes = [int((labels == c).sum()) for c in sorted(set(labels))]
        largest = max(sizes) if sizes else 0
        conclusions = [f"基于 {cfg.display_name} 的 {total} 个{cfg.entity_word}、"
                       f"{best_k} 个特征维度聚为 {best_k} 类，最大簇占 {largest / total:.0%}。"]
        recommendations = ["建议依据各簇画像实施分层运营（高价值重点维护、潜力客群促活、流失风险客群挽留）。"]
        # 两法融合结果透明化：记录肘部拐点 K 与轮廓峰值 K，不一致时提示用户确认
        k_elbow = _elbow_k(inertia_pts)
        valid_sil = [(k, s) for k, s in sil_pts if not (isinstance(s, float) and math.isnan(s))]
        k_sil = max(valid_sil, key=lambda x: x[1])[0] if valid_sil else best_k
        if k_method == "silhouette_override":
            recommendations.append(
                f"肘部拐点(K={k_elbow})与轮廓系数峰值(K={k_sil})不一致，"
                f"已按业务偏好（轮廓系数更反映簇分离质量）选定 K={best_k}，建议结合业务确认。"
            )
        return AnalysisPackage(
            id=cfg.name, analysis_type=cfg.name, business_question=cfg.description,
            algorithm="KMeans", dimension=cfg.name, metric=cfg.name,
            can_run=True,
            chart_data=charts, tables=tables, kpis=kpis,
            findings=findings, insights=insights,
            conclusions=conclusions, recommendations=recommendations,
            metadata={
                "k": best_k, "module": cfg.name, "n_entities": total,
                "n_features": X.shape[1], "silhouette": dict(sil_pts).get(best_k),
                "k_elbow": k_elbow, "k_sil": k_sil, "k_method": k_method,
                "cluster_sizes": {names[c]: int((labels == c).sum()) for c in sorted(set(labels))},
            },
            confidence=0.8, calculator_used="kmeans", template_used=cfg.name,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("K-means 管道异常（%s）", cfg.name)
        return _skipped(cfg, f"计算异常：{e}", "数据存在异常格式或缺失，请检查后重试。")


def run_user_seg(df: pd.DataFrame) -> AnalysisPackage:
    """USER_SEG 降级函数（不注册为模型）。仅 M+R 两维，永不含订单ID。"""
    return run_kmeans(df, USER_SEG_CONFIG)


def user_seg_label_users(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """USER_SEG 每用户簇宽表：返回每用户 [用户ID, M, R, 簇(命名标签)]。

    复刻 run_kmeans 共享管道（_build_user_seg / _encode / _select_k / _cluster /
    _profile / _name_clusters）与 RANDOM_STATE=42，故簇名与 run_user_seg 完全一致。
    实体<2 或异常返回 None。供下游用户画像消费（瞬态）。
    """
    try:
        norm = _normalize_columns(df)
        if not set(USER_SEG_CONFIG.core).issubset(norm.columns):
            return None
        df_feat, col_types = USER_SEG_CONFIG.feature_fn(norm, USER_SEG_CONFIG)
        if df_feat is None or len(df_feat) == 0:
            return None
        X, feat_cols, valid = _encode(df_feat, col_types)
        if X.size == 0 or X.shape[1] < 1:
            return None
        df_feat = df_feat[valid].reset_index(drop=True)
        X = X[valid]
        if len(df_feat) < 2:
            return None
        best_k, inertia_pts, sil_pts, _ = _select_k(X)
        # ★ 可分性早退（与 run_kmeans 一致，严格档）
        if not _is_separable(inertia_pts, sil_pts)[0]:
            return None
        labels, _ = _cluster(X, best_k)
        if len(set(labels)) < 2:
            return None
        prof = _profile(df_feat, labels, feat_cols)
        names = _name_clusters(df_feat, labels, USER_SEG_CONFIG, prof)
        out = pd.DataFrame({
            "用户ID": df_feat["用户ID"].astype(str).tolist(),
            "M": df_feat["M"].tolist(),
            "R": df_feat["R"].tolist(),
            "簇": [names[int(c)] for c in labels],
        })
        return out
    except Exception:
        return None


# ============================================================
# 模块配置（6 份）
# ============================================================
USER_SEG_CONFIG = KMeansModuleConfig(
    name="user_seg", display_name="用户价值分层",
    description="按消费力与活跃度对用户做价值分层（RFM 降级：无订单ID 时启用）",
    primary_key="用户ID", group_by="用户ID",
    core={"用户ID": "主键", "订单实付金额": "数值", "订单时间": "日期"},
    optional={"商品类目": "无序", "注册日期": "日期", "退款金额": "数值", "性别": "无序", "城市": "无序", "商品单价": "数值"},
    feature_fn=_build_user_seg,
    feature_labels={
        "M": {"高": "高消费", "中": "中消费", "低": "低消费"},
        "R": {"高": "久未购", "中": "偶活跃", "低": "近期活跃"},
        "客户年限": {"高": "老客", "低": "新客"},
        "退款率": {"高": "高退款", "低": "低退款"},
        "商品单价": {"高": "高单价", "低": "低单价"},
    },
    scatter=["M", "R"], name_features=["M", "R"], entity_word="客",
    feature_display={"M": "消费金额(元)", "R": "购买间隔(天)"},
    # R = 距最近一次购买的天数（Recency），越大越久未购=越差 → 负向量纲
    feature_polarity={"M": True, "R": False},
)

SKU_SEG_CONFIG = KMeansModuleConfig(
    name="sku_seg", display_name="商品聚类",
    description="按价格、销量、毛利等特征对商品做聚类，识别商品矩阵结构",
    primary_key="商品ID", group_by="商品ID",
    core={"商品ID": "主键", "商品单价": "数值", "购买数量": "数值", "商品成本": "数值"},
    optional={"商品类目": "无序", "类目ID": "无序", "类目编码": "无序", "品牌": "无序",
              "商品规格": "无序", "库存": "数值", "原价": "数值", "运费": "数值"},
    feature_fn=_build_sku_seg,
    feature_labels={
        "商品单价": {"高": "高单价", "低": "低单价"},
        "购买数量": {"高": "高销量", "低": "低销量"},
        "毛利率": {"高": "高毛利", "低": "低毛利"},
        "销售额": {"高": "高销售额", "低": "低销售额"},
        "库存": {"高": "高库存", "低": "低库存"},
        "原价": {"高": "高原价", "低": "低原价"},
        "运费": {"高": "高运费", "低": "低运费"},
    },
    scatter=["商品单价", "购买数量"], name_features=["商品单价", "购买数量", "毛利率"], entity_word="品",
    feature_display={"商品单价": "商品单价(元)", "购买数量": "购买数量(件)", "毛利率": "毛利率(%)"},
    feature_polarity={"商品单价": True, "购买数量": True, "毛利率": True},
)

GEO_SEG_CONFIG = KMeansModuleConfig(
    name="geo_seg", display_name="地域聚类",
    description="按省份聚合的 ARPU、客单价、订单密度等特征做地域聚类",
    primary_key="用户ID", group_by="省份",
    core={"省份": "无序", "用户ID": "主键", "订单实付金额": "数值"},
    optional={"城市": "无序", "邮编": "无序", "运费": "数值", "商品类目": "无序",
              "订单ID": "主键"},
    feature_fn=_build_geo_seg,
    feature_labels={
        "地域ARPU": {"高": "高价值", "低": "低价值"},
        "地域客单价": {"高": "高客单", "低": "低客单"},
        "地域订单密度": {"高": "高频购", "低": "低频购"},
        "运费": {"高": "高运费", "低": "低运费"},
    },
    scatter=["地域ARPU", "地域订单密度"], name_features=["地域ARPU", "地域客单价", "地域订单密度"],
    entity_word="省", min_group_n=MIN_GROUP_N,
    feature_display={"地域ARPU": "地域ARPU(元)", "地域客单价": "地域客单价(元)", "地域订单密度": "地域订单密度(次)"},
    feature_polarity={"地域ARPU": True, "地域客单价": True, "地域订单密度": True},
)

ACTIVITY_SEG_CONFIG = KMeansModuleConfig(
    name="activity_seg", display_name="活跃行为聚类",
    description="按活跃频次、停留时长、时段分布等行为特征对用户做活跃度分层",
    primary_key="用户ID", group_by="用户ID",
    core={"用户ID": "主键", "事件时间": "日期", "行为类型": "无序"},
    optional={"在站时长": "数值", "浏览页面数": "数值", "访问次数": "数值",
              "设备类型": "无序", "会话开始时间": "日期", "平台": "无序", "流量来源": "无序"},
    feature_fn=_build_activity_seg,
    feature_labels={
        "日活频次": {"高": "高频", "低": "低频"},
        "在站时长": {"高": "长停留", "低": "短停留"},
        "浏览页面数": {"高": "多浏览", "低": "少浏览"},
        "访问次数": {"高": "高访问", "低": "低访问"},
        "会话时长": {"高": "长会话", "低": "短会话"},
        "行为漏斗转化比": {"高": "高转化", "低": "低转化"},
    },
    scatter=["日活频次", "在站时长"], name_features=["日活频次", "在站时长", "访问次数"],
    entity_word="户",
    feature_display={"日活频次": "日活频次(次)", "在站时长": "在站时长(分钟)", "访问次数": "访问次数(次)"},
    feature_polarity={"日活频次": True, "在站时长": True, "访问次数": True},
)

CATEGORY_SEG_CONFIG = KMeansModuleConfig(
    name="category_seg", display_name="类目偏好聚类",
    description="按购买数量、跨类目广度、类目消费占比等做用户类目偏好聚类",
    primary_key="用户ID", group_by="用户ID",
    core={"用户ID": "主键", "商品类目": "无序", "购买数量": "数值"},
    optional={"类目ID": "无序", "品牌": "无序", "商品ID": "主键", "折扣金额": "数值",
              "商品单价": "数值", "订单时间": "日期"},
    feature_fn=_build_category_seg,
    feature_labels={
        "购买数量": {"高": "高购买", "低": "低购买"},
        "跨类目广度": {"高": "多类目", "低": "单一类目"},
        "最近购买间隔": {"高": "久未购", "低": "近期购"},
        "折扣金额": {"高": "高折扣", "低": "低折扣"},
        "商品单价": {"高": "高单价", "低": "低单价"},
    },
    scatter=["购买数量", "跨类目广度"], name_features=["购买数量", "跨类目广度"], entity_word="客",
    feature_display={"购买数量": "购买数量(件)", "跨类目广度": "跨类目广度(类)"},
    feature_polarity={"购买数量": True, "跨类目广度": True},
)

CHURN_SEG_CONFIG = KMeansModuleConfig(
    name="churn_seg", display_name="流失风险聚类",
    description="按静默天数、历史消费、投诉率等做用户流失风险分层",
    primary_key="用户ID", group_by="用户ID",
    core={"用户ID": "主键", "最后活跃时间": "日期", "订单时间": "日期"},
    optional={"注册日期": "日期", "订单实付金额": "数值", "订单ID": "主键", "退订状态": "无序",
              "客诉次数": "数值", "注销时间": "日期", "退款金额": "数值"},
    feature_fn=_build_churn_seg,
    feature_labels={
        "静默天数": {"高": "久未活跃", "低": "近期活跃"},
        "历史消费": {"高": "高历史消费", "低": "低历史消费"},
        "投诉率": {"高": "高投诉", "低": "低投诉"},
        "最近购买": {"高": "久未购", "低": "近期购"},
        "客户年限": {"高": "老客", "低": "新客"},
        "客诉次数": {"高": "多投诉", "低": "少投诉"},
        "退款金额": {"高": "高退款", "低": "低退款"},
    },
    scatter=["静默天数", "历史消费"], name_features=["静默天数", "历史消费", "投诉率"], entity_word="客",
    feature_display={"静默天数": "静默天数(天)", "历史消费": "历史消费(元)", "投诉率": "投诉率(%)"},
    feature_polarity={"静默天数": False, "历史消费": True, "投诉率": False},
)


# ============================================================
# 5 个独立模型（USER_SEG 不注册，仅作 RFM 降级函数）
# ============================================================
class _KMeansBase(AnalysisModel):
    cfg: KMeansModuleConfig

    def can_run(self, df: pd.DataFrame) -> bool:
        norm = _normalize_columns(df)
        return bool(set(self.cfg.core).issubset(norm.columns))

    def compute(self, df: pd.DataFrame) -> AnalysisPackage:
        return run_kmeans(df, self.cfg)


class SkuSegModel(_KMeansBase):
    name = "sku_seg"
    display_name = "商品聚类(SKU)"
    description = "按价格/销量/毛利对商品聚类"
    cfg = SKU_SEG_CONFIG
    required_columns = list(SKU_SEG_CONFIG.core.keys())


class GeoSegModel(_KMeansBase):
    name = "geo_seg"
    display_name = "地域聚类(GEO)"
    description = "按省份聚合特征做地域聚类"
    cfg = GEO_SEG_CONFIG
    required_columns = list(GEO_SEG_CONFIG.core.keys())


class ActivitySegModel(_KMeansBase):
    name = "activity_seg"
    display_name = "活跃行为聚类"
    description = "按行为特征做活跃度分层"
    cfg = ACTIVITY_SEG_CONFIG
    required_columns = list(ACTIVITY_SEG_CONFIG.core.keys())


class CategorySegModel(_KMeansBase):
    name = "category_seg"
    display_name = "类目偏好聚类"
    description = "按类目偏好做用户聚类"
    cfg = CATEGORY_SEG_CONFIG
    required_columns = list(CATEGORY_SEG_CONFIG.core.keys())


class ChurnSegModel(_KMeansBase):
    name = "churn_seg"
    display_name = "流失风险聚类"
    description = "按流失风险特征做用户聚类"
    cfg = CHURN_SEG_CONFIG
    required_columns = list(CHURN_SEG_CONFIG.core.keys())


def _register():
    from src.analysis_engine.registry import register_model
    register_model(SkuSegModel())
    register_model(GeoSegModel())
    register_model(ActivitySegModel())
    register_model(CategorySegModel())
    register_model(ChurnSegModel())


_register()
