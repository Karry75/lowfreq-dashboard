# -*- coding: utf-8 -*-
"""读本地 out/records.json，按电池产品统计低频分布，重点高亮"深圳4824"等优选产品。
用法：把本文件放到 lowfreq_local/ 目录下，确保已在看板点过 [SYNC] 同步数据库（生成 out/records.json），
然后运行：python3 analyze_products.py
"""
import json
import os
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(BASE, 'out', 'records.json')

if not os.path.exists(path):
    print("未找到 out/records.json，请先打开看板点 [SYNC] 同步数据库一次。")
    raise SystemExit(1)

data = json.load(open(path, encoding='utf-8'))
rows = data.get('rows', [])
now = data.get('now', '?')
print(f"数据截止: {now} | 总活跃协议(全量): {len(rows)}")

PREF = ['深圳4824', '杭州4824', '阳朔4824', '深圳4814', '杭州4814', '阳朔4814']

# 按产品聚合
agg = defaultdict(lambda: {'total': 0, 'lf': 0, 'l1': 0, 'l2': 0, 'l3': 0, 'l4': 0, 'sw': 0, 'lf_sw': 0})
for r in rows:
    p = (r.get('pd') or '').strip() or '(空/未知)'
    a = agg[p]
    a['total'] += 1
    a['sw'] += (r.get('sw') or 0)
    if r.get('lf'):
        a['lf'] += 1
        a['lf_sw'] += (r.get('sw') or 0)
        lv = r.get('lv') or 0
        a['l%d' % lv] += 1

# 按低频数降序
items = sorted(agg.items(), key=lambda kv: -kv[1]['lf'])

print("\n=== 各电池产品：活跃协议数 / 低频用户 / 各档(L1~L4) / 低频占比 / 平均累计换电 ===")
print(f"{'产品':<30}{'活跃':>8}{'低频':>8}{'L1':>5}{'L2':>5}{'L3':>5}{'L4':>5}{'低频占比':>9}{'平均换电':>9}")
for p, a in items:
    rate = (a['lf'] / a['total'] * 100) if a['total'] else 0
    avg_sw = (a['sw'] / a['total']) if a['total'] else 0
    mark = '   <<<' if any(k in p for k in PREF) else ''
    print(f"{p[:29]:<30}{a['total']:>8}{a['lf']:>8}{a['l1']:>5}{a['l2']:>5}{a['l3']:>5}{a['l4']:>5}{rate:>8.1f}%{avg_sw:>9.2f}{mark}")

# 重点：4824 / 4814 真相
print("\n=== 含 4824 / 4814 字样的产品重点核查 ===")
found = False
for p, a in items:
    if '4824' in p or '4814' in p:
        found = True
        rate = (a['lf'] / a['total'] * 100) if a['total'] else 0
        avg_lf_sw = (a['lf_sw'] / a['lf']) if a['lf'] else 0
        print(f"  【{p}】活跃协议={a['total']}  低频={a['lf']} (占比 {rate:.1f}%)  "
              f"L1={a['l1']}/L2={a['l2']}/L3={a['l3']}/L4={a['l4']}  低频用户平均换电={avg_lf_sw:.2f}次")
if not found:
    print("  未发现含 4824/4814 的产品名，请核对看板下拉里'深圳4824'对应的实际 product 名称。")

print("\n【如何解读】")
print("1) 低频占比 = 该产品低频协议数 / 该产品活跃协议总数。")
print("2) 若深圳4824活跃协议本就不多(如<1000)，低频400多属正常(占比偏高说明这批用户近期几乎不换电)。")
print("3) 若深圳4824活跃协议有数千却只低频400多，结合'低频用户平均换电'判断：")
print("   平均换电很高→产品本身高频，低频少是正常现象；平均换电也很低→再查阈值/母集。")
print("4) 注意：三千多/1717 是【所有产品加总】的全量低频；深圳4824只是单一产品子集，二者不是同一量级。")
