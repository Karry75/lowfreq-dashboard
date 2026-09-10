# -*- coding: utf-8 -*-
"""
一键生成回访名单（独立入口）
============================
背景：
  v10.28.16 起，fix_and_sync.py 不再自动调用 assign.py（设计上让用户在
  UI「回访排班」页选人员+配额后点「生成回访名单」按钮触发）。

  本脚本为不点 UI 的用户（脚本化运维、定时任务）提供等价入口：
    · 默认生成今日（2026-08-28 之类）回访名单
    · 自动套用 active_staff_quota 默认值：华平平=30 / 黄连霞=30（与 UI 默认一致）
    · 调 assign.py::run_assignment('force')

使用（在看板根目录）：
    python gen_assignments.py                  # 默认生成今天的名单
    python gen_assignments.py --date 2026-08-28
    python gen_assignments.py --solvers 华平平:30 黄连霞:20
"""

import sys
import os
import json
import datetime
import argparse

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, 'out')

# 与 UI「回访排班」默认配额对齐：只勾华平平/黄连霞，每人 30 条
DEFAULT_QUOTA = {'华平平': 30, '黄连霞': 30}

# Pinyin alias map (for users with command-line encoding pain)
ALIAS = {
    'huapingping': '华平平',
    'huangpingping': '黄平平',  # 兼容输入习惯
    'hulianxia': '黄连霞',
    'huangxialian': '黄连霞',
}


def today():
    return datetime.datetime.now().strftime('%Y-%m-%d')


def log(msg):
    print(msg)
    sys.stdout.flush()


def patch_today_staff(quota):
    """把接待人+配额写入 out/today_staff.json，给 assign.py 读。

    assign.py 通过 cfg.get('today_staff') 取今日排班人员。
    我们直接覆盖 staff.json 里的 quota 字段，确保 run_assignment 拿到对的数。
    """
    if not quota:
        return
    staff_file = os.path.join(OUT, 'staff.json')
    if not os.path.exists(staff_file):
        log(f'[WARN] {staff_file} 不存在，跳过 quota 写入（assign 会用回退默认）')
        return
    try:
        with open(staff_file, encoding='utf-8') as f:
            cfg = json.load(f)

        # v10.28.19 BUGFIX：staff.json 是 dict {staff:[...], daily_quota:N, quotas:{}, today_staff:[]}，
        # 旧代码把它当「数组」遍历 → for s in dict 拿到的是 key 字符串 → s.get('name') 抛
        # AttributeError → 被 except 吞掉 → 配额与今日排班根本没写进去（只留一行 WARN）。
        if isinstance(cfg, dict):
            cfg['staff'] = list(cfg.get('staff') or [])
            cfg['quotas'] = dict(cfg.get('quotas') or {})
            for name, q in quota.items():
                if name not in cfg['staff']:
                    cfg['staff'].append(name)
                cfg['quotas'][name] = q
            # 其余人员配额归零，确保只给指定的人分配
            for s in cfg['staff']:
                cfg['quotas'].setdefault(s, 0)
            cfg['today_staff'] = list(quota.keys())
        else:
            # 兜底：万一真是数组形态
            cfg = [{'name': n, 'daily_quota': quota.get(n, 0)} for n in (quota.keys())]

        with open(staff_file, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
        log(f'[OK] staff.json updated | today_staff={list(quota.keys())} | quotas={quota}')
    except Exception as e:
        log(f'[WARN] quota write failed (non-fatal): {e}')
        import traceback
        traceback.print_exc()


def funnel_report(rows, quota, gen_date):
    """v10.28.18：四层过滤漏斗诊断。

    assign.py 生成名单时依次套 4 道过滤，任何一道归零都会导致「名单 0 条」，
    而原日志只打印最终候选数，看不出卡在哪一层。这里把每一层单独算一遍，
    一眼定位：是低频判定(lf)、可回访标记(followable)、近N天换电(rcnd)，
    还是已分配/冷却窗口把人吃掉了。
    """
    if not rows:
        log('[FUNNEL] records.json 里没有任何行，无法诊断')
        return

    def cnt(pred):
        return sum(1 for r in rows if pred(r))

    log('')
    log('=' * 62)
    log('  候选漏斗诊断 (v10.28.18) —— 定位「名单 0 条」卡在哪一层')
    log('=' * 62)

    n_all = len(rows)
    n_lf = cnt(lambda r: r.get('lf'))
    n_owe = cnt(lambda r: r.get('owe'))
    n_ba = cnt(lambda r: r.get('ba'))
    n_type = cnt(lambda r: r.get('lf') or r.get('owe') or r.get('ba'))
    n_followable = cnt(lambda r: r.get('followable'))
    n_type_and_f = cnt(lambda r: (r.get('lf') or r.get('owe') or r.get('ba')) and r.get('followable'))
    n_excl = cnt(lambda r: r.get('excluded'))
    n_nf = cnt(lambda r: r.get('need_followup'))
    n_rcnd = cnt(lambda r: r.get('rcnd'))

    # [6] 历史任务排除（v10.28.19 前这里是「永久排除」，是名单为 0 的头号原因）
    asg_file = os.path.join(OUT, 'assignments.json')
    n_asg_total = n_asg_pending = 0
    asg_aids = set()
    if os.path.exists(asg_file):
        try:
            _a = json.load(open(asg_file, encoding='utf-8'))
            _it = _a.get('items', [])
            n_asg_total = len(_it)
            n_asg_pending = sum(1 for x in _it if x.get('status') == '待回访')
            asg_aids = set(x.get('agreement_id') for x in _it if x.get('agreement_id') is not None)
        except Exception:
            pass
    n_pool = cnt(lambda r: (r.get('lf') or r.get('owe') or r.get('ba'))
                 and r.get('followable') and not r.get('rcnd'))
    n_after_assigned = sum(1 for r in rows
                           if (r.get('lf') or r.get('owe') or r.get('ba'))
                           and r.get('followable') and not r.get('rcnd')
                           and r.get('id') not in asg_aids)

    log(f'  [0] records.json 总行数              : {n_all}')
    log(f'  [1] 低频 lf=1                        : {n_lf}')
    log(f'      欠租 owe=1                       : {n_owe}')
    log(f'      电池异常 ba=1                    : {n_ba}')
    log(f'  [2] 类型命中(lf|owe|ba)              : {n_type}')
    log(f'  [3] followable=1                     : {n_followable}')
    log(f'      其中 need_followup=1             : {n_nf}')
    log(f'      被剔除原因 excluded 非空         : {n_excl}')
    log(f'  [4] 类型命中 且 followable           : {n_type_and_f}   <<< assign.py 的候选池')
    log(f'  [5] 其中 近N天换过电 rcnd=1(将被排除): {n_rcnd}')
    log(f'  [6] 过滤 rcnd 后候选池               : {n_pool}')
    log(f'  [7] assignments.json 历史任务        : {n_asg_total} 条（其中待回访 {n_asg_pending} 条）')
    log(f'      历史任务覆盖的协议ID去重         : {len(asg_aids)} 个')
    log(f'  [8] 扣掉历史任务后可分配             : {n_after_assigned}   <<< v10.28.19 前这一步会归零')

    # 定位结论
    log('  ' + '-' * 58)
    if n_all == 0:
        log('  >> 结论：records.json 是空的，请先跑 fix_and_sync.bat 抽数')
    elif n_type == 0:
        log('  >> 结论：卡在第[2]层——低频/欠租/电池异常一个都没命中')
        log('     检查 db_conf.json 的 lowfreq_thresholds 与 recent_swap_filter_days')
    elif n_followable == 0:
        log('  >> 结论：卡在第[3]层——followable 全为 0')
        log('     即 is_lf、excluded、need_followup 三道里至少一道把所有人否掉了')
    elif n_type_and_f == 0:
        log('  >> 结论：卡在第[4]层——类型命中的人 followable 都是 0')
        log('     说明低频判定与可回访判定口径互斥，需核对 excluded 的具体原因')
    elif n_type_and_f - n_rcnd <= 0:
        log('  >> 结论：卡在第[5]层——候选全被「近N天换过电」(rcnd) 排除了')
        log('     可调大 db_conf.json 的 recent_swap_filter_days，或改成生成后过滤')
    elif n_after_assigned <= 0:
        log('  >> 结论：卡在第[8]层——候选池本有 %d 条，但被历史任务全部吃掉了' % n_pool)
        log('     这正是「名单恒为 0」的头号原因：v10.28.19 之前，一个协议只要')
        log('     被分配过一次就永久不再进名单，低频用户池固定，跑几次就被吃光。')
        log('     >> v10.28.19 已修复：只排除「仍待回访」+「冷却期内已回访」的，')
        log('        已过冷却期的允许重新进入名单。重新跑一次即可。')
        if n_asg_pending > 0:
            log('     若仍为 0，说明历史里有 %d 条「待回访」未消化，可加 --reset 清空重来。' % n_asg_pending)
    else:
        cap = sum(quota.values()) if quota else 0
        log(f'  >> 结论：候选池有 {n_after_assigned} 条，配额上限 {cap} 条')
        if cap <= 0:
            log('     警告：配额为 0，请检查 --solvers 参数或 staff.json 的 daily_quota')
    log('=' * 62)
    log('')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', default=today(), help='生成哪天（YYYY-MM-DD），默认今天')
    parser.add_argument('--solvers', nargs='*',
                        help='指定排班人员+配额，如 华平平:30 黄连霞:20；不传则用 DEFAULT_QUOTA')
    parser.add_argument('--reset', action='store_true',
                        help='清空 assignments.json 全部历史任务后重新生成（历史「待回访」堆积导致名单为 0 时用）')
    args = parser.parse_args()

    # 解析 --solvers
    quota = {}
    if args.solvers:
        for kv in args.solvers:
            if ':' in kv:
                k, v = kv.split(':', 1)
                try:
                    qv = int(v)
                except ValueError:
                    qv = 30
            else:
                k = kv
                qv = 30
            # Pinyin alias -> Chinese name
            k_cn = ALIAS.get(k.lower(), k)
            quota[k_cn] = qv
    else:
        quota = dict(DEFAULT_QUOTA)

    log('============================================================')
    log('  gen_assignments')
    log(f'  date: {args.date}')
    log(f'  solvers: {quota}')
    log('============================================================')

    # 1) 前置检查：records.json
    rec_file = os.path.join(OUT, 'records.json')
    if not os.path.exists(rec_file):
        log(f'[FAIL] {rec_file} missing. Run fix_and_sync.bat first.')
        sys.exit(1)
    size = os.path.getsize(rec_file)
    if size < 100:
        log(f'[FAIL] records.json is empty shell ({size} bytes). Run fix_and_sync.bat first.')
        sys.exit(1)
    log(f'[OK] records.json ready ({size/1024/1024:.1f} MB)')

    # 1.5) v10.28.18：先跑一遍漏斗诊断，名单为 0 时直接定位卡在哪一层
    try:
        _d = json.load(open(rec_file, encoding='utf-8'))
        funnel_report(_d.get('rows') or [], quota, args.date)
    except Exception as _fe:
        log(f'[WARN] funnel diagnosis skipped: {_fe}')

    # 2) 写 quota 到 staff.json
    patch_today_staff(quota)

    # 3) 加载 assign，跑 run_assignment
    try:
        sys.path.insert(0, BASE)
        from assign import run_assignment
    except ImportError as e:
        log(f'[FAIL] import assign.py failed: {e}')
        sys.exit(1)

    # v10.28.19：--reset 清空历史任务（历史「待回访」堆积会吃掉全部候选）
    if args.reset:
        asg_file = os.path.join(OUT, 'assignments.json')
        bak = None
        if os.path.exists(asg_file):
            bak = asg_file + '.bak_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            try:
                import shutil
                shutil.copy2(asg_file, bak)
                json.dump({'items': []}, open(asg_file, 'w', encoding='utf-8'),
                          ensure_ascii=False, indent=1)
                log(f'[RESET] assignments.json cleared. backup -> {os.path.basename(bak)}')
            except Exception as e:
                log(f'[WARN] reset failed: {e}')
        else:
            log('[RESET] assignments.json not found, nothing to clear')

    log('--- calling assign.run_assignment(mode="force") ---')
    try:
        run_assignment(mode='force', gen_date=args.date)
    except Exception as e:
        log(f'[FAIL] run_assignment error: {e}')
        sys.exit(2)

    # 4) 看一眼 out/assignments.json
    asg_file = os.path.join(OUT, 'assignments.json')
    if os.path.exists(asg_file):
        try:
            d = json.load(open(asg_file, encoding='utf-8'))
            n = len(d.get('items', []))
            log(f'  -> {n} visit tasks generated for {args.date} -> {asg_file}')
        except Exception:
            log('  -> assignments.json generated but parse failed')
    else:
        log('  [WARN] assignments.json NOT produced. Check assign output above.')

    log('--- done ---')


if __name__ == '__main__':
    main()
