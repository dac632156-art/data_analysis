"""用测试1真实数据跑完整 RFM 报告并打印（只读，不改代码）。"""
import os
import sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.analysis_engine.models.rfm import RFMModel, SEGMENT_INFO, SEGMENTS
from src.analysis_engine.base import AnalysisPackage

CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "数据测试集", "测试1.csv")

df = pd.read_csv(CSV, low_memory=False)
print(f"=== 输入数据 ===  shape={df.shape}")
print(f"列: {list(df.columns)}")
print(df.head(3).to_string())

model = RFMModel()
print(f"\n=== can_run === {model.can_run(df)}")

pkg = model.compute(df)

lines = []
L = lines.append
L("=" * 70)
L("RFM 用户分层 · 完整报告（测试1）")
L("=" * 70)

L(f"\n[业务问题] {pkg.business_question}")
L(f"[算法] {pkg.algorithm}  [置信度] {pkg.confidence}")

L("\n" + "-" * 70)
L("一、KPI 指标")
L("-" * 70)
for k in pkg.kpis:
    L(f"  • {k.label}: {k.value}")

L("\n" + "-" * 70)
L("二、图表清单")
L("-" * 70)
for c in pkg.chart_data:
    L(f"  • [{c.chart_type}] {c.title}  (slot={c.slot}, 数据条数={len(c.data)})")

L("\n" + "-" * 70)
L("三、洞察 Insights")
L("-" * 70)
for i in pkg.insights:
    L(f"  • {i}")

L("\n" + "-" * 70)
L("四、明细表：RFM 8 群体汇总")
L("-" * 70)
t = pkg.tables[0]
L("  " + " | ".join(t.columns))
L("  " + "-" * 56)
for row in t.rows:
    L("  " + " | ".join(str(row.get(c, "")) for c in t.columns))

L("\n" + "-" * 70)
L("五、8 层结论（定义 + 含义）")
L("-" * 70)
for c in pkg.conclusions:
    L(f"  {c}")

L("\n" + "-" * 70)
L("六、8 层运营策略 + 转化路径")
L("-" * 70)
for r in pkg.recommendations:
    L(f"  {r}")

L("\n" + "=" * 70)
L("报告结束")
L("=" * 70)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_rfm_report_out.txt")
with open(out, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("\nWROTE", out)
