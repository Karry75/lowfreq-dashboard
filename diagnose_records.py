# -*- coding: utf-8 -*-
"""
records.json 诊断 - 只读、不改任何数据
====================================
用于诊断"生成回访名单后 0 条"的根因。双击运行后，
把所有候选数、followable 过滤、近 N 天换电过滤、字段缺失等
以可读形式输出到 out/诊断报告.txt。

使用：在看板根目录 python diagnose_records.py
"""

import sys
import os
import json
import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, 'out')
REC = os.path.join(OUT, 'records.json')
RPT = os.path.join(OUT, '诊断报告.txt')

# Configurable thresholds (mirror v10.28.16 db_conf.json defaults)
RECENT_SWAP_FILTER_DAYS = 15   # build_lists.py RECENT_SWAP_FILTER_DAYS = db_conf.json.recent_swap_filter_days
DEFAULT_RECALL_COOLDOWN_DAYS = 5  # assign.py recall_cooldown_days default
today = datetime.date.today()


def load_staff():
    p = os.path.join(OUT, 'staff.json')
    if not os.path.exists(p):
        return []
    try:
        d = json.load(open(p, encoding='utf-8'))
        return [s.get('name') for s in d if s.get('name')]
    except Exception as e:
        return [f'[parse err: {e}]']


def parse_visited_at(s):
    if not s: return None
    s = str(s).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d'):
        try:
            return datetime.datetime.strptime(s, fmt)
        except Exception:
            continue
    return None


def main():
    lines = []
    lines.append('=' * 60)
    lines.append('  records.json 诊断报告  (gen: ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ')')
    lines.append('=' * 60)
    lines.append('')

    if not os.path.exists(REC):
        lines.append('[FAIL] records.json 不存在。')
        lines.append('       请先双击 fix_and_sync.bat 抽数。')
        open(RPT, 'w', encoding='utf-8').write('\n'.join(lines))
        print('\n'.join(lines))
        sys.exit(1)

    size = os.path.getsize(REC)
    lines.append(f'文件: {REC}')
    lines.append(f'大小: {size/1024/1024:.1f} MB')
    lines.append('')

    try:
        d = json.load(open(REC, encoding='utf-8'))
    except Exception as e:
        lines.append(f'[FAIL] JSON 解析失败: {e}')
        open(RPT, 'w', encoding='utf-8').write('\n'.join(lines))
        print('\n'.join(lines))
        sys.exit(1)

    # 1. 顶层
    lines.append('[1] 顶层 keys:')
    for k in d.keys():
        v = d[k]
        if isinstance(v, list):
            lines.append(f'    {k}: list, len={len(v)}')
        else:
            lines.append(f'    {k}: {repr(v)[:80]}')
    lines.append('')

    rows = d.get('rows') or []
    lines.append(f'[2] rows 总数: {len(rows)}')
    if not rows:
        lines.append('[FAIL] rows 为空，无法生成名单。')
        open(RPT, 'w', encoding='utf-8').write('\n'.join(lines))
        print('\n'.join(lines))
        sys.exit(1)

    # 2. 字段完整性
    keys_set = set()
    for r in rows:
        keys_set.update(r.keys())
    lines.append(f'[3] rows 中出现的所有字段: {len(keys_set)} 个')
    must_have = ['id', 'lf', 'owe', 'followable', 'rcnd', 'pd', 'soc', 'pcity', 'lla', 'bsn', 'rt', 'rs']
    lines.append('    关键字段缺失检查:')
    for k in must_have:
        present = k in keys_set
        null_count = sum(1 for r in rows if r.get(k) in (None, ''))
        lines.append(f'      {k:<14} present={present}  null_or_empty={null_count}/{len(rows)}')
    lines.append('')

    # 3. 候选分析
    n_total = len(rows)
    n_lf = sum(1 for r in rows if r.get('lf'))
    n_owe = sum(1 for r in rows if r.get('owe'))
    n_ba = sum(1 for r in rows if r.get('ba'))
    n_followable = sum(1 for r in rows if r.get('followable'))
    n_lf_or_ba = sum(1 for r in rows if (r.get('lf') or r.get('ba')))
    n_candidate = sum(1 for r in rows if (r.get('lf') or r.get('ba')) and r.get('followable'))
    n_rcnd = sum(1 for r in rows if r.get('rcnd'))
    n_after_rcnd = sum(1 for r in rows if (r.get('lf') or r.get('ba')) and r.get('followable') and not r.get('rcnd'))
    lines.append('[4] 候选协议统计:')
    lines.append(f'    总 rows                : {n_total}')
    lines.append(f'    lf=1 (低频)            : {n_lf}')
    lines.append(f'    owe=1 (欠租)           : {n_owe}')
    lines.append(f'    ba=1 (电池异常)        : {n_ba}')
    lines.append(f'    followable=1           : {n_followable}')
    lines.append(f'    (lf|ba) AND followable : {n_candidate}   <-- assign.py 候选基数')
    lines.append(f'    rcnd=1 (近15天换电)    : {n_rcnd}')
    lines.append(f'    排除近15天换电后候选   : {n_after_rcnd}')
    lines.append('')

    # 4. 接待人员 vs 配置
    staff = load_staff()
    lines.append(f'[5] 接待人员 (out/staff.json): {staff}')
    if '史苏梅' in staff:
        lines.append('    (含 史苏梅 / 邓志远 / 王日威 / 胡选顿 / 陈名锡 / 黄连霞 / 华平平 / 黄凯琦)')
    lines.append('')

    # 5. 字段为空的占比
    lines.append('[6] 关键显示字段（前端"——"即此字段为 None 或空）:')
    fields_display = ['pcity', 'lla', 'llt', 'psrc', 'bsn', 'rt', 'rs', 'rd', 'rty', 'rc', 'tags', 'ln', 'pr', 'dpw']
    for f in fields_display:
        if f in keys_set:
            null_count = sum(1 for r in rows if r.get(f) in (None, '', [], {}))
            pct = null_count * 100 / max(1, len(rows))
            lines.append(f'    {f:<8} null/empty = {null_count}/{len(rows)} ({pct:.1f}%)')
        else:
            lines.append(f'    {f:<8} 字段完全不存在（schema 缺失）')
    lines.append('')

    # 6. 结论
    lines.append('=' * 60)
    lines.append('  诊断结论:')
    lines.append('=' * 60)
    if n_candidate == 0:
        lines.append('  [BAD] 候选基数 = 0：assign.py 跑不出名单是必然的。')
        if n_lf + n_owe + n_ba == 0:
            lines.append('         rows 中 lf/owe/ba 全部为 0，')
            lines.append('         说明 build_lists.py 没有把"低频"标出来。')
            lines.append('         可能原因：抽数时间过早 / SQL WHERE 条件 / is_del=0 过滤太严')
        elif n_followable == 0:
            lines.append('         followable 全为 0：所有候选被 build_lists.py 标记为"不可回访"')
            lines.append('         常见原因：流通异常 / 柜内归还无电池 / 空号 / 退订等')
        else:
            lines.append('         有候选但被过滤掉了，见上面 [4] 段。')
    elif n_after_rcnd < 5:
        lines.append(f'  [WARN] 排除近 {RECENT_SWAP_FILTER_DAYS} 天换电后仅剩 {n_after_rcnd} 条候选。')
        lines.append(f'         如果 {RECENT_SWAP_FILTER_DAYS} 天内大部分协议都换过电，可考虑')
        lines.append('         把 db_conf.json 的 recent_swap_filter_days 调小或设为 0')
    else:
        lines.append(f'  [OK] 候选 {n_after_rcnd} 条足够生成名单。')
        lines.append('       如果还出 0 条，问题在：active_staff 不匹配 / quota 太小 / cooldown 窗口')
    lines.append('')
    lines.append('  接下来:')
    lines.append('    1) 把本文件 out\\诊断报告.txt 整份发给我')
    lines.append('    2) 我能精准告诉你"为什么 0 条" + 修法')
    lines.append('=' * 60)

    open(RPT, 'w', encoding='utf-8').write('\n'.join(lines))

    # 同时打印到屏幕
    print('\n'.join(lines))
    print(f'\n[OK] 报告已保存: {RPT}')
    print('     请把这个文件发给我。')


if __name__ == '__main__':
    main()
