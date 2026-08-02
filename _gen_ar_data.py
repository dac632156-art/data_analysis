"""生成商品关联规则测试数据（单张CSV长表，随机稀疏单品订单）。

目的：产出一份可用分析流水线验证「商品关联规则」块稳定不崩溃、并如实报告
「未发掘出显著关联规则」的数据。不做任何确定性共购偏向，共购率自然极低。

列：订单ID, 商品ID, 商品类目（中文列名，使 AssociationRulesModel.can_run 直接通过）
"""
import csv
import random

random.seed(20260730)

CATEGORIES = ["食品", "母婴", "数码", "家居", "服饰", "美妆", "图书", "运动", "汽车", "宠物"]

# 每个类目下随机 15~30 个商品，商品ID 形如 P00001
cat_products: dict[str, list[str]] = {}
pid = 1
for c in CATEGORIES:
    n = random.randint(15, 30)
    prods = []
    for _ in range(n):
        prods.append(f"P{pid:05d}")
        pid += 1
    cat_products[c] = prods

# 平铺所有 (商品ID, 类目) 供随机抽
all_items = [(p, c) for c, ps in cat_products.items() for p in ps]

OUT_PATH = r"d:/数据分析项目/数据测试集/测试8_关联规则.csv"
N_ORDERS = 1500
rows: list[tuple[str, str, str]] = []
order_id = 10001

for _ in range(N_ORDERS):
    oid = f"O{order_id}"
    order_id += 1
    # 以单品订单为主：85% 一单一件，12% 两件，3% 三件（稀疏）
    r = random.random()
    if r < 0.85:
        k = 1
    elif r < 0.97:
        k = 2
    else:
        k = 3
    # 随机抽 k 件不同商品（不引入共购偏向）
    chosen = random.sample(all_items, k)
    for p, c in chosen:
        rows.append((oid, p, c))

with open(OUT_PATH, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["订单ID", "商品ID", "商品类目"])
    w.writerows(rows)

print(f"生成完成: {len(rows)} 行, {N_ORDERS} 个订单 -> {OUT_PATH}")
