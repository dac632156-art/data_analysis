"""临时检查：数据测试集各文件是否能被 RFM 模型直接命中（can_run）。
按 rfm.py 的真实 COLUMN_ALIASES / REQUIRED_COLUMNS 判定；大文件只取表头。"""
import os
import pandas as pd
from src.analysis_engine.models.rfm import _normalize_columns, REQUIRED_COLUMNS

BASE = r"d:\数据分析项目\数据测试集"

FILES = [
    "测试1.csv", "测试2.csv", "测试3.csv", "测试5.csv", "测试7.csv",
    "同期群测试数据.csv", "业务数据.csv",
    r"测试4\orders.csv", r"测试4\order_items.csv", r"测试4\customers.csv",
    r"测试6\olist_orders_dataset.csv", r"测试6\olist_order_items_dataset.csv",
    r"测试6\olist_customers_dataset.csv", r"测试6\olist_order_payments_dataset.csv",
]

def check(path):
    if not os.path.exists(path):
        return f"  [缺失] {path}"
    # 只取表头（大文件不加载全量）
    try:
        df = pd.read_csv(path, nrows=3, low_memory=False)
    except Exception as e:
        return f"  [读取失败] {path}: {e}"
    norm = _normalize_columns(df)
    have = [c for c in REQUIRED_COLUMNS if c in norm.columns]
    ok = set(REQUIRED_COLUMNS).issubset(set(norm.columns))
    # 交易级判定：归一化后有 用户ID 列且存在重复行（多笔订单/事件）
    tx = False
    if "用户ID" in norm.columns:
        tx = norm["用户ID"].astype(str).duplicated().any()
    extra = []
    for canon, keys in {
        "订单ID": ["订单ID", "order_id"],
        "消费次数": ["消费次数", "F"],
        "地域": ["地域", "省份", "城市", "region", "state"],
    }.items():
        if any(k in norm.columns for k in keys):
            extra.append(canon)
    status = "[OK]可触发" if ok else "[NO]不触发"
    note = []
    if ok:
        note.append("交易级->B可用" if tx else "非交易级->B跳过")
        if extra:
            note.append("附:" + "/".join(extra))
    return (f"  {status} | 命中必需要素={have} | "
            f"{' | '.join(note) if note else '（缺:' + '/'.join(set(REQUIRED_COLUMNS)-set(have)) + '）'}")

lines = []
lines.append("===== RFM 命中检查（按 rfm.py 真实别名归一化）=====")
for f in FILES:
    full = os.path.join(BASE, f)
    lines.append(f"\n[{f}]")
    lines.append(check(full))

with open(os.path.join(BASE, "..", "_rfm_check_out.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines))
print("WROTE _rfm_check_out.txt (utf-8)")
