"""
用 Mock DB 模拟用户环境，真实跑 fix_records.py 的核心三步：
1) build_lists.py → out/records.json
2) gen_dashboard.py → out/followup_dashboard.html
3) assign.run_assignment(force) → out/assignments.json

验证：低频用户不为 0、followable 不为 0、KeyError 不再出现
"""
import sys, os, json, datetime
sys.path.insert(0, '/tmp/audit')

# 拦截 pymysql.connect：返回 MockConn
import pymysql
import mock_db
pymysql.connect = lambda **kw: mock_db.MockConn()

# 关键：env.py 也会调 connect，先 patch 它
import env
env.connect = lambda: mock_db.MockConn()

# 同样 patch build_lists 和 assign
import build_lists
build_lists.connect = lambda: mock_db.MockConn()
import assign
assign.connect = lambda: mock_db.MockConn()

print('=' * 70)
print('  v10.28.28 集大成包 · 沙箱端到端验证（Mock DB 模式）')
print('=' * 70)

# ---- STEP 1: build_lists ----
print('\n[STEP 1/3] build_lists.py (抽数 + 低频判定)')
import io
import contextlib
buf = io.StringIO()
try:
    with contextlib.redirect_stdout(buf):
        build_lists.main() if hasattr(build_lists, 'main') else exec(open('build_lists.py').read())
    print('  exit: 0')
except SystemExit as e:
    print(f'  exit: {e.code}')
except Exception as e:
    import traceback
    print(f'  ❌ EXCEPTION: {type(e).__name__}: {e}')
    print(traceback.format_exc()[-1500:])

# 关键指标
rp = 'out/records.json'
if os.path.exists(rp):
    d = json.load(open(rp, encoding='utf-8'))
    rows = d.get('rows', [])
    n_followable = sum(1 for r in rows if r.get('followable'))
    n_lf = sum(1 for r in rows if r.get('lf'))
    n_owe = sum(1 for r in rows if r.get('owe'))
    n_bsn = sum(1 for r in rows if r.get('bsn', '').strip())
    print(f'  📊 records 总数: {len(rows)}')
    print(f'  📊 低频用户: {n_lf} | 欠租: {n_owe} | followable: {n_followable} | bsn非空: {n_bsn}')
    if n_lf > 0:
        print('  ✅ 低频用户判定正确（>0）')
    else:
        print('  ❌ 低频用户判定为 0 ← v10.28.17 真凶可能没修')
    if n_followable > 0:
        print('  ✅ followable 不为 0，回访名单能生成')
    else:
        print('  ❌ followable=0 ← 名单会空')

# ---- STEP 2: gen_dashboard ----
print('\n[STEP 2/3] gen_dashboard.py (看板渲染)')
buf2 = io.StringIO()
try:
    with contextlib.redirect_stdout(buf2):
        gen_dashboard_mod = exec(open('gen_dashboard.py').read())
    print('  exit: 0')
except SystemExit as e:
    print(f'  exit: {e.code}')
except Exception as e:
    import traceback
    print(f'  ❌ EXCEPTION: {type(e).__name__}: {e}')

hp = 'out/followup_dashboard.html'
if os.path.exists(hp):
    sz = os.path.getsize(hp)
    print(f'  📊 dashboard.html: {sz} 字节')
    html = open(hp, encoding='utf-8').read()
    has_7_filters = all(k in html for k in ['协议ID', '电池产品', '协议状态', '协议类型', '是否低频', '档位', '手机号'])
    has_export_all = 'btnCsvAll' in html and 'btnAnalysisCsvAll' in html
    has_low_freq_tab = 'data-v="lf"' in html or '低频用户' in html
    has_analysis_tab = 'data-v="analysis"' in html or '低频用户数据分析' in html
    print(f'  📊 7 个筛选维度: {"✅" if has_7_filters else "❌"}')
    print(f'  📊 导出全部按钮: {"✅" if has_export_all else "❌"}')
    print(f'  📊 低频用户 Tab: {"✅" if has_low_freq_tab else "❌"}')
    print(f'  📊 数据分析 Tab: {"✅" if has_analysis_tab else "❌"}')

# ---- STEP 3: assign ----
print('\n[STEP 3/3] assign.run_assignment(force) (生成回访名单)')
ap = 'out/assignments.json'
if os.path.exists(ap):
    os.remove(ap)
buf3 = io.StringIO()
try:
    with contextlib.redirect_stdout(buf3):
        assign.run_assignment(mode='force', gen_date='2026-08-28')
    print('  exit: 0')
except SystemExit as e:
    print(f'  exit: {e.code}')
except Exception as e:
    import traceback
    print(f'  ❌ EXCEPTION: {type(e).__name__}: {e}')

if os.path.exists(ap):
    ad = json.load(open(ap, encoding='utf-8'))
    items = ad.get('items', [])
    n_today = sum(1 for x in items if x.get('created_date') == '2026-08-28')
    print(f'  📊 assignments.json items: {len(items)}')
    print(f'  📊 今日任务: {n_today}')
    if n_today > 0:
        print('  ✅ 今日回访名单生成成功')
    else:
        print('  ❌ 今日任务为 0')

# ---- 总结 ----
print('\n' + '=' * 70)
print('  验证总结')
print('=' * 70)
