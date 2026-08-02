"""向量化改写前后差分对账脚本（只读，不进主链路）。

原理：
- 用当前代码（改写前或改写后均可）跑完整服务器链路（column_mapper -> run_df_to_packages），
  把每个 AnalysisPackage 过 sanitize_json 后 dump 成 JSON。
- 覆盖两部分输入：
  (A) 「数据测试集」下所有 CSV（真实数据，额外覆盖 rfm/clv/kmeans）；
  (B) 一份「标准列名 + 日期合法」的合成数据帧，确保 cohort 也能跑通（规避改动前已有的
      Cohort_Month NaN 崩溃），从而 4 个目标模型全部纳入对账。
- KMeans 已用固定 random_state=42，RFM/CLV/cohort 均为确定性计算，故同一份代码两次运行
  产生的包 JSON 逐字段一致；任何不一致即代表「计算逻辑/输出被改变」→ 视为引入 bug。

用法：
    python _vectorize_audit.py baseline   # 用当前代码 dump 基线到 _vectorize_baseline.json
    python _vectorize_audit.py check      # 重新跑并与基线逐字段 diff，不一致则非零退出
"""
import os
import sys
import json
import glob

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from src.mapping.column_mapper import map_dataset_columns  # noqa: E402
from backend.routers._analysis_pipeline import run_df_to_packages  # noqa: E402
from src.utils.json_serializer import sanitize_json  # noqa: E402

BASELINE = os.path.join(BASE, "_vectorize_baseline.json")
DATA_DIR = os.path.join(BASE, "数据测试集")

# 这些模型本身输出不确定（聚类随机 / 采样等），与本次改动无关，且不在修改范围 → 全包 diff 排除。
# 其中 sku_seg 的「毛利率」改动由 _vectorize_unit.py 单独做表达式等价验证。
DENY_MODELS = {"category_seg", "user_profile", "activity_seg", "churn_seg", "sku_seg"}


def _pkg_id(key):
    return key.split("::", 1)[1] if "::" in key else key


def _filter(bundles):
    return {k: v for k, v in bundles.items() if _pkg_id(k) not in DENY_MODELS}


def _run(df, tag):
    """对一份 df 跑全链路，返回 {f'{tag}::{pkgid}': sanitized_pkg}。失败记为 _error（确定性）。"""
    out = {}
    try:
        mapped = map_dataset_columns("audit", None, df, {})
    except Exception as e:
        out[tag] = {"_error": f"map:{e}"}
        return out
    try:
        pkgs, _ = run_df_to_packages(mapped)
    except Exception as e:
        out[tag] = {"_error": f"run:{e}"}
        return out
    for p in pkgs:
        out[f"{tag}::{p.get('id')}"] = sanitize_json(p)
    return out


def _synthetic_df():
    """标准列名、日期合法的合成数据，触发 rfm/clv/cohort/kmeans(user+sku)。"""
    rng = np.random.default_rng(7)
    n_users = 400
    orders_per = rng.integers(1, 8, size=n_users)
    rows = []
    oid = 0
    cats = ["美妆", "食品", "家居", "服饰", "数码"]
    cities = ["上海", "北京", "广州", "深圳", "成都"]
    genders = ["男", "女"]
    for u in range(n_users):
        uid = f"U{u:05d}"
        n = int(orders_per[u])
        start_month = int(rng.integers(1, 19))  # 2025-01 .. 2026-06
        for _ in range(n):
            m = start_month + int(rng.integers(0, 6))
            year = 2025 + m // 12
            mon = m % 12 + 1
            day = int(rng.integers(1, 28))
            oid += 1
            amount = float(rng.integers(50, 3000))
            cost = amount * float(rng.uniform(0.3, 0.8))
            refund = amount * float(rng.uniform(0, 0.15)) if rng.random() < 0.3 else 0.0
            ship = int(rng.choice([0, 0, 8, 12, 15]))
            sku = f"S{int(rng.integers(0, 60)):04d}"
            price = amount
            qty = int(rng.integers(1, 4))
            rows.append({
                "用户ID": uid,
                "订单ID": f"O{oid:07d}",
                "订单时间": f"{year}-{mon:02d}-{day:02d}",
                "订单实付金额": amount,
                "退款金额": refund,
                "运费": ship,
                "商品ID": sku,
                "商品单价": price,
                "购买数量": qty,
                "商品成本": cost,
                "商品类目": str(rng.choice(cats)),
                "城市": str(rng.choice(cities)),
                "性别": str(rng.choice(genders)),
            })
    return pd.DataFrame(rows)


def collect():
    bundles = {}
    # (A) 真实 CSV
    for path in sorted(glob.glob(os.path.join(DATA_DIR, "**", "*.csv"), recursive=True)):
        name = os.path.relpath(path, DATA_DIR)
        try:
            df = pd.read_csv(path, low_memory=False)
        except Exception as e:
            bundles[name] = {"_error": f"read:{e}"}
            continue
        bundles.update(_run(df, name))
    # (B) 合成帧（保证 cohort 覆盖）
    bundles.update(_run(_synthetic_df(), "synthetic"))
    return bundles


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "baseline":
        bundles = collect()
        with open(BASELINE, "w", encoding="utf-8") as f:
            json.dump(bundles, f, ensure_ascii=False, sort_keys=True, indent=1)
        print(f"[baseline] 已 dump {len(bundles)} 个包 -> {BASELINE}")
        return

    if not os.path.exists(BASELINE):
        print("!!! 未找到基线，请先运行 `python _vectorize_audit.py baseline`")
        sys.exit(2)
    with open(BASELINE, "r", encoding="utf-8") as f:
        base = _filter(json.load(f))
    cur = _filter(collect())

    print(f"[check] 基线 {len(base)} 包 / 当前 {len(cur)} 包")
    errors = []
    for k in sorted(set(base) | set(cur)):
        if k not in base:
            errors.append(f"新增包 {k}")
            continue
        if k not in cur:
            errors.append(f"缺失包 {k}")
            continue
        if base[k] != cur[k]:
            errors.append(f"包 {k} 内容不一致")
    if errors:
        print(f"!!! 对账失败：{len(errors)} 处")
        for e in errors[:60]:
            print("  -", e)
        sys.exit(1)
    print("[check] 全部包逐字段一致 OK")


if __name__ == "__main__":
    main()
