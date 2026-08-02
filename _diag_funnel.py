"""诊断脚本：实跑 funnel._advanced_a 看渠道转化质量对比的 data_rows 真值。"""
import sys
sys.path.insert(0, ".")

import pandas as pd
from src.analysis_engine.models.funnel import (
    FunnelAnalysisModel,
    _sniff_model_with_freq,
    _core_compute,
    _advanced_a,
)

df = pd.read_csv("数据测试集/转化漏斗测试数据.csv")
print("CSV 列名:", df.columns.tolist())
print("CSV 总行数:", len(df))

# 跑 compute
model = FunnelAnalysisModel()
pkg = model.compute(df)
print("\n=== pkg.charts 中的渠道转化质量对比 ===")
for chart in pkg.charts:
    if chart.slot == "funnel_channel":
        print(f"chart_type: {chart.chart_type}")
        print(f"title: {chart.title}")
        print(f"raw_data ({len(chart.raw_data)} 行):")
        for row in chart.raw_data:
            print(f"  {row}")

print("\n=== 所有 charts 摘要 ===")
for chart in pkg.charts:
    print(f"  slot={chart.slot}  type={chart.chart_type}  title={chart.title}  raw_data_len={len(chart.raw_data or [])}")

print("\n=== pkg.kpis ===")
for kpi in pkg.kpis:
    print(f"  {kpi.label}: {kpi.value}")