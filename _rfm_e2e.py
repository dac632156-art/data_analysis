"""完整服务器链路验证：映射 -> run_df_to_packages(含图表渲染)。只读。"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import pandas as pd
from src.mapping.column_mapper import map_dataset_columns
from backend.routers._analysis_pipeline import run_df_to_packages

out = []
L = out.append

df = pd.read_csv(os.path.join(BASE, "数据测试集", "测试1.csv"), low_memory=False)
mapped = map_dataset_columns("diag_e2e", None, df, {})
L(f"映射后列: {list(mapped.columns)}")

try:
    pkgs, pkgmap = run_df_to_packages(mapped)
    L(f"\n返回包数: {len(pkgs)}")
    for p in pkgs:
        cd = p.get("chart_data") or []
        kp = p.get("kpis") or []
        L(f"  - id={p.get('id')} can_run={p.get('can_run')} "
           f"charts={len(cd)} kpis={len(kp)}")
        for c in cd:
            opt = c.get("option")
            L(f"      chart[{c.get('chart_type')}] title={c.get('title')!r} "
               f"option_present={bool(opt)} data_items={len(c.get('data') or [])}")
except Exception as e:
    import traceback
    L(f"\n!!! run_df_to_packages 抛异常: {e}")
    L(traceback.format_exc())

with open(os.path.join(BASE, "_rfm_e2e_out.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("\n".join(out))
