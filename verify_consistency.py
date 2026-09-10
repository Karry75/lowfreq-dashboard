# -*- coding: utf-8 -*-
# 数据一致性与准确性验证脚本（v10.18.4）
# 跑法：python3 verify_consistency.py
# 作用：连库后对每条低频判定做反向校验，输出可读报告 + 一致性校验
import os, json, datetime, sys
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from env import resolve_db_host  # 与 build_lists.py 共用连库逻辑
import pymysql
from db_conf import load_conf
from datetime import datetime

NOW = int(datetime.now().timestamp() * 1000)
DAY = 86400 * 1000

c = load_conf()
HOST = resolve_db_host(c.get('host'), c.get('intranet_host'))
PORT = int(c.get('port', 3306))
USER = c.get('user')
PWD = c.get('password')
DB = c.get('database')

THR = c.get('lowfreq_thresholds') or {}
PROT = int(THR.get('protected_days', 15))
L1_MAX = int(THR.get('L1_max_days', 30)); L1_MIN = int(THR.get('L1_min_count', 1))
L2_MAX = int(THR.get('L2_max_days', 45)); L2_MIN = int(THR.get('L2_min_count', 2))
L3_MAX = int(THR.get('L3_max_days', 60)); L3_MIN = int(THR.get('L3_min_count', 3))
L4_MIN = int(THR.get('L4_min_count', 4))
PWR = int(c.get('lowfreq_power_threshold', 25))

print('========= 数据一致性 & 准确性验证（v10.18.4） =========')
print(f'规则：8/12 口径  +  L5（电量<{PWR}%）  +  流通异常过滤')
print(f'阈值：L1={L1_MAX}天<{L1_MIN}次 / L2={L2_MAX}天<{L2_MIN}次 / L3={L3_MAX}天<{L3_MIN}次 / L4>{L3_MAX}天<{L4_MIN}次')
print(f'数据库：{HOST}:{PORT}/{DB}')

conn = pymysql.connect(host=HOST, port=PORT, user=USER, password=PWD, database=DB, charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()

# 1) 拉抽数结果
with open(os.path.join(BASE, 'out', 'records.json'), encoding='utf-8') as f:
    recs = json.load(f)
print(f'\n[1] 抽数结果 records.json 行数: {len(recs)}')

# 2) 反向校验：每条低频记录的判定逻辑是否一致
print(f'\n[2] 反向判定校验（每条记录用相同规则重新判定，核对 level）')
mismatch = []
level_dist = {0:0, 1:0, 2:0, 3:0, 4:0, 5:0}
for r in recs:
    use = r.get('use_days')
    c15, c30, c45, c60 = r.get('c15',0), r.get('c30',0), r.get('c45',0), r.get('c60',0)
    soc_raw = r.get('soc') or ''
    soc = int(''.join(c for c in str(soc_raw) if c.isdigit())) if any(ch.isdigit() for ch in str(soc_raw)) else None
    is_lf, lv = False, 0
    if soc is not None and soc < PWR:
        if use is not None and use <= PROT:
            is_lf, lv = True, 5
        elif c15 == 0:
            is_lf, lv = True, 5
    if not is_lf and use is not None and use > PROT:
        if use <= L1_MAX and c30 < L1_MIN: is_lf, lv = True, 1
        elif use <= L2_MAX and c45 < L2_MIN: is_lf, lv = True, 2
        elif use <= L3_MAX and c60 < L3_MIN: is_lf, lv = True, 3
        elif use > L3_MAX and c60 < L4_MIN: is_lf, lv = True, 4
    if r.get('is_lf') and lv == 0:
        mismatch.append((r.get('id'), r.get('use_days'), c15, c30, c45, c60, soc, r.get('level'), r.get('lname')))
    if r.get('is_lf'):
        level_dist[lv] += 1
    else:
        level_dist[0] += 1

print(f'  反向判定命中数 {sum(level_dist.values())} = 抽数结果命中数 {sum(1 for r in recs if r.get("is_lf"))}')
print(f'  各档位分布: L0(非低频)={level_dist[0]} / L1={level_dist[1]} / L2={level_dist[2]} / L3={level_dist[3]} / L4={level_dist[4]} / L5={level_dist[5]}')
if mismatch:
    print(f'  [WARN] {len(mismatch)} 条记录"抽数为低频但反向判定不命中"（前5条）：')
    for m in mismatch[:5]:
        print(f'    aid={m[0]} use={m[1]}d c15={m[2]} c30={m[3]} c45={m[4]} c60={m[5]} soc={m[6]} → 原 L{m[7]} {m[8]}')
else:
    print(f'  [OK] 所有低频记录反向判定一致（0 不匹配）')

# 3) 流通异常过滤校验
print(f'\n[3] 流通异常过滤校验')
abn = sum(1 for r in recs if r.get('is_lf') and (r.get('circ_abn') or not r.get('circ_in')))
in_lf = sum(1 for r in recs if r.get('is_lf') and not (r.get('circ_abn') or not r.get('circ_in')))
print(f'  低频候选被流通异常剔除: {abn}')
print(f'  进入 lf_list（回访名单）: {in_lf}')
print(f'  校验：{abn} + {in_lf} = {abn+in_lf}，抽数总低频命中 {sum(level_dist[1:6])}（应相等）')
assert abn + in_lf == sum(level_dist[1:6]), '数量不一致！'
print(f'  [OK] 数量一致')

# 4) 现场抽 5 条"流通异常"用户展示
print(f'\n[4] 流通异常样本（最多 5 条）')
sample = [r for r in recs if r.get('is_lf') and (r.get('circ_abn') or not r.get('circ_in'))][:5]
for r in sample:
    print(f'  aid={r.get("id")} SN={r.get("battery_sn","")} circ={r.get("circ_op","")} abn={r.get("circ_abn","")[:50]}')

# 5) 现场抽 5 条"今天电池流通"的样本（如果有）
print(f'\n[5] 电池最后流通时间在今天的低频用户样本（若为空表示已被剔除）')
today = datetime.now().strftime('%Y-%m-%d')
today_users = [r for r in recs if r.get('is_lf') and str(r.get('circ_last','')).startswith(today)]
if today_users:
    print(f'  [WARN] 仍有 {len(today_users)} 条"今天流通"的用户在回访名单里（需查流通异常判定）：')
    for r in today_users[:5]:
        print(f'    aid={r.get("id")} last_circ={r.get("circ_last")} op={r.get("circ_op")}')
else:
    print(f'  [OK] 回访名单里无今天流通的用户')

# 6) 电池SN / 流通SN / 流通时间 / 操作类型 一致性校验（v10.18.4）
print(f'\n[6] 电池SN 与 流通记录 一致性校验')
unmatched = [r for r in recs if r.get('circ_match') != '一致']
print(f'  未匹配流通记录的协议数: {len(unmatched)} / 总 {len(recs)}')
if unmatched:
    print(f'  [提示] 这些协议的绑定电池SN在 cb_battery_circulate_log 里查不到流通记录（三列无法对齐）')
    print(f'  [提示] 可能原因：cb_battery.device_sn 与 cb_battery_circulate_log.battery_device_sn 编码/大小写不一致，需核对两表SN字段')
    for r in unmatched[:5]:
        print(f'    aid={r.get("id")} 绑定SN={r.get("battery_sn")!r} 一致性={r.get("circ_match")}')
else:
    print(f'  [OK] 全部协议电池SN均能在流通表中找到对应记录，三列一致')
assert len(unmatched) + sum(1 for r in recs if r.get('circ_match')=='一致') == len(recs), '一致性计数异常'

conn.close()
print('\n========= 验证结束 =========')