import pandas as pd
import numpy as np
np.random.seed(42)
n_users = 16268
n_orders = n_users * 3

# 用户级数据
user_df = pd.DataFrame({
    '用户ID': [f'u{i}' for i in range(n_users)],
    '年龄': np.random.randint(18, 65, n_users),
    '收入': np.random.uniform(3000, 30000, n_users),
    '性别': np.random.choice(['男', '女'], n_users),
    '所在地区': np.random.choice(['北京', '上海', '广州', '深圳'], n_users),
    '兴趣': np.random.choice(['运动', '音乐', '美食'], n_users),
    '总消费': np.random.uniform(100, 5000, n_users),
})

# 订单级（每用户 3 单）
order_df = pd.DataFrame({
    '订单ID': [f'o{i}' for i in range(n_orders)],
    '用户ID': np.repeat(user_df['用户ID'].values, 3),
    '订单时间': pd.date_range('2024-01-01', periods=n_orders, freq='h'),
    '订单实付金额': np.random.uniform(10, 500, n_orders),
    '订单状态': ['已完成'] * n_orders,
})

# 8 分群 RFM
quantiles = pd.qcut(user_df['总消费'], 8, labels=[f'群{i}' for i in range(8)])
user_df['Segment'] = quantiles

# 把 seg 里的 Segment/M_raw/R_raw 注入到 merged
user_df['M_raw'] = user_df['总消费']
user_df['R_raw'] = np.random.randint(1, 30, n_users)

# 合并为一份订单级 df（含用户级画像）
merged = order_df.merge(user_df, on='用户ID', how='inner')
print('merged rows:', len(merged))
print('merged cols:', list(merged.columns))

from src.analysis_engine.models.user_profile import UserProfileModel
m = UserProfileModel()
seg = user_df[['用户ID', 'Segment', 'M_raw', 'R_raw']].copy()
pkg = m._compute(merged, {'rfm_user_segmentation': seg})

print('CANRUN:', pkg.can_run)
print('TABLES_COUNT:', len(pkg.tables))
if pkg.tables:
    t = pkg.tables[0]
    print('TITLE:', t.title)
    print('COLUMNS:', t.columns)
    print('ROWS_COUNT:', len(t.rows))
    for k, v in list(t.rows[0].items()):
        print('  COL={} VAL={!r} TYPE={}'.format(k, v.get('value'), v.get('type')))