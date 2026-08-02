"""端到端诊断：run_df_to_packages 后 charts 里 hbar_family 的 raw_data 是否有值"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from backend.routers._analysis_pipeline import run_df_to_packages

# 构造能触发 churn F 分支的数据：每个用户 >=2 单（算得出群体间隔），部分流失
n_users = 120
base = datetime(2024, 1, 1)
rows = []
for i in range(n_users):
    uid = f"U{i:03d}"
    recent = (i % 2 == 0)  # 一半正常(近期活跃)，一半流失
    for k in range(3):
        order_days = (10 + k * 5) if recent else (200 + k * 5)
        evt_days = (3 + k * 2) if recent else (205 + k * 5)
        city = np.random.choice(["北京", "上海", "广州"], p=[0.5, 0.3, 0.2])
        gender = np.random.choice(["男", "女"])
        age = np.random.choice([25, 35, 45, 55])
        rows.append({
            "用户ID": uid,
            "订单时间": (base - timedelta(days=order_days)).strftime("%Y-%m-%d %H:%M:%S"),
            "事件时间": (base - timedelta(days=evt_days)).strftime("%Y-%m-%d %H:%M:%S"),
            "城市": city,
            "性别": gender,
            "年龄": age,
            "订单实付金额": np.random.randint(50, 500),
        })
df = pd.DataFrame(rows)
df.loc[df["用户ID"].str[-3:].astype(int) % 2 == 1, "城市"] = "北京"

pkgs, meta = run_df_to_packages(df)
print("生成包数量:", len(pkgs))
for pkg in pkgs:
    charts = pkg.get("charts", [])
    hb = [c for c in charts if c.get("chart_type") == "hbar_family"]
    print(f"\n包 charts 数={len(charts)}, hbar_family 数={len(hb)}")
    if hb:
        c = hb[0]
        rd = c.get("raw_data")
        print("  chart_type:", c.get("chart_type"))
        print("  raw_data 长度:", len(rd) if rd else 0)
        print("  raw_data 前2条:", (rd[:2] if rd else None))
        print("  option 类型:", type(c.get("option")).__name__, "| option 内容keys:", list(c.get("option").keys()) if isinstance(c.get("option"), dict) else c.get("option"))
        # 模拟前端 DashboardPage 第201行提取
        extracted = (c.get("data") or c.get("raw_data") or [])
        print("  前端提取 raw_data 长度:", len(extracted) if extracted else 0)
    else:
        # 看有哪些 chart_type
        types = [c.get("chart_type") for c in charts]
        print("  所有 chart_type:", types)
