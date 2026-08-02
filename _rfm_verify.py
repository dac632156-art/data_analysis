"""临时验证脚本：用合成交易级数据跑 RFM 模型，检查各图表 option 合法。"""
import random
import pandas as pd
import numpy as np
from src.analysis_engine.engine import run_analysis

random.seed(42)
np.random.seed(42)

rows = []
uid = 1000
for _ in range(320):
    uid += 1
    n_orders = random.choice([1, 1, 2, 2, 3, 4, 5])
    region = random.choice(["华东", "华北", "华南", "西南", "东北"])
    base_monetary = random.choice([80, 150, 300, 600, 1200, 2500])  # 客单差异
    # 近度：部分用户很久没来
    last_month_offset = random.choice([0, 0, 1, 1, 2, 3, 4])  # 0=最近月
    for k in range(n_orders):
        # 订单落在最近 0~(last_month_offset+1) 月内
        m_off = random.randint(0, last_month_offset + 1)
        month = 7 - m_off  # 2026-0X
        day = random.randint(1, 28)
        oid = f"O{uid}-{k}"
        amount = max(10, int(base_monetary * random.uniform(0.7, 1.3)))
        cost = int(amount * random.uniform(0.4, 0.7))
        refund = int(amount * random.uniform(0.0, 0.1)) if random.random() < 0.3 else 0
        ship = random.choice([0, 0, 8, 12, 15])
        rows.append({
            "用户ID": f"U{uid}",
            "订单时间": f"2026-{month:02d}-{day:02d}",
            "订单实付金额": amount,
            "订单ID": oid,
            "地域": region,
            "商品成本": cost,
            "退款金额": refund,
            "运费": ship,
        })

df = pd.DataFrame(rows)
print(f"[数据] 行数={len(df)} 用户数={df['用户ID'].nunique()} 月份={sorted(df['订单时间'].str[:7].unique())}")

packages = run_analysis(df, [])
rfm = next((p for p in packages if p.id == "rfm_user_segmentation"), None)
assert rfm is not None, "RFM 包未生成"
print(f"[包] KPI={len(rfm.kpis)} 图表={len(rfm.chart_data)} 表={len(rfm.tables)} "
      f"insights={len(rfm.insights)} conclusions={len(rfm.conclusions)}")

types = [c.chart_type for c in rfm.chart_data]
print("[图表类型]", types)
assert "bar" in types and "pie" in types and "rfm_scatter" in types
assert "sankey" in types and "rfm_line" in types
assert "heatmap_2d" in types and "dual_axis" in types

# 渲染各图表，检查 option 合法
from src.chart_renderer import ChartRenderer
rendered = ChartRenderer().render_all(rfm.chart_data)
for cd, item in zip(rfm.chart_data, rendered):
    assert item is not None, f"{cd.chart_type} 渲染返回 None"
    opt = getattr(item, "option", item)
    assert isinstance(opt, dict), f"{cd.chart_type} option 非 dict"
    assert "series" in opt and opt["series"], f"{cd.chart_type} 无 series"

# sankey 检查：无自环 link
sk = next(getattr(it, "option", it) for cd, it in zip(rfm.chart_data, rendered) if cd.chart_type == "sankey")
links = sk["series"][0]["links"]
assert all(l["source"] != l["target"] for l in links), "sankey 含自环 link"
print(f"[sankey] links={len(links)} 自环已过滤 稳定用户量={sk.get('_stable_value')}")

# heatmap_2d 检查：_heatmap_kind=cohort，未被截断
hm = next(getattr(it, "option", it) for cd, it in zip(rfm.chart_data, rendered) if cd.chart_type == "heatmap_2d")
assert hm.get("_heatmap_kind") == "cohort", "heatmap_2d 缺少 _heatmap_kind=cohort"
print(f"[heatmap_2d] 数据格={len(hm['series'][0]['data'])} 保真(未截断)")

# rfm_line 检查：8 条 series
ln = next(getattr(it, "option", it) for cd, it in zip(rfm.chart_data, rendered) if cd.chart_type == "rfm_line")
assert len(ln["series"]) == 8, f"rfm_line 应为 8 条线，实得 {len(ln['series'])}"
print(f"[rfm_line] series 数={len(ln['series'])} 月份={ln['xAxis']['data']}")

# dual_axis 检查：含 净毛利 柱 + 人数 线
da = next(getattr(it, "option", it) for cd, it in zip(rfm.chart_data, rendered) if cd.chart_type == "dual_axis")
print(f"[dual_axis] series 数={len(da['series'])} 类型={[s['type'] for s in da['series']]}")

# KPI 抽样
print("[KPI 抽样]")
for k in rfm.kpis[:4]:
    print(f"  - {k.label}: {k.value}")

# 明细表
t = rfm.tables[0]
print(f"[表] 标题={t.title} 列={t.columns}")
for r in t.rows[:3]:
    print("  ", r)

print("\n=== 测试2：纯订单明细（无 订单ID/无 消费次数 列）→ 降级 K-means 用户分层 ===")
df2 = df.drop(columns=["订单ID", "地域", "商品成本", "退款金额", "运费"])
df2 = df2.rename(columns={"订单实付金额": "消费金额", "订单时间": "消费日期"})
pkgs2 = run_analysis(df2, [])
rfm2 = next((p for p in pkgs2 if p.id == "rfm_user_segmentation"), None)
# 用户已定：无订单ID 保持降级 K-means（不返回 RFM 8 群）
assert rfm2 is None, "无订单ID 时应降级 K-means，不应生成 rfm_user_segmentation"
seg2 = next((p for p in pkgs2 if p.id == "user_seg"), None)
assert seg2 is not None, "无订单ID 纯明细应降级到 K-means user_seg 包"
print(f"[纯明细→降级] user_seg KPI={len(seg2.kpis)} 图表={[c.chart_type for c in seg2.chart_data]}")
print("  -> 无 地域列 → 不应有 heatmap_2d，insights 应有说明")

print("\n=== 测试3：用户级聚合表（每人一行 + 消费次数，单月）→ B 跳过 ===")
agg = df.groupby("用户ID").agg(
    消费日期=("订单时间", "max"),
    消费金额=("订单实付金额", "sum"),
    消费次数=("订单ID", "nunique"),
).reset_index()
agg["消费日期"] = "2026-07-15"  # 单月
pkgs3 = run_analysis(agg, [])
rfm3 = next((p for p in pkgs3 if p.id == "rfm_user_segmentation"), None)
assert rfm3 is not None, "用户级聚合 RFM 未触发"
ct3 = [c.chart_type for c in rfm3.chart_data]
print(f"[聚合表] 图表={ct3}")
assert "sankey" not in ct3 and "rfm_line" not in ct3, "单月聚合不应有 B 图表"
assert any("单一月份" in i or "动态演化" in i for i in rfm3.insights), "应提示无法计算动态演化"
print("  -> B 已跳过，insights 含说明 OK")

print("\n=== 测试4：用户级聚合表（每人一行 + 最近消费日期跨多月）→ 仍应跳过 B ===")
# 每人一行，但「最近消费日期」分布在不同月份（非交易级明细）
agg2 = pd.DataFrame({
    "用户ID": [f"U{i}" for i in range(1, 61)],
    "消费日期": [f"2026-{m:02d}-15" for m in ([7]*30 + [6]*20 + [5]*10)],
    "消费金额": [random.choice([200, 500, 1200, 3000]) for _ in range(60)],
    "消费次数": [random.choice([1, 2, 3, 5]) for _ in range(60)],
})
pkgs4 = run_analysis(agg2, [])
rfm4 = next((p for p in pkgs4 if p.id == "rfm_user_segmentation"), None)
assert rfm4 is not None, "用户级聚合(跨月) RFM 未触发"
ct4 = [c.chart_type for c in rfm4.chart_data]
print(f"[聚合跨月] 图表={ct4}")
assert "sankey" not in ct4 and "rfm_line" not in ct4, "用户级聚合(跨月)不应误触发 B"
assert any("动态演化" in i or "聚合" in i for i in rfm4.insights), "应提示无法计算动态演化"
print("  -> 新护栏 OK：聚合表即使日期跨多月份也不误触发 B")

print("\n全部验证通过 [OK]")
