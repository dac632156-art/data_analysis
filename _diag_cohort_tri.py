import pandas as pd, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import src.analysis_engine.models.cohort as C
from src.analysis_engine.models.cohort import _select_user_key, _normalize_columns, validate_input, compute_base

orders = pd.read_csv("数据测试集/测试6/olist_orders_dataset.csv")
cust = pd.read_csv("数据测试集/测试6/olist_customers_dataset.csv")
items = pd.read_csv("数据测试集/测试6/olist_order_items_dataset.csv")
df = orders.merge(cust[["customer_id","customer_unique_id"]], on="customer_id", how="left")
am = items.groupby("order_id").apply(lambda x: (x["price"]+x["freight_value"]).sum())
df["payment_value"] = df["order_id"].map(am)
df = df.rename(columns={"customer_unique_id":"用户ID","order_purchase_timestamp":"订单时间",
                        "payment_value":"订单实付金额","order_id":"订单ID",
                        "order_status":"订单状态"})

print("RAW_MAX_DT=" + str(pd.to_datetime(df["订单时间"]).max()), file=sys.stderr)

# 复刻 m.compute 预处理
chosen, rate = _select_user_key(df)
print("CHOSEN_KEY=" + repr(chosen) + " RATE=%.4f" % rate, file=sys.stderr)
if chosen is not None and chosen != "用户ID":
    if "用户ID" in df.columns:
        df = df.drop(columns=["用户ID"])
    df = df.rename(columns={chosen: "用户ID"})
df = _normalize_columns(df)
v = validate_input(df)
work = v["df"]
print("VALIDATE_STATUS=" + v["status"], file=sys.stderr)
print("WORK_MAX_DT=" + str(pd.to_datetime(work["订单时间"]).max()), file=sys.stderr)

# 9、10月订单与状态
wm = pd.to_datetime(work["订单时间"])
for mm in ["2018-09","2018-10"]:
    sub = work[wm.astype(str).str.startswith(mm)]
    print("WORK_%s_ORDERS=%d" % (mm, len(sub)), file=sys.stderr)
    if "订单状态" in work.columns and len(sub):
        print("WORK_%s_STATUS=%s" % (mm, sub["订单状态"].value_counts().to_dict()), file=sys.stderr)

# 首单月分布（work 内）
first_dt = work.groupby("用户ID")["订单时间"].transform("min")
cm = (pd.to_datetime(first_dt).dt.year*12 + pd.to_datetime(first_dt).dt.month)
dist = cm.value_counts().sort_index()
# 打印最后 6 个首单月
keys = sorted(dist.index.tolist())
print("LAST6_COHORT_MONTHS=" + str([(C._mi_to_label(k), int(dist[k])) for k in keys[-6:]]), file=sys.stderr)

base = compute_base(work)
print("BASE_COHORT_LABELS_TAIL=" + str([C._mi_to_label(k) for k in base["cohort_labels"][-6:]]), file=sys.stderr)
print("BASE_MAX_J=" + str(base["max_j"]), file=sys.stderr)

# 打印每个 win cohort 行的 j 范围
_W = C._SUMMARY_COHORT_WINDOW
all_labels = base["cohort_labels"]
win = all_labels[-_W:]
for m in win:
    js = [j for (i,j) in base["retention"].keys() if i==m]
    print("ROW %s j_range=%s" % (C._mi_to_label(m), (min(js),max(js)) if js else None), file=sys.stderr)
