"""临时：用真实文件 同期群测试数据.csv 实跑 RFM，确认开箱即用。"""
import pandas as pd
from src.analysis_engine.engine import run_analysis

df = pd.read_csv(r"d:\数据分析项目\数据测试集\同期群测试数据.csv", low_memory=False)
print(f"行数={len(df)}  列={list(df.columns)}")
print(f"用户数={df['用户ID'].nunique()}  月份数={pd.to_datetime(df['订单时间'],errors='coerce').dt.to_period('M').nunique()}")

pkgs = run_analysis(df, [])
rfm = next((p for p in pkgs if p.id == "rfm_user_segmentation"), None)
if rfm is None:
    print("结果: 未触发 RFM（异常）")
else:
    ct = [c.chart_type for c in rfm.chart_data]
    print(f"触发RFM OK | charts({len(ct)})={ct}")
    print(f"KPI={[k.label for k in rfm.kpis]}")
    print("B是否触发:", "sankey" in ct or "rfm_line" in ct)
    print("insights示例:", rfm.insights[:2])
