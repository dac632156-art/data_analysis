"""
多表关联合并：在 process-datasets 流水线中（数据清洗之后、列名映射之前）自动研判
多张已清洗数据集之间是否存在关联键，能合则 inner join 合成一张宽表。

识别策略（混合评分制）：
1. 同名前置：两表须存在归一化后同名列（按原始列名判断，此刻尚未做列名映射）。
2. 主键侧闸门：候选键在「至少一侧」的「去重比例 = 去重值数 ÷ 行数」须 ≥ KEY_THRESHOLD(0.8)
   且去重值数 ≥ 2。这允许典型的事实表外键（如订单表 user_id 大量重复、比例低）与其
   维度表主键（用户表 user_id 比例≈1.0，是键）成功合并；同时挡掉两表都只共享
   低基数类别列（地区/状态/月份，两侧都不是键）的误合并。
3. 重叠率闸门：|A∩B| / min(|A|,|B|) ≥ 0.5 才算关联键（确认两表引用同一批实体）。
4. 名字加分：列名像 id/key/编号/编码/码/uuid 的优先选为键；
   反之度量列（金额/价格/数量/…）绝不作为关联键（直接排除）。

连接类型：固定 inner join（只保留两表都能匹配的行）。
N≥2 张表：建图取连通分量，分量内从行数最多的表出发贪心链式 inner 合并；
连不上的表各自独立。
安全降级：无关联键 / inner 合并后 0 行 / 合并异常 → 退化为原多表分别分析。

本模块为确定性规则（非 LLM），与列名映射模块平级，便于单测与复用。
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

from src.mapping.column_mapper import coordinate_map_component

_logger = logging.getLogger("dataset_merger")

# 主键名识别：含这些 token 的列名优先当关联键（加分）
_KEY_TOKENS = ["id", "key", "编号", "编码", "码", "uuid", "userid", "user_id", "no", "num", "号", "order"]

# 度量列识别：含这些 token 的列名绝不作为关联键（金额/价格/数量等）
_MEASURE_TOKENS = [
    "金额", "价格", "单价", "总价", "总额", "cost", "price", "amount", "total",
    "数量", "销量", "qty", "quant", "sales", "利润", "profit", "value", "值",
    "体重", "身高", "温度", "score", "分数", "gdp", "收入", "income",
]

# 主键侧阈值：某侧去重比例 ≥ 该值即视为「主键/唯一键」侧，允许与另一侧合并。
# 事实表外键通常大量重复（比例低），维度表主键比例≈1.0，故用此区分真实关联键
# 与双方都是低基数的类别列。
_KEY_THRESHOLD = 0.8


@dataclass
class AnalysisUnit:
    """一个分析单元：宽表(merged) 或 单表(single)。"""
    kind: str                                   # 'merged' | 'single'
    dataset_id: Optional[str] = None            # single 用
    df: Optional[pd.DataFrame] = None           # merged 用，注册前持有
    sources: List[str] = field(default_factory=list)   # 来源 dataset_id 列表（merged）
    keys: List[str] = field(default_factory=list)       # 实际使用的关联键列名（merged）
    file_name: str = ""


def _norm(col) -> str:
    """列名归一化：转小写、去空白、去常见分隔符，用于同名判断。"""
    if col is None:
        return ""
    s = str(col).strip().lower()
    s = re.sub(r"[\s_\-./]+", "", s)
    return s


def _is_key_like(name: str) -> bool:
    n = _norm(name)
    return any(tok in n for tok in _KEY_TOKENS)


def _is_measure_like(name: str) -> bool:
    n = _norm(name)
    return any(tok in n for tok in _MEASURE_TOKENS)


def _cardinality_ratio(series: pd.Series) -> Tuple[int, float]:
    """返回 (去重值数, 去重比例)。基于 dropna 后的唯一值。"""
    s = series.dropna()
    n = len(s)
    if n == 0:
        return 0, 0.0
    uniq = int(s.nunique())
    return uniq, float(uniq) / float(n)


def _overlap_ratio(a_vals: Set, b_vals: Set) -> float:
    """重叠率 = |A∩B| / min(|A|, |B|)。"""
    if not a_vals or not b_vals:
        return 0.0
    inter = len(a_vals & b_vals)
    denom = min(len(a_vals), len(b_vals))
    if denom == 0:
        return 0.0
    return inter / denom


def _candidate_keys(dfa: pd.DataFrame, dfb: pd.DataFrame) -> List[Tuple[str, str, float]]:
    """找 a、b 两表的关联键。返回 [(a_col, b_col, score), ...] 按 score 降序。

    通过条件：同名前置 + 主键侧闸门(至少一侧去重比例≥KEY_THRESHOLD 且去重值≥2)
    + 重叠率闸门(≥0.5) + 度量列排除。
    score 含主键名加分；度量列直接排除（绝不参与）。
    """
    norm_to_a: Dict[str, str] = {}
    for c in dfa.columns:
        norm_to_a.setdefault(_norm(c), c)   # 同归一名取首个
    norm_to_b: Dict[str, str] = {}
    for c in dfb.columns:
        norm_to_b.setdefault(_norm(c), c)

    results = []
    considered = set()
    for norma, acol in norm_to_a.items():
        if norma not in norm_to_b:
            continue
        bcol = norm_to_b[norma]
        pair_key = (acol, bcol)
        if pair_key in considered:
            continue
        considered.add(pair_key)

        # 度量列绝不作为关联键（金额/价格/数量等）
        if _is_measure_like(acol) or _is_measure_like(bcol):
            continue

        # 主键侧闸门：至少一侧去重比例≥KEY_THRESHOLD（即该侧是主键/唯一键）；
        # 允许事实表外键大量重复（比例低），只要维度表主键唯一即可合并。
        # 两表都只共享低基数类别列（两侧都不是键）→ 不合并。
        a_uniq, a_ratio = _cardinality_ratio(dfa[acol])
        b_uniq, b_ratio = _cardinality_ratio(dfb[bcol])
        if min(a_uniq, b_uniq) < 2:
            continue
        a_is_key = a_ratio >= _KEY_THRESHOLD
        b_is_key = b_ratio >= _KEY_THRESHOLD
        if not (a_is_key or b_is_key):
            continue

        # 重叠率闸门
        a_set = set(dfa[acol].dropna().astype(str).tolist())
        b_set = set(dfb[bcol].dropna().astype(str).tolist())
        if not a_set or not b_set:
            continue
        ov = _overlap_ratio(a_set, b_set)
        if ov < 0.5:
            continue

        # 评分：重叠率为主，主键名加分
        score = ov
        if _is_key_like(acol) or _is_key_like(bcol):
            score += 0.5
        results.append((acol, bcol, score))

    results.sort(key=lambda x: x[2], reverse=True)
    return results


def _component_join_cols(edges: List[Tuple[int, int, str, str, float]],
                        idxs: List[int], n: int) -> List[str]:
    """取某连通分量内所有关联键列名（用于排除协同重命名）。"""
    idx_set = set(idxs)
    cols: List[str] = []
    for (i, j, a_col, b_col, _score) in edges:
        if i in idx_set and j in idx_set:
            cols.append(a_col)
            cols.append(b_col)
    seen: Set[str] = set()
    out: List[str] = []
    for c in cols:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _merge_two(dfa: pd.DataFrame, dfb: pd.DataFrame,
                a_col: str, b_col: str) -> Optional[pd.DataFrame]:
    """按 (a_col, b_col) inner join 两表。非键同名列由 pandas 自动加 _x/_y 区分。

    返回合并后 df；0 行或异常返回 None。
    键列处理：删除右表关联键列（inner 后恒等于左表关联键，冗余），
    左表关联键若被加后缀 _x 则还原为原名，便于后续链式合并的键名匹配。
    """
    try:
        merged = pd.merge(
            dfa, dfb,
            left_on=a_col, right_on=b_col,
            how="inner",
            suffixes=("_x", "_y"),
        )
    except Exception:
        return None
    if merged is None or len(merged) == 0:
        return None
    # 删除右表关联键列（inner 后恒等于左表关联键，冗余）
    if a_col == b_col:
        # 同名合并：两列变为 a_col_x / a_col_y，删右(y)、左还原为原名
        right_key = a_col + "_y"
        left_key = a_col + "_x"
        if right_key in merged.columns:
            merged = merged.drop(columns=[right_key])
        if left_key in merged.columns and a_col not in merged.columns:
            merged = merged.rename(columns={left_key: a_col})
    else:
        # 异名合并：右键若与左表其它列碰撞则加 _y，否则原名
        right_key = b_col + "_y" if b_col in dfa.columns else b_col
        if right_key in merged.columns:
            merged = merged.drop(columns=[right_key])
    return merged


def _greedy_merge_component(tables: List[Tuple[str, pd.DataFrame]]) -> Tuple[Optional[pd.DataFrame], List[str], List[str]]:
    """对同一个连通分量内的表做贪心链式 inner 合并。

    返回 (合并后 df 或 None, 来源 did 列表, 关联键人类可读名列表)。
    若无法合并（0 行 / 无键）返回 (None, [], [])。
    """
    if len(tables) <= 1:
        return None, [], []
    # 按行数降序，最大的作初始累加器
    ordered = sorted(tables, key=lambda x: len(x[1]), reverse=True)
    acc_did, acc_df = ordered[0]
    acc_sources = [acc_did]
    keys_used: List[str] = []
    merged_set = {acc_did}
    changed = True
    while changed:
        changed = False
        for did_k, df_k in ordered[1:]:
            if did_k in merged_set:
                continue
            cands = _candidate_keys(acc_df, df_k)
            if not cands:
                continue
            a_col, b_col, _score = cands[0]
            new_df = _merge_two(acc_df, df_k, a_col, b_col)
            if new_df is None or len(new_df) == 0:
                continue
            # 合并后存活的键列名恒为左侧累加器列 a_col（右表键列在 _merge_two
            # 中被丢弃或加 _y 后缀），故关联键名记录 a_col，保证 UI 徽标准确。
            key_name = a_col
            if key_name not in keys_used:
                keys_used.append(key_name)
            acc_df = new_df
            acc_sources.append(did_k)
            merged_set.add(did_k)
            changed = True
            break  # 累加器已变，重启扫描以正确处理传递链
    if len(acc_sources) > 1:
        return acc_df, acc_sources, keys_used
    return None, [], []


def build_analysis_units(
    datasets: List[Tuple[str, pd.DataFrame]],
    file_names: Optional[Dict[str, str]] = None,
    llm_cfg: Optional[dict] = None,
) -> List[AnalysisUnit]:
    """载入各表 df，识别关联键建图取连通分量，分量内链式 inner 合并。

    入参 datasets: [(dataset_id, df), ...]。
    返回分析单元列表（每连通分量一张宽表 + 每个孤立表一张单表）。

    安全降级：无效 df / 仅单表 / 合并异常 → 退化为原多表单表单元。
    """
    file_names = file_names or {}
    valid = [
        (did, df) for did, df in datasets
        if df is not None and not df.empty and len(df.columns) > 0
    ]
    if len(valid) == 0:
        return []
    if len(valid) == 1:
        did = valid[0][0]
        return [AnalysisUnit(kind="single", dataset_id=did, file_name=file_names.get(did, did))]

    n = len(valid)
    # 1) 两两识别关联键建边
    edges: List[Tuple[int, int, str, str, float]] = []
    for i in range(n):
        for j in range(i + 1, n):
            cands = _candidate_keys(valid[i][1], valid[j][1])
            if cands:
                a_col, b_col, score = cands[0]
                edges.append((i, j, a_col, b_col, score))

    # 2) 连通分量（并查集）
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for (i, j, _, _, _) in edges:
        union(i, j)
    comps: Dict[int, List[int]] = {}
    for idx in range(n):
        comps.setdefault(find(idx), []).append(idx)

    units: List[AnalysisUnit] = []
    # 3) 每个分量贪心链式合并
    for _root, idxs in comps.items():
        if len(idxs) == 1:
            did = valid[idxs[0]][0]
            units.append(AnalysisUnit(kind="single", dataset_id=did, file_name=file_names.get(did, did)))
            continue
        tables = [valid[k] for k in idxs]
        # ---- 合表前跨表协同映射（A+B）：对分量内非关联键列做全局消歧重命名 ----
        if llm_cfg and llm_cfg.get("api_key"):
            try:
                join_cols = _component_join_cols(edges, idxs, n)
                remap = coordinate_map_component(tables, join_cols, file_names, llm_cfg)
                if remap:
                    renamed = []
                    for did, df in tables:
                        mp = remap.get(did)
                        if mp:
                            df = df.rename(columns={
                                r: s for r, s in mp.items() if r in df.columns
                            })
                        renamed.append((did, df))
                    tables = renamed
            except Exception as e:
                _logger.warning("跨表协同映射失败，降级为 pandas _x/_y：%s", e)
        merged_df, sources, keys = _greedy_merge_component(tables)
        if merged_df is None:
            # 连通分量内一张都没合进来（边都被 0 行过滤）→ 各自单表
            for k in idxs:
                did = valid[k][0]
                units.append(AnalysisUnit(kind="single", dataset_id=did, file_name=file_names.get(did, did)))
            continue
        units.append(AnalysisUnit(
            kind="merged",
            df=merged_df,
            sources=sources,
            keys=keys,
            file_name=f"合并宽表（{len(sources)}张表）",
        ))
    return units
