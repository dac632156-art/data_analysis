"""临时：验证 测试1（用户级预聚合）能触发 RFM，并回归 同期群（交易级）。UTF-8 写文件。"""
import os
import pandas as pd
from src.analysis_engine.engine import run_analysis
from src.analysis_engine.models.rfm import RFMModel

out = []

def section(t): out.append("\n===== " + t + " ======")

# ---- 测试1：用户级预聚合 ----
section("测试1.csv（预聚合用户级）")
df1 = pd.read_csv(r"d:\数据分析项目\数据测试集\测试1.csv", low_memory=False)
out.append(f"行数={len(df1)} 用户唯一={df1['User_ID'].nunique()}")
m = RFMModel()
out.append(f"can_run={m.can_run(df1)}")
pk = run_analysis(df1, [])
rfm = next((p for p in pk if p.id == "rfm_user_segmentation"), None)
if rfm is None:
    out.append("结果: 未触发 RFM !!")
else:
    ct = [c.chart_type for c in rfm.chart_data]
    out.append(f"触发OK | charts({len(ct)})={ct}")
    out.append(f"KPI={[k.label for k in rfm.kpis]}")
    out.append("含 sankey/rfm_line(应为F, 预聚合无逐月)? " + str(("sankey" in ct) or ("rfm_line" in ct)))
    out.append("含 heatmap_2d(应为T, 有Location)? " + str("heatmap_2d" in ct))
    # 抽样看 R/F/M 是否来自正确列
    out.append("insight[0]=" + rfm.insights[0][:60])

# ---- 回归：同期群（交易级） ----
section("同期群测试数据.csv（交易级·回归）")
df2 = pd.read_csv(r"d:\数据分析项目\数据测试集\同期群测试数据.csv", low_memory=False)
pk2 = run_analysis(df2, [])
rfm2 = next((p for p in pk2 if p.id == "rfm_user_segmentation"), None)
if rfm2 is None:
    out.append("回归失败: 同期群未触发 !!")
else:
    ct2 = [c.chart_type for c in rfm2.chart_data]
    out.append(f"触发OK | charts({len(ct2)})={ct2}")
    out.append("含 sankey/rfm_line(应为T)? " + str(("sankey" in ct2) or ("rfm_line" in ct2)))
    out.append("含 heatmap_2d(应为F, 无地域)? " + str("heatmap_2d" in ct2))

with open(r"d:\数据分析项目\_rfm_t1_out.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("WROTE _rfm_t1_out.txt")
