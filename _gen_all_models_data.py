"""生成可跑通项目所有分析模型的测试数据。

产出两份 CSV（与现有测试集同目录）：
  1. 全能订单流水测试集.csv  → RFM/CLV/同期群/流失/画像/关联规则/5个KMeans 共 11 个模型
  2. 用户行为事件测试集.csv    → 转化漏斗 1 个模型

生成后自动触发模型注册并跑 run_analysis，打印每个模型是否点亮。
"""
import os
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

random.seed(20260802)
np.random.seed(20260802)

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "数据测试集")

# ---------- 公共字典 ----------
PROVINCES = {
    "北京": ["北京"], "上海": ["上海"], "广东": ["广州", "深圳", "东莞"],
    "浙江": ["杭州", "宁波", "温州"], "江苏": ["南京", "苏州", "无锡"],
    "四川": ["成都", "绵阳"], "湖北": ["武汉", "宜昌"], "山东": ["济南", "青岛"],
}
PROV_LIST = list(PROVINCES.keys())

CATEGORIES = ["手机数码", "服饰鞋包", "家居生活", "美妆个护", "食品生鲜", "母婴玩具", "运动户外"]
SOURCES = ["百度SEM", "微信", "抖音", "直通车", "自然搜索", "小红书"]
GENDERS = ["男", "女"]
PLATFORMS = ["iOS", "Android", "Web"]
STATUS = ["已完成", "已完成", "已完成", "已退款", "已取消"]  # 偏已完成
BEHAVIORS = ["访问", "浏览", "加购", "收藏", "分享", "活跃", "支付", "下单"]

N_USERS = 600
START = datetime(2023, 1, 1)
END = datetime(2025, 6, 30)
SPAN_DAYS = (END - START).days


def rand_date():
    return START + timedelta(days=random.randint(0, SPAN_DAYS))


# 高价值省份 vs 低价值省份（制造地域群间差异，让 geo_seg 能分出簇）
HIGH_VALUE_PROV = ["北京", "上海", "广东", "浙江", "江苏"]
LOW_VALUE_PROV = ["四川", "湖北", "山东"]

# ---------- 用户主档 ----------
users = []
for i in range(1, N_USERS + 1):
    uid = f"U{i:04d}"
    reg = START + timedelta(days=random.randint(0, 200))
    # 用户分两类：活跃型（最近活跃+多买） / 沉默型（很久没来+少买），多特征一致分离
    if random.random() < 0.5:
        utype = "活跃"
        last_active = END - timedelta(days=random.randint(0, 30))        # 活跃型：近1个月来过
        reg = END - timedelta(days=random.randint(60, 400))              # 活跃型：较晚注册
    else:
        utype = "沉默"
        last_active = START + timedelta(days=random.randint(30, 360))    # 沉默型：1~2年前
        reg = START + timedelta(days=random.randint(0, 120))             # 沉默型：很早注册
    # 省份按高低价值分组抽样（强化省间差异）
    if random.random() < 0.45:
        prov = random.choice(HIGH_VALUE_PROV)
    else:
        prov = random.choice(LOW_VALUE_PROV)
    city = random.choice(PROVINCES[prov])
    gender = random.choice(GENDERS)
    age = random.randint(18, 60)
    # 绑定偏好类目，制造类目偏好群结构（供 category_seg 聚类）
    if utype == "活跃":
        fav_cats = random.sample(CATEGORIES, 2)  # 活跃用户偏好集中2类
    else:
        fav_cats = CATEGORIES  # 沉默用户类目分散
    users.append({
        "用户ID": uid, "注册日期": reg.strftime("%Y-%m-%d"),
        "最后活跃时间": last_active.strftime("%Y-%m-%d %H:%M:%S"),
        "性别": gender, "年龄": age, "省份": prov, "城市": city, "省份等级": "高" if prov in HIGH_VALUE_PROV else "低", "用户类型": utype, "偏好类目": "/".join(fav_cats),
    })
users_df = pd.DataFrame(users)
user_by_id = {u["用户ID"]: u for u in users}
UIDS = [u["用户ID"] for u in users]

# ---------- 商品主档（明确两档：高价高毛利 / 低价低毛利，制造清晰群结构） ----------
SKUS = []
HIGH_SKUS = []
LOW_SKUS = []
for j in range(1, 81):
    sku = f"S{j:03d}"
    cat = random.choice(CATEGORIES)
    if j <= 40:
        # 高价高毛利档
        price = round(random.uniform(1500, 4000), 2)
        margin = round(random.uniform(0.6, 0.8), 2)
        rec = {"商品ID": sku, "商品类目": cat, "商品单价": price, "毛利率": margin}
        HIGH_SKUS.append(rec)
    else:
        # 低价低毛利档
        price = round(random.uniform(20, 200), 2)
        margin = round(random.uniform(0.1, 0.3), 2)
        rec = {"商品ID": sku, "商品类目": cat, "商品单价": price, "毛利率": margin}
        LOW_SKUS.append(rec)
    SKUS.append(rec)
sku_df = pd.DataFrame(SKUS)
sku_by_id = {s["商品ID"]: s for s in SKUS}
# 计算商品成本时按毛利率反推，强化 sku_seg 的毛利差异
sku_margin = {s["商品ID"]: s.get("毛利率", 0.5) for s in SKUS}

# ============================================================
# 文件1：全能订单流水测试集
# ============================================================
order_rows = []
ORDER_SEQ = 0
ACTIVE_UIDS = [u["用户ID"] for u in users if u["用户类型"] == "活跃"]
SILENT_UIDS = [u["用户ID"] for u in users if u["用户类型"] == "沉默"]
# 订单按 7:3 分给活跃/沉默用户池，且活跃用户订单金额放大，强化 churn_seg 多特征分离
for _ in range(3000):
    ORDER_SEQ += 1
    if random.random() < 0.70:
        uid = random.choice(ACTIVE_UIDS)
        amt_boost = 1.5
    else:
        uid = random.choice(SILENT_UIDS)
        amt_boost = 0.4
    u = user_by_id[uid]
    if u["用户类型"] == "活跃":
        # 活跃用户订单集中在近1.5年
        otime = END - timedelta(days=random.randint(0, 540))
    else:
        # 沉默用户订单集中在2年前及更早
        otime = START + timedelta(days=random.randint(0, 400))
    # 一个订单含 1~3 个商品
    n_items = random.randint(1, 3)
    total = 0.0
    total_cost = 0.0
    total_qty = 0
    cat_set = set()
    for _ in range(n_items):
        # 高价值省偏向高价商品，低价值省偏向低价商品，强化地域群间差异
        fav = u.get("偏好类目", "").split("/")
        if u.get("用户类型") == "活跃" and random.random() < 0.75 and fav:
            # 活跃用户优先买自己偏好类目的商品，制造类目偏好群
            cand = [s for s in SKUS if s["商品类目"] in fav]
            if cand:
                sku = random.choice(cand)
            else:
                sku = random.choice(SKUS)
        elif u.get("省份等级") == "高" and random.random() < 0.7:
            sku = random.choice(HIGH_SKUS)
        elif u.get("省份等级") == "低" and random.random() < 0.7:
            sku = random.choice(LOW_SKUS)
        else:
            sku = random.choice(SKUS)
        s = sku_by_id[sku["商品ID"]]
        qty = random.randint(1, 4)
        price = s["商品单价"]
        total_qty += qty
        total += price * qty * amt_boost
        margin = sku_margin.get(sku["商品ID"], 0.5)
        total_cost += price * qty * (1 - margin)  # 成本 = 售价 × (1 - 毛利率)
        cat_set.add(s["商品类目"])
    total = round(total, 2)
    total_cost = round(total_cost, 2)
    if u["用户类型"] == "活跃" and random.random() < 0.85:
        status = "已完成"  # 活跃用户退款/取消概率低，保住高消费差异
    else:
        status = random.choice(STATUS)
    refund = 0.0
    if status == "已退款":
        refund = total
        total = 0.0
    elif status == "已取消":
        total = 0.0
    freight = round(random.uniform(0, 20), 2)
    order_rows.append({
        "用户ID": uid,
        "订单ID": f"O{ORDER_SEQ:06d}",
        "订单时间": otime.strftime("%Y-%m-%d %H:%M:%S"),
        "订单实付金额": total,
        "订单状态": status,
        "退款金额": refund,
        "商品成本": total_cost,
        "运费": freight,
        "流量来源": random.choice(SOURCES),
        "商品类目": "/".join(sorted(cat_set)),
        "注册日期": u["注册日期"],
        "最后活跃时间": u["最后活跃时间"],
        "性别": u["性别"],
        "年龄": u["年龄"],
        "省份": u["省份"],
        "城市": u["城市"],
        "商品ID": sku["商品ID"],
        "商品单价": sku["商品单价"],
        "购买数量": total_qty,
        "事件时间": otime.strftime("%Y-%m-%d %H:%M:%S"),
    })

orders_df = pd.DataFrame(order_rows)
orders_path = os.path.join(OUT_DIR, "全能订单流水测试集.csv")
orders_df.to_csv(orders_path, index=False, encoding="utf-8-sig")
print(f"[写] {orders_path}  {len(orders_df)} 行")

# ============================================================
# 文件2：用户行为事件测试集
# ============================================================
event_rows = []
SESSION_SEQ = 0
for _ in range(2000):
    uid = random.choice(UIDS)
    u = user_by_id[uid]
    etime = rand_date()
    SESSION_SEQ += 1
    sid = f"S{SESSION_SEQ:05d}_{random.randint(1,4)}"
    # 每个事件一行
    btype = random.choice(BEHAVIORS)
    # 订单实付金额仅支付/下单行为有值
    amt = 0.0
    if btype in ("支付", "下单"):
        amt = round(random.uniform(20, 2000), 2)
    event_rows.append({
        "用户ID": uid,
        "行为类型": btype,
        "事件时间": etime.strftime("%Y-%m-%d %H:%M:%S"),
        "流量来源": random.choice(SOURCES),
        "平台": random.choice(PLATFORMS),
        "会话ID": sid,
        "订单实付金额": amt,
    })

events_df = pd.DataFrame(event_rows)
events_path = os.path.join(OUT_DIR, "用户行为事件测试集.csv")
events_df.to_csv(events_path, index=False, encoding="utf-8-sig")
print(f"[写] {events_path}  {len(events_df)} 行")

# ============================================================
# 验证：触发注册 + run_analysis
# ============================================================
from src.analysis_engine import models as _m  # 触发 register_model 副作用
from src.analysis_engine.registry import get_models
from src.analysis_engine.engine import run_analysis

print("\n=== 注册模型数:", len(get_models()))
names = [m.name for m in get_models()]

print("\n--- 对【订单流水】跑 run_analysis ---")
pkgs1 = run_analysis(orders_df.copy())
got1 = {p.id for p in pkgs1} | {p.analysis_type for p in pkgs1}
print(f"点亮 {len(got1)} 个:")
for m in get_models():
    mark = "OK" if (m.name in got1 or m.name.split("与")[0] in got1 or "cohort" in got1 and "同期" in m.name) else "--"
    print(f"  [{mark}] {m.name}")

# 诊断：逐个模型 try/except，打印未点亮模型的真实异常
from src.analysis_engine.base import AnalysisModel
print("\n[诊断] 精确排查所有未点亮模型在订单流水的状态：")
for m in get_models():
    can = m.can_run(orders_df.copy())
    if can:
        try:
            pkg = m.compute(orders_df.copy())
            if not getattr(pkg, "can_run", True):
                print(f"  {m.name}: can_run=True but pkg.can_run=False, reason={getattr(pkg,'metadata',{}).get('reason','-')}")
        except Exception as e:
            print(f"  {m.name}: EXCEPTION {type(e).__name__}: {e}")

print("\n--- 对【行为事件】跑 run_analysis ---")
pkgs2 = run_analysis(events_df.copy())
got2 = {p.id for p in pkgs2} | {p.analysis_type for p in pkgs2}
print(f"点亮 {len(got2)} 个:")
for m in get_models():
    mark = "OK" if (m.name in got2 or "cohort" in got2 and "同期" in m.name) else "--"
    print(f"  [{mark}] {m.name}")

print("\n全部模型总数:", len(names))
print("订单流水点亮:", len(got1), " 行为事件点亮:", len(got2))
