import pandas as pd
import numpy as np
import json

# 加载测试4真实数据
customers = pd.read_csv('数据测试集/测试4/customers.csv')
orders = pd.read_csv('数据测试集/测试4/orders.csv', usecols=['order_id', 'customer_id', 'order_time', 'total_usd'])

print('customers shape:', customers.shape)
print('orders shape:', orders.shape)
print('customers cols:', list(customers.columns))
print('orders cols:', list(orders.columns))

# 模拟上游 RFM 分群（8 个）
np.random.seed(7)
customers['Segment'] = pd.qcut(customers['age'].fillna(30), 8, labels=[f'群{i}' for i in range(8)], duplicates='drop')
seg = customers[['customer_id', 'Segment']].copy()
seg['M_raw'] = customers['total_spend'] if 'total_spend' in customers.columns else np.random.uniform(100, 5000, len(customers))
seg['R_raw'] = np.random.randint(1, 30, len(customers))

# 跑 user_profile
from src.analysis_engine.models.user_profile import UserProfileModel
m = UserProfileModel()

# 映射到规范列名
df = orders.rename(columns={'customer_id': '用户ID', 'order_id': '订单ID', 'order_time': '订单时间', 'total_usd': '订单实付金额'})
df['订单状态'] = '已完成'

# 注入用户画像列
df2 = df.merge(customers, left_on='用户ID', right_on='customer_id', how='inner')
print('after merge:', df2.shape)

pkg = m._compute(df2, {'rfm_user_segmentation': seg})
print('CANRUN:', pkg.can_run)
print('SUGGESTION:', pkg.suggestion)
print('TABLES_COUNT:', len(pkg.tables))

if pkg.tables:
    t = pkg.tables[0]
    print('TITLE:', t.title)
    print('COLUMNS:', t.columns)
    print('ROWS_COUNT:', len(t.rows))
    print('FIRST ROW KEYS:', list(t.rows[0].keys()) if t.rows else 'empty')
    if t.rows:
        print('FIRST ROW:', json.dumps(t.rows[0], ensure_ascii=False, indent=2, default=str))
        if len(t.rows) > 1:
            print('LAST ROW:', json.dumps(t.rows[-1], ensure_ascii=False, indent=2, default=str))