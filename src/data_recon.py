"""
数据侦察模块：上传后自动扫描 df 结构，产出结构化快照（列名/类型/缺失值/数值统计/行数）。

用途：
1) 上传链路（upload.py）调用 scan() 生成侦察结果存 session，后续对话不必重复算。
2) LLM 工具 get_data_profile 直接返回该快照，无需每次重扫。

本模块为确定性规则（非 LLM），纯 pandas，便于单测与复用。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

import numpy as np
import pandas as pd

_logger = logging.getLogger("data_recon")


def _infer_kind(series: pd.Series) -> str:
    """粗略推断某列的语义类型（业务视角）。"""
    if pd.api.types.is_datetime64_any_dtype(series):
        return "日期时间"
    if pd.api.types.is_numeric_dtype(series):
        # 整数且基数低 → 可能类别/ID
        uniq_ratio = series.nunique(dropna=True) / max(len(series.dropna()), 1)
        if uniq_ratio < 0.05 and series.nunique(dropna=True) <= 20:
            return "类别(整数)"
        return "数值"
    # 文本列
    uniq = series.nunique(dropna=True)
    if uniq <= 30:
        return "类别(文本)"
    return "文本"


def scan(df: pd.DataFrame) -> Dict[str, Any]:
    """扫描 df，返回结构化侦察快照。

    返回字段：
    {
        "rows": int,
        "columns": [str, ...],
        "column_count": int,
        "missing_overview": {"total_missing": int, "cols_with_missing": int},
        "columns_detail": [
            {
                "name": str,
                "dtype": str,
                "kind": str,                 # 数值 / 类别 / 文本 / 日期时间
                "missing": int,
                "missing_pct": float,
                "non_null": int,
                "unique": int,
                "stats": {                   # 数值列才有
                    "min": float, "max": float,
                    "mean": float, "median": float,
                    "std": float,
                },
                "sample_values": [Any, ...],  # 前 3 个非空样本（用于 LLM 理解语义）
            }, ...
        ],
    }
    """
    if df is None or not isinstance(df, pd.DataFrame):
        return {"rows": 0, "columns": [], "column_count": 0,
                "missing_overview": {"total_missing": 0, "cols_with_missing": 0},
                "columns_detail": []}
    if df.empty:
        return {"rows": 0, "columns": list(df.columns), "column_count": len(df.columns),
                "missing_overview": {"total_missing": 0, "cols_with_missing": 0},
                "columns_detail": []}

    total_missing = 0
    cols_with_missing = 0
    columns_detail: List[Dict[str, Any]] = []

    for col in df.columns:
        series = df[col]
        missing = int(series.isna().sum())
        total_missing += missing
        if missing > 0:
            cols_with_missing += 1
        non_null = int(series.notna().sum())
        unique = int(series.nunique(dropna=True))
        missing_pct = round(missing / max(len(series), 1) * 100, 2)
        kind = _infer_kind(series)

        detail: Dict[str, Any] = {
            "name": str(col),
            "dtype": str(series.dtype),
            "kind": kind,
            "missing": missing,
            "missing_pct": missing_pct,
            "non_null": non_null,
            "unique": unique,
        }

        # 数值统计
        if pd.api.types.is_numeric_dtype(series):
            try:
                detail["stats"] = {
                    "min": _round(series.min()),
                    "max": _round(series.max()),
                    "mean": _round(series.mean()),
                    "median": _round(series.median()),
                    "std": _round(series.std()),
                }
            except Exception:
                detail["stats"] = {}

        # 样本值（前 3 个非空，转成可序列化）
        samples = series.dropna().head(3).tolist()
        detail["sample_values"] = [_to_jsonable(v) for v in samples]

        columns_detail.append(detail)

    return {
        "rows": int(len(df)),
        "columns": [str(c) for c in df.columns],
        "column_count": len(df.columns),
        "missing_overview": {
            "total_missing": total_missing,
            "cols_with_missing": cols_with_missing,
        },
        "columns_detail": columns_detail,
    }


def _round(v: Any):
    try:
        if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
            return None
        if isinstance(v, (int, float, np.integer, np.floating)):
            return round(float(v), 4)
    except Exception:
        return None
    return _to_jsonable(v)


def _to_jsonable(v: Any):
    try:
        if v is None:
            return None
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating,)):
            f = float(v)
            return None if (np.isnan(f) or np.isinf(f)) else round(f, 4)
        if isinstance(v, (pd.Timestamp,)):
            return v.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
            return None
        return v
    except Exception:
        return str(v)
