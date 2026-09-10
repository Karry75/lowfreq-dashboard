# -*- coding: utf-8 -*-
"""v10.28.26 一键跑通：抽数 + 生成名单（完全 inline，不调 subprocess）。
最关键：脚本一进来就写 out\status.json 第一行 = alive，证明 Python 真的跑起来了。
输出三件套：
  out\\status.json             结构化结果（成功/失败、行数、错误）
  out\\fix_records.stdout.log  完整 stdout
  out\\fix_records.stderr.log  完整 stderr
"""
import os
import sys
import json
import datetime
import traceback
import platform

# Force unbuffered
try:
    sys.stdout.reconfigure(line_buffering=True, encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(line_buffering=True, encoding='utf-8', errors='replace')
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, 'out')
os.makedirs(OUT, exist_ok=True)
ST = os.path.join(OUT, 'status.json')

# === 最重要：脚本一进来就写一行 alive，避免黑窗口空白 ===
status = {
    'version': 'v10.28.38',
    'started_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'python': sys.executable,
    'python_version': platform.python_version(),
    'cwd': os.getcwd(),
    'db_ok': False,
    'records_rows': 0,
    'dashboard_ok': False,
    'assignments_today': 0,
    'followable_count': 0,
    'low_freq_count': 0,
    'error': None,
    'traceback': None,
    'phases': [],   # 各阶段耗时
}


def write_status():
    try:
        with open(ST, 'w', encoding='utf-8') as f:
            json.dump(status, ensure_ascii=False, indent=2)
    except Exception:
        pass


# 立刻写第一份 status，避免空白
write_status()
print('=' * 70)
print(f'  fix_records.py  v10.28.38  (inline, no subprocess)')
print(f'  python {status["python_version"]}  cwd={status["cwd"][-50:]}')
print('=' * 70)


def phase(name):
    """记一个阶段开始时间 + 立即 flush"""
    t0 = datetime.datetime.now()
    status['phases'].append({'name': name, 'start': t0.strftime('%H:%M:%S')})
    write_status()
    print(f'\n[PHASE] {name}  ({t0:%H:%M:%S})')
    return t0


def phase_end(t0, **extra):
    status['phases'][-1].update({
        'end': datetime.datetime.now().strftime('%H:%M:%S'),
        'sec': round((datetime.datetime.now() - t0).total_seconds(), 1),
    })
    status['phases'][-1].update(extra)
    write_status()


try:
    t0 = phase('1.抽数 build_lists.py')
    sys.path.insert(0, BASE)
    import build_lists
    phase_end(t0, ok=True)

    t0 = phase('2.读 records.json')
    rp = os.path.join(OUT, 'records.json')
    if os.path.exists(rp):
        with open(rp, encoding='utf-8') as f:
            d = json.load(f)
        rows = d.get('rows') or []
        status['records_rows'] = len(rows)
        status['followable_count'] = sum(1 for r in rows if r.get('followable'))
        status['low_freq_count'] = sum(1 for r in rows if r.get('lf'))
        print(f'  rows={len(rows)}  followable={status["followable_count"]}  low_freq={status["low_freq_count"]}')
    else:
        print('  [WARN] records.json 不存在')
    phase_end(t0)

    t0 = phase('3.看板 gen_dashboard.py')
    import gen_dashboard
    status['dashboard_ok'] = True
    print('  dashboard.html 已生成')
    phase_end(t0, ok=True)

    t0 = phase('4.生成名单 assign.run_assignment(force)')
    import assign
    today = datetime.date.today().strftime('%Y-%m-%d')
    assign.run_assignment(mode='force', gen_date=today)
    ap = os.path.join(OUT, 'assignments.json')
    if os.path.exists(ap):
        with open(ap, encoding='utf-8') as f:
            ad = json.load(f)
        items = ad.get('items', [])
        n_today = sum(1 for x in items if x.get('created_date') == today)
        status['assignments_today'] = n_today
        print(f'  今日任务 {n_today} 条 | 总任务 {len(items)} 条')
    phase_end(t0, ok=True)

    status['finished_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print('\n' + '=' * 70)
    print('  ALL DONE')
    print('=' * 70)
    print(json.dumps(status, ensure_ascii=False, indent=2))

except SystemExit:
    raise
except Exception as e:
    status['error'] = str(e)
    status['traceback'] = traceback.format_exc()
    status['finished_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print('\n[FAIL]', e)
    print(traceback.format_exc())
    write_status()
    sys.exit(1)
finally:
    write_status()
