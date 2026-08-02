"""
全项目唯一 JSON 序列化安全层。

所有 API 返回前必须调用 sanitize_json(result)，确保：
- NaN / inf → None（JSON null）
- numpy.float64/32 → float（含 inf/nan 检查）
- numpy.int64/32 → int
- numpy.bool_ → bool
- numpy.ndarray → list（递归清理元素）
- pd.Timestamp / datetime → ISO 字符串
- Decimal → float
- dict / list / tuple → 递归清理所有元素

使用方式：
    from src.utils.json_serializer import sanitize_json
    return sanitize_json(result)
"""

import math
import datetime
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd


def sanitize_json(obj: Any) -> Any:
    """递归清理所有非 JSON 安全类型，转换为 JSON 兼容对象。

    覆盖规则：
    - NaN / inf → None
    - numpy float → Python float（含 inf/nan 检查）
    - numpy integer → Python int
    - numpy bool_ → Python bool
    - numpy ndarray → list（递归清理元素）
    - pd.Timestamp / datetime → ISO 字符串
    - Decimal → float
    - dict → 递归清理所有 value
    - list / tuple → 递归清理所有元素
    - 其他类型 → 原样返回（str, int, float, bool, None 等原生 JSON 类型）
    """
    # None — JSON null，直接返回
    if obj is None:
        return None

    # Python float — 检查 inf/nan
    if isinstance(obj, float):
        if math.isinf(obj) or math.isnan(obj):
            return None
        return obj

    # Python int, str, bool — 原生 JSON 类型，直接返回
    if isinstance(obj, (int, str, bool)):
        return obj

    # numpy 类型
    if isinstance(obj, np.floating):
        val = float(obj)
        if math.isinf(val) or math.isnan(val):
            return None
        return val

    if isinstance(obj, np.integer):
        return int(obj)

    if isinstance(obj, np.bool_):
        return bool(obj)

    if isinstance(obj, np.ndarray):
        return [sanitize_json(item) for item in obj.tolist()]

    # pandas Timestamp
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()

    # datetime 类型
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()

    # Decimal
    if isinstance(obj, Decimal):
        return float(obj)

    # dict — 递归清理所有 value
    if isinstance(obj, dict):
        return {k: sanitize_json(v) for k, v in obj.items()}

    # list / tuple — 递归清理所有元素，tuple 转 list
    if isinstance(obj, (list, tuple)):
        return [sanitize_json(item) for item in obj]

    # set / frozenset → list（递归清理元素）
    if isinstance(obj, (set, frozenset)):
        return [sanitize_json(item) for item in obj]

    # bytes / bytearray → utf-8 解码（失败兜底转 str）
    if isinstance(obj, (bytes, bytearray)):
        try:
            return obj.decode("utf-8", errors="replace")
        except Exception:
            try:
                return str(obj)
            except Exception:
                return None

    # 其他未知类型 — 安全降级为字符串，杜绝 FastAPI 序列化 500
    try:
        return str(obj)
    except Exception:
        return None
