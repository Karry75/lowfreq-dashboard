# -*- coding: utf-8 -*-
"""
低频口径对照脚本
================
用途：在同一份真实 records.json（当前活跃母集）上，分别用
      「带 15 天保护（当前代码 = 用户指定 4 条判定）」与
      「临时无保护版（上一轮临时口径）」
      复算低频用户数，分离"阈值效应"与"母集效应"。

运行（在 lowfreq_local 目录下）：
      python analyze_lf.py
或指定文件：
      python analyze_lf.py /path/to/records.json
"""
import json, os, sys

def find_records():
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        return sys.argv[1]
    BASE = os.path.dirname(os.path.abspath(__file__))
    cands = [
        os.path.join(BASE, 'out', 'records.json'),
        os.path.join(os.getcwd(), 'out', 'records.json'),
        '/workspace/lowfreq_local/out/records.json',
    ]
    for p in cands:
        if os.path.exists(p):
            return p
    return None

p = find_records()
if not p:
    print("找不到 records.json，请放到 out/ 下或作为参数传入。")
    sys.exit(1)

data = json.load(open(p, encoding='utf-8'))
rows = data.get('rows') or data.get('records') or []
diag = data.get('diagnostic', {})
active_total = diag.get('active_total', len(rows))

# ---- 当前代码口径：用户指定的 4 条判定（生效 >15 天参与，≤15 天保护） ----
def lf_protected(days, total):
    if days is None or days <= 15:
        return False
    if days <= 30:   return total < 1   # L1
    if days <= 45:   return total < 2   # L2
    if days <= 60:   return total < 3   # L3
    return total < 4                            # L4

# ---- 临时无保护版（上一轮临时口径，现已回退）：≤15 天也参与 ----
def lf_noprotect(days, total):
    if days is None:
        return False
    if days <= 30:   return total < 1
    if days <= 45:   return total < 2
    if days <= 60:   return total < 3
    return total < 4

cur_cnt, tmp_cnt = 0, 0
cur_lv = {1: 0, 2: 0, 3: 0, 4: 0}
for r in rows:
    days = r.get('days') or r.get('use_days')
    total = r.get('sw') or r.get('total_swaps') or 0
    if lf_protected(days, total):
        cur_cnt += 1
        if days is not None:
            if days <= 30:   cur_lv[1] += 1
            elif days <= 45: cur_lv[2] += 1
            elif days <= 60: cur_lv[3] += 1
            else:            cur_lv[4] += 1
    if lf_noprotect(days, total):
        tmp_cnt += 1

print("=" * 56)
print("低频口径对照（基于当前 records.json 的真实活跃母集）")
print("=" * 56)
print(f"数据文件        : {p}")
print(f"活跃协议母集     : {active_total}")
print(f"当前代码低频(≤15保护): {cur_cnt}   <- 看板/名单用的就是这个数")
print(f"临时无保护版低频 : {tmp_cnt}")
print(f"取消保护的增量   : {tmp_cnt - cur_cnt}  （无保护版应更多）")
print(f"当前代码档位分布 : L1={cur_lv[1]} L2={cur_lv[2]} L3={cur_lv[3]} L4={cur_lv[4]}")
print("-" * 56)
print("解读：")
print("  · 当前代码 = 用户指定的 4 条判定（>15天参与，≤15天保护）。")
print("  · 若当前低频({0})仍远小于记忆中的'三千多'，说明 active_total".format(cur_cnt))
print("    比当年小很多——这是数字下跌主因，与统计逻辑无关。")
print("  · 想回升需让 active_total 回到当年量级（确认 status/is_del 是否")
print("    被批量变更），而非调阈值。")
print("=" * 56)
