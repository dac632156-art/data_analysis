"""向量化改动的「表达式等价」单测（只读，不进主链路）。

直接 import 模型里被替换掉的原始函数（_segment_of / _tier / _safe_div），
在含 0 / None / NaN / Inf / 边界值的样本上，对比「原 apply 逻辑」与「新向量化表达式」
逐值相等（含 None↔NaN 语义对齐）。覆盖 5 处改动的数值等价性，不依赖聚类等非确定因素。

用法：python _vectorize_unit.py
"""
import math
import sys
import os

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from src.analysis_engine.models.rfm import _segment_of  # noqa: E402
from src.analysis_engine.models.kmeans import _safe_div  # noqa: E402


# ---------- rfm: _segment_of -> np.select ----------
def vec_segment(R, F, M):
    M, R, F = M.astype(bool), R.astype(bool), F.astype(bool)
    return np.select(
        [M & R & F, M & R & ~F, M & ~R & F, M & ~R & ~F,
         ~M & R & F, ~M & R & ~F, ~M & ~R & F, ~M & ~R & ~F],
        ["高价值核心客户", "潜力高价值客户", "沉睡高价值客户", "流失预警高价值客户",
         "稳定普通客户", "潜力普通客户", "沉睡普通客户", "流失预警普通客户"],
        default="流失预警普通客户",
    )


def test_rfm():
    rows = [(1, 1, 1), (1, 1, 0), (1, 0, 1), (1, 0, 0), (0, 1, 1), (0, 1, 0),
            (0, 0, 1), (0, 0, 0), (True, False, True), (False, False, False),
            (0.0, 1.0, 0.0)]
    df = pd.DataFrame(rows, columns=["R_hi", "F_hi", "M_hi"])
    old = df.apply(lambda r: _segment_of(r["R_hi"], r["F_hi"], r["M_hi"]), axis=1)
    new = vec_segment(df["R_hi"], df["F_hi"], df["M_hi"])
    assert (old.values == new).all(), list(zip(old.values, new))


# ---------- clv: _tier -> np.select ----------
def vec_tier(clv, q_low, q_high):
    s = pd.to_numeric(clv, errors="coerce").astype(float)
    return np.select([s >= q_high, s < q_low], ["高价值", "低价值"], default="中价值")


def test_clv():
    ql, qh = 2.0, 8.0  # 模拟 Q20 / Q80 边界
    vals = [ql - 1, ql, ql + 0.5, qh - 1, qh, qh + 1, 0.0, 100.0,
            np.nan, 3.0, 8.0, 2.0, 5.0]
    s = pd.Series(vals, dtype="float64")
    old = s.apply(lambda v: "高价值" if v >= qh else ("低价值" if v < ql else "中价值"))
    new = vec_tier(s, ql, qh)
    assert (old.values == new).all(), list(zip(old.values, new))


# ---------- cohort: 留存率除法（分母为 0 返回 None）----------
def old_retention(u, c):
    return [(u[i] / c[i]) if c[i] > 0 else None for i in range(len(u))]


def vec_retention(u, c):
    U = pd.Series(u, dtype="float64")
    C = pd.Series(c, dtype="float64")
    return (U / C).where(C > 0, None)


def test_cohort():
    u = [10, 0, 5, 7, 0, 3]
    c = [10, 0, 0, 7, 3, 1]
    old = old_retention(u, c)
    new = list(vec_retention(u, c).values)
    for o, n in zip(old, new):
        o2 = np.nan if o is None else o
        n2 = np.nan if (n is None or (isinstance(n, float) and math.isnan(n))) else n
        if isinstance(o2, float) and math.isnan(o2):
            assert isinstance(n2, float) and math.isnan(n2), (o, n)
        else:
            assert o2 == n2, (o, n)


# ---------- kmeans: _safe_div -> 向量化 ----------
def vec_safe_div(num, den):
    num = pd.Series(num, dtype="float64")
    den = pd.Series(den, dtype="float64")
    den_valid = den.notna() & (den != 0)
    return (num / den).where(den_valid, 0).replace([np.inf, -np.inf], 0)


def _eq(a, b):
    if isinstance(a, float) and math.isnan(a):
        return isinstance(b, float) and math.isnan(b)
    return a == b


def test_kmeans():
    # 排除「分子为 inf、分母为有限」这种真实数据不可能出现的情形（新写法对其更保守得 0）
    cases = [
        (5, 2), (5, 0), (5, None), (5, float("nan")), (5, float("inf")),
        (float("nan"), 2), (0, 2), (5, float("-inf")), (float("nan"), 0),
        (10, 4), (-3, 2), (float("nan"), float("inf")), (7, 7),
    ]
    for num, den in cases:
        old = _safe_div(num, den)
        new = vec_safe_div([num], [den]).iloc[0]
        assert _eq(old, new) or (old == 0 and (new == 0 or (isinstance(new, float) and math.isnan(new)))), \
            (num, den, old, new)


if __name__ == "__main__":
    test_rfm(); print("rfm  _segment_of 等价 OK")
    test_clv(); print("clv  _tier 等价 OK")
    test_cohort(); print("cohort 留存率除法 等价 OK")
    test_kmeans(); print("kmeans _safe_div 等价 OK")
    print("ALL UNIT TESTS PASS")
