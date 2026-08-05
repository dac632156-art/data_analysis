"""#4 回归测试 — rfm._bin_score 确定性（锁定 #11 修复）

#11 将分箱 rank 从 method="first" 改为 method="average"，
消除：
1. 相同 R/F/M 值的客户被伪排序打进不同档（ties 必须共享同一分）；
2. 结果对输入行序的依赖（nondeterministic）。
本测试锁定该行为，防止回退。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from src.analysis_engine.models.rfm import _bin_score


def test_bin_score_in_range():
    s = pd.Series([10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
    out = _bin_score(s, ascending=True, q=5)
    assert set(out.unique()).issubset({1, 2, 3, 4, 5})


def test_bin_score_deterministic_same_input():
    s = pd.Series([10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
    assert _bin_score(s, ascending=True, q=5).equals(_bin_score(s, ascending=True, q=5))


def test_bin_score_ties_share_rank():
    # 三个相同值 5 必须得到完全相同的分（method="average"），而非伪排序
    s = pd.Series([5, 5, 5, 10, 10, 20])
    out = _bin_score(s, ascending=True, q=5)
    assert out[0] == out[1] == out[2]


def test_bin_score_order_invariant():
    # #11 关键：结果不得依赖输入行序（仅由值多集合决定）
    base = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5]
    s_ordered = pd.Series(base)
    s_shuffled = pd.Series(base).sample(frac=1, random_state=42).reset_index(drop=True)
    out_ordered = _bin_score(s_ordered, ascending=True, q=5)
    out_shuffled = _bin_score(s_shuffled, ascending=True, q=5)
    # 分的多集合只取决于值，与顺序无关
    assert sorted(out_ordered.tolist()) == sorted(out_shuffled.tolist())
