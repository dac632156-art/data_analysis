"""向量化加速基准：在同一进程、同一份 150 万行数据上，对比旧 apply 写法 vs 新 np.select 写法的耗时。
只做计时与一致性断言，不修改任何业务代码。
"""
import time
import numpy as np
import pandas as pd

N = 1_500_000
rng = np.random.default_rng(42)
M_hi = rng.integers(0, 2, N).astype(bool)
R_hi = rng.integers(0, 2, N).astype(bool)
F_hi = rng.integers(0, 2, N).astype(bool)
df = pd.DataFrame({"M_hi": M_hi, "R_hi": R_hi, "F_hi": F_hi})


# ---- 复刻旧写法：RFM 8 宫格分群（apply 逐行 if-else）----
def _seg_of(m, r, f):
    if m and r and f:
        return "高价值核心客户"
    if m and r and not f:
        return "潜力高价值客户"
    if m and not r and f:
        return "沉睡高价值客户"
    if m and not r and not f:
        return "流失预警高价值客户"
    if (not m) and r and f:
        return "稳定普通客户"
    if (not m) and r and not f:
        return "潜力普通客户"
    if (not m) and not r and f:
        return "沉睡普通客户"
    return "流失预警普通客户"


# ---- 复刻新写法：np.select ----
def _seg_new(m, r, f):
    return np.select(
        [m & r & f, m & r & ~f, m & ~r & f, m & ~r & ~f,
         ~m & r & f, ~m & r & ~f, ~m & ~r & f, ~m & ~r & ~f],
        ["高价值核心客户", "潜力高价值客户", "沉睡高价值客户", "流失预警高价值客户",
         "稳定普通客户", "潜力普通客户", "沉睡普通客户", "流失预警普通客户"],
        default="流失预警普通客户",
    )


# ============ RFM 分群计时 ============
t0 = time.perf_counter()
old_seg = df.apply(lambda r: _seg_of(r["M_hi"], r["R_hi"], r["F_hi"]), axis=1)
t_old = time.perf_counter() - t0

t0 = time.perf_counter()
new_seg = _seg_new(df["M_hi"], df["R_hi"], df["F_hi"])
t_new = time.perf_counter() - t0

assert (old_seg.values == new_seg).all(), "RFM 新旧写法结果不一致！"
print(f"[RFM 分群] 旧 apply: {t_old:.3f}s | 新 np.select: {t_new:.3f}s | 加速 {t_old / t_new:.1f}x")

# ============ CLV 分层计时 ============
clv = rng.random(N) * 1000.0
q_low, q_high = np.percentile(clv, [20, 80])


def _tier(v):
    if v >= q_high:
        return "高价值"
    if v < q_low:
        return "低价值"
    return "中价值"


t0 = time.perf_counter()
old_tier = pd.Series(clv).apply(_tier)
t_old_c = time.perf_counter() - t0

t0 = time.perf_counter()
new_tier = np.select([clv >= q_high, clv < q_low], ["高价值", "低价值"], default="中价值")
t_new_c = time.perf_counter() - t0

assert (old_tier.values == new_tier).all(), "CLV 新旧写法结果不一致！"
print(f"[CLV 分层] 旧 apply: {t_old_c:.3f}s | 新 np.select: {t_new_c:.3f}s | 加速 {t_old_c / t_new_c:.1f}x")

# ============ Cohort 留存率/客单价向量化计时 ============
# 复刻旧写法：逐行 apply 除法（除数为 0 返回 None）
def _retention_old(r):
    return (r["U_ij"] / r["cohort_size"]) if r["cohort_size"] > 0 else None
def _arpu_old(r):
    return (r["R_ij"] / r["U_ij"]) if r["U_ij"] > 0 else None

# 构造大表：含部分 cohort_size==0 / U_ij==0 的边界行
N_c = 1_500_000
U_ij = rng.integers(0, 500, N_c).astype(float)
cohort_size = rng.integers(0, 500, N_c).astype(float)
R_ij = rng.random(N_c) * 1000.0
coh = pd.DataFrame({"U_ij": U_ij, "cohort_size": cohort_size, "R_ij": R_ij})

t0 = time.perf_counter()
old_ret = coh.apply(_retention_old, axis=1)
old_arpu = coh.apply(_arpu_old, axis=1)
t_old_h = time.perf_counter() - t0

t0 = time.perf_counter()
new_ret = np.where(coh["cohort_size"] > 0, coh["U_ij"] / coh["cohort_size"], np.nan)
new_arpu = np.where(coh["U_ij"] > 0, coh["R_ij"] / coh["U_ij"], np.nan)
t_new_h = time.perf_counter() - t0

assert np.allclose(old_ret.values, new_ret, equal_nan=True), "cohort 留存率新旧不一致"
assert np.allclose(old_arpu.values, new_arpu, equal_nan=True), "cohort 客单价新旧不一致"
print(f"[Cohort 留存率/客单价] 旧 apply: {t_old_h:.3f}s | 新 np.where: {t_new_h:.3f}s | 加速 {t_old_h / t_new_h:.1f}x")

print("\n一致性断言全部通过：新旧写法产出完全相同。")
