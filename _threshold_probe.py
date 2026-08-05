import csv, os
from collections import defaultdict, Counter
from datetime import datetime

BASE = 'D:/数据分析项目/数据测试集'


def load(path):
    with open(path, encoding='utf-8', errors='ignore') as f:
        for row in csv.DictReader(f):
            yield row


def quantile(sv, p):
    if not sv:
        return None
    sv = sorted(sv)
    if len(sv) == 1:
        return sv[0]
    k = (len(sv) - 1) * p
    f = int(k)
    c = min(f + 1, len(sv) - 1)
    return sv[f] if f == c else sv[f] + (sv[c] - sv[f]) * (k - f)


def parse_dt(s):
    if not s:
        return None
    s = s.replace(' UTC', '').replace('Z', '').strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


print('=' * 70)
print('A. 样本量')
for name in ['测试1', '测试2', '测试3', '测试5', '测试7']:
    print(f'  {name}.csv: {sum(1 for _ in load(BASE + "/" + name + ".csv"))} 行')
for t in ['customers', 'orders', 'events', 'order_items', 'sessions']:
    print(f'  测试4/{t}.csv: {sum(1 for _ in load(BASE + "/测试4/" + t + ".csv"))} 行')

print('\nB. 相对流失天数分布(绝对天数代理, 测试1/2/7)')
for name, col in [('测试1', 'Last_Login_Days_Ago'), ('测试2', 'Recency'), ('测试7', 'LastPurchaseDaysAgo')]:
    v = []
    for r in load(BASE + '/' + name + '.csv'):
        try:
            v.append(float(r[col]))
        except Exception:
            pass
    v.sort()
    print(f'  {name}.{col}: P50={quantile(v,.5):.1f}  P75={quantile(v,.75):.1f}  P90={quantile(v,.9):.1f}')

print('\nC. 购买间隔倍数(客户最后订单距参考日 / 全集中位间隔), 超2倍占比')
for name, path, cid, ot in [('测试4', BASE + '/测试4/orders.csv', 'customer_id', 'order_time'),
                             ('测试5', BASE + '/测试5.csv', 'user_id', 'event_time')]:
    byc = defaultdict(list)
    for r in load(path):
        t = parse_dt(r.get(ot, ''))
        if t:
            byc[r[cid]].append(t)
    gaps = []
    for ts in byc.values():
        ts.sort()
        for i in range(1, len(ts)):
            gaps.append((ts[i] - ts[i - 1]).days)
    if not gaps:
        print(f'  {name}: 无时间间隔数据')
        continue
    om = quantile(gaps, .5)
    ref = max(max(ts) for ts in byc.values())
    ratios = [(ref - max(ts)).days / om for ts in byc.values() if om > 0]
    if not ratios:
        print(f'  {name}: 订单间隔数据不足(中位间隔={om:.0f}天), 跳过超2倍计算')
        continue
    ratios.sort()
    over2 = sum(1 for x in ratios if x > 2) / len(ratios)
    print(f'  {name}: 中位间隔={om:.0f}天  超2倍客户占比={over2*100:.1f}%  P90倍数={quantile(ratios,.9):.1f}  n客户={len(byc)}')

print('\nD. top20%客户营收集中度')
def spent_by_customer(name):
    d = defaultdict(float)
    if name == '测试1':
        for r in load(BASE + '/测试1.csv'):
            try:
                d[r['User_ID']] += float(r['Total_Spending'])
            except Exception:
                pass
    elif name == '测试2':
        for r in load(BASE + '/测试2.csv'):
            s = 0.0
            for k in ['MntWines', 'MntFruits', 'MntMeatProducts', 'MntFishProducts', 'MntSweetProducts', 'MntGoldProds']:
                try:
                    s += float(r.get(k, 0) or 0)
                except Exception:
                    pass
            d[r['ID']] += s
    elif name == '测试4':
        for r in load(BASE + '/测试4/orders.csv'):
            try:
                d[r['customer_id']] += float(r['total_usd'])
            except Exception:
                pass
    elif name == '测试5':
        for r in load(BASE + '/测试5.csv'):
            try:
                d[r['user_id']] += float(r['price'])
            except Exception:
                pass
    return d

for name in ['测试1', '测试2', '测试4', '测试5']:
    d = spent_by_customer(name)
    if not d:
        print(f'  {name}: 无金额数据')
        continue
    tot = sorted(d.values(), reverse=True)
    top20 = max(1, int(len(tot) * 0.2))
    print(f'  {name}: top20%占比={sum(tot[:top20])/sum(tot)*100:.1f}%  n客户={len(tot)}')

print('\nE. RFM 关键层占比(测试4/5 完整RFM)')
for name, path, cid, ot, amt in [('测试4', BASE + '/测试4/orders.csv', 'customer_id', 'order_time', 'total_usd'),
                                 ('测试5', BASE + '/测试5.csv', 'user_id', 'event_time', 'price')]:
    rows = []
    for r in load(path):
        t = parse_dt(r.get(ot, ''))
        try:
            m = float(r[amt])
        except Exception:
            m = None
        if t and m is not None:
            rows.append((r[cid], t, m))
    if not rows:
        print(f'  {name}: 无RFM数据')
        continue
    ref = max(t for _, t, _ in rows)
    byc = defaultdict(lambda: {'last': None, 'n': 0, 'm': 0.0})
    for c, t, m in rows:
        d = byc[c]
        d['n'] += 1
        d['m'] += m
        if d['last'] is None or t > d['last']:
            d['last'] = t
    R = []; F = []; M = []
    for c, d in byc.items():
        R.append((ref - d['last']).days)
        F.append(d['n'])
        M.append(d['m'])
    def qcut(vals):
        s = sorted(vals)
        edges = [quantile(s, p) for p in [0, .2, .4, .6, .8, 1]]
        out = []
        for v in vals:
            sc = 1
            for i in range(5):
                if edges[i] is not None and v <= edges[i + 1]:
                    sc = 5 - i
                    break
            out.append(sc)
        return out
    rs = qcut(R); fs = qcut(F); ms = qcut(M)
    n = len(R)
    imp_value = sum(1 for i in range(n) if rs[i] >= 4 and fs[i] >= 4 and ms[i] >= 4) / n * 100
    imp_loss = sum(1 for i in range(n) if rs[i] <= 2 and fs[i] >= 4 and ms[i] >= 4) / n * 100
    print(f'  {name}: 重要价值类(R>=4,F>=4,M>=4)={imp_value:.1f}%  重要流失类(R<=2,F>=4,M>=4)={imp_loss:.1f}%  n客户={n}')

print('\nF. cohort M1留存率(测试4: 按signup月分群, 首单后30天内有二单占比)')
signup = {}
for r in load(BASE + '/测试4/customers.csv'):
    t = parse_dt(r.get('signup_date', ''))
    if t:
        signup[r['customer_id']] = t
obc = defaultdict(list)
for r in load(BASE + '/测试4/orders.csv'):
    t = parse_dt(r.get('order_time', ''))
    if t:
        obc[r['customer_id']].append(t)
grp = defaultdict(list)
for c, sd in signup.items():
    if c in obc:
        grp[(sd.year, sd.month)].append(c)
m1 = []
for cs in grp.values():
    ret = 0
    for c in cs:
        ts = sorted(obc[c])
        if len(ts) >= 2 and (ts[1] - ts[0]).days <= 30:
            ret += 1
    if cs:
        m1.append(ret / len(cs))
if m1:
    m1.sort()
    print(f'  同期群数={len(m1)}  M1留存 P10={quantile(m1,.1)*100:.1f}%  P50={quantile(m1,.5)*100:.1f}%  P90={quantile(m1,.9)*100:.1f}%')

print('\nG. funnel 步骤转化(测试4 events.event_type, 按session)')
et = Counter()
sess_steps = defaultdict(set)
for r in load(BASE + '/测试4/events.csv'):
    e = r.get('event_type', '')
    et[e] += 1
    sess_steps[r.get('session_id', '')].add(e)
print('  event_type 总数:', dict(et))
step_cnt = Counter()
for steps in sess_steps.values():
    for s in steps:
        step_cnt[s] += 1
print('  各步骤覆盖的session数:', dict(step_cnt))
n_sess = len(sess_steps)
if n_sess:
    for s, c in step_cnt.most_common():
        print(f'    {s}: {c} sessions = {c/n_sess*100:.1f}%')
