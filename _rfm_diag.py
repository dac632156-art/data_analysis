"""复刻服务器链路诊断：注册模型 -> map_dataset_columns -> run_analysis。
只读，不改任何代码。目标是定位「数据洞察 0 包」根因。
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import pandas as pd

# 1) 复刻服务器 import（触发模型注册，等价于 from src.analysis_engine import run_analysis）
import src.analysis_engine  # noqa: F401  触发 __init__ 内 import models -> register rfm/cohort
from src.analysis_engine.registry import get_models
from src.mapping.column_mapper import map_dataset_columns
from src.analysis_engine import run_analysis

out = []
L = out.append

CSV = os.path.join(BASE, "数据测试集", "测试1.csv")
df = pd.read_csv(CSV, low_memory=False)

L("===== 1) 注册表 =====")
models = get_models()
L(f"已注册模型数: {len(models)} -> {[m.name for m in models]}")
if not models:
    L("!!! 注册表为空 -> run_analysis 必返回 [] -> 0 包。根因在『模块未被加载』")
    L("    检查：应用是否在 rfm.py 创建前已启动且未重启？或 __init__ 注册链未触发？")

L("\n===== 2) 原始列 =====")
L(f"{list(df.columns)}")

L("\n===== 3) map_dataset_columns 之后 =====")
mapped = map_dataset_columns("diag_session", None, df, {})
L(f"映射后列: {list(mapped.columns)}")

L("\n===== 4) 每个模型 can_run(映射后df) =====")
for m in models:
    try:
        ok = m.can_run(mapped)
    except Exception as e:
        ok = f"EXC:{e}"
    L(f"  {m.name:28s} can_run={ok}  required={getattr(m,'required_columns',None)}")

L("\n===== 5) run_analysis(映射后df) 结果 =====")
try:
    pkgs = run_analysis(mapped)
    L(f"返回包数: {len(pkgs)}")
    for p in pkgs:
        L(f"  - id={p.id} can_run={getattr(p,'can_run',None)} charts={len(getattr(p,'chart_data',[]))} kpis={len(getattr(p,'kpis',[]))}")
except Exception as e:
    L(f"!!! run_analysis 抛异常: {e}")

L("\n===== 6) 对照：跳过映射、直接对原始列 run_analysis =====")
try:
    pkgs2 = run_analysis(df)
    L(f"返回包数(无映射): {len(pkgs2)}")
    for p in pkgs2:
        L(f"  - id={p.id} can_run={getattr(p,'can_run',None)} charts={len(getattr(p,'chart_data',[]))}")
except Exception as e:
    L(f"!!! 无映射 run_analysis 抛异常: {e}")

with open(os.path.join(BASE, "_rfm_diag_out.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("\n".join(out))
