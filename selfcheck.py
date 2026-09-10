# -*- coding: utf-8 -*-
"""v10.28.30 集大成包 · 逐模块基本功能自检（不连真实DB）"""
import os, sys, io, json, glob, re, subprocess, datetime, importlib

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE); os.chdir(BASE)
R = []
def rec(mod, item, ok, note=''):
    R.append((mod, item, bool(ok), note))
    print(f"  {'✅' if ok else '❌'} {item:<40} {note}")

print("="*80)
print("  集大成包 · 逐模块基本功能自检   v10.28.30   ", datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
print("="*80)

# ---------- 1. 语法编译 ----------
print("\n【模块组 1】Python 源码语法编译")
pys = sorted(f for f in glob.glob('*.py') if f not in ('mock_db.py','run_with_mock.py','selfcheck.py'))
fail = []
for f in pys:
    p = subprocess.run([sys.executable,'-m','py_compile',f], capture_output=True, text=True)
    if p.returncode != 0:
        fail.append((f, (p.stderr or '').strip().splitlines()[-1]))
rec('语法编译', f'{len(pys)} 个 .py 全部编译', not fail,
    '全部通过' if not fail else '; '.join(f'{a}: {b}' for a,b in fail))

# ---------- 2. 依赖库 ----------
print("\n【模块组 2】第三方依赖")
for m in ('pymysql','openpyxl'):
    try:
        importlib.import_module(m); rec('依赖库', m, True, 'OK')
    except Exception as e:
        rec('依赖库', m, False, str(e))

# ---------- 3. should_follow_up 规则引擎 ----------
print("\n【模块组 3】should_follow_up.py · 回访判定规则（单元用例）")
try:
    import should_follow_up as SF
    fn = getattr(SF, 'shouldFollowUp', None)
    rec('规则引擎', 'import should_follow_up', fn is not None, f'入口 shouldFollowUp()')
    cases = [
        ("末次=柜内归还电池 + SN=暂无电池 → False", [{"操作类型":"柜内归还电池","电池SN":"暂无电池"}], False),
        ("末次=柜内借出电池 + SN 有值    → True",  [{"操作类型":"柜内借出电池","电池SN":"SN123"}], True),
        ("末次=柜内归还电池 + SN 有值    → True",  [{"操作类型":"柜内归还电池","电池SN":"SN999"}], True),
        ("末次 SN 字段缺失              → True",  [{"操作类型":"柜内归还电池"}], True),
        ("空历史                        → True",  [], True),
    ]
    for name, hist, exp in cases:
        try:
            got = bool(fn(hist))
            rec('规则引擎', name, got == exp, f'返回={got} 期望={exp}')
        except Exception as e:
            rec('规则引擎', name, False, f'{type(e).__name__}: {e}')
except Exception as e:
    rec('规则引擎', 'import should_follow_up', False, f'{type(e).__name__}: {e}')

# ---------- 4. env.py / 配置 ----------
print("\n【模块组 4】环境 & 配置")
try:
    import env; rec('环境模块', 'import env', True, 'OK')
except Exception as e:
    rec('环境模块', 'import env', False, f'{type(e).__name__}: {e}')
try:
    c = json.load(io.open('db_conf.json',encoding='utf-8'))
    need = ['host','port','user','password','database','lowfreq_thresholds']
    miss = [k for k in need if k not in c]
    rec('配置文件', 'db_conf.json 必需键', not miss, '缺失:'+','.join(miss) if miss else '6/6 齐全')
    rec('配置文件', 'lowfreq 阈值 4 档', len(c.get('lowfreq_thresholds',{}))>=8, f"{len(c.get('lowfreq_thresholds',{}))} 个键")
except Exception as e:
    rec('配置文件', 'db_conf.json', False, str(e))

# ---------- 5. assign.py ----------
print("\n【模块组 5】assign.py · 派单模块")
try:
    import assign
    rec('派单模块', 'import assign', True, 'OK')
    for fn_ in ('run_assignment','load_config','save','load_assignments','sync_rebalance','replace_assignment'):
        rec('派单模块', f'{fn_}()', hasattr(assign,fn_), '存在' if hasattr(assign,fn_) else '缺失')
except Exception as e:
    rec('派单模块', 'import assign', False, f'{type(e).__name__}: {e}')

# ---------- 6. serve.py ----------
print("\n【模块组 6】serve.py · Web 服务")
try:
    import serve
    rec('Web服务', 'import serve', True, 'OK')
    src = io.open('serve.py',encoding='utf-8').read()
    routes = sorted(set(re.findall(r"""path\s*==\s*["'](/api/[^"']+)["']""", src)))
    rec('Web服务', f'/api/* 路由 {len(routes)} 个', len(routes)>=8, ', '.join(routes))
    for r_ in ('/api/force_run','/api/redispatch','/api/assignments','/api/version','/api/login','/api/battery_now'):
        rec('Web服务', r_, r_ in routes, '存在' if r_ in routes else '缺失')
    rec('Web服务', 'importlib.reload 热重载', 'importlib.reload' in src,
        f"{src.count('importlib.reload')} 处")
except Exception as e:
    rec('Web服务', 'import serve', False, f'{type(e).__name__}: {e}')

# ---------- 7. gen_dashboard.py ----------
print("\n【模块组 7】gen_dashboard.py · 看板生成器")
g = io.open('gen_dashboard.py',encoding='utf-8').read()
rec('看板生成', '__DATA__ 注入', "HTML.replace('__DATA__'" in g, 'OK')
rec('看板生成', '__DEFAULT_UPDATE_URL__', '__DEFAULT_UPDATE_URL__' in g, 'OK')
rec('看板生成', '导出全部开关 __EXPORT_ALL__', '__EXPORT_ALL__' in g, f"{g.count('__EXPORT_ALL__')} 处")

# ---------- 8. build_lists.py ----------
print("\n【模块组 8】build_lists.py · 取数模块")
b = io.open('build_lists.py',encoding='utf-8').read()
rec('取数模块', '__VERSION__', True, re.search(r"__VERSION__\s*=\s*'([^']+)'", b).group(1))
rec('取数模块', 'USE_NEED_FOLLOWUP_FILTER 默认关', "c.get('use_need_followup_filter', False)" in b, 'False = 昨日正常口径')
rec('取数模块', '_circ_from_log 修复 (v10.28.30)', '_circ_from_log' in b, 'OK')
rec('取数模块', 'to_ms 兼容 datetime', "hasattr(ts, 'timestamp')" in b, 'OK')
rec('取数模块', 'records 横杠兜底', "_r['pkg'] = '-'" in b, 'OK')

# ---------- 9. 产物 ----------
print("\n【模块组 9】运行产物 out/")
for fn_, minb in (('records.json',1000),('followup_dashboard.html',100000),('assignments.json',10),('回访名单.xlsx',1000)):
    p = os.path.join('out',fn_)
    ok = os.path.exists(p) and os.path.getsize(p)>=minb
    rec('运行产物', fn_, ok, f'{os.path.getsize(p):,} B' if os.path.exists(p) else '不存在')

# ---------- 10. HTML 内容 ----------
print("\n【模块组 10】followup_dashboard.html 内容体检")
h = io.open(os.path.join('out','followup_dashboard.html'),encoding='utf-8').read()
rec('看板内容', '文件大小', True, f'{len(h):,} 字符')
tabs = re.findall(r'<button data-v="([^"]+)"[^>]*>([^<]+)</button>', h)
rec('看板内容', f'Tab 数 {len(tabs)}', len(tabs)>=10,
    ' / '.join(n for _,n in tabs))
must = ['全部活跃协议','欠租催收','低频用户','低频用户数据分析','回访看板','回访排班','回访调度','排班总览','历史排班','无需回访']
miss_t = [t for t in must if t not in [n for _,n in tabs]]
rec('看板内容', '10 个必需 Tab 齐全', not miss_t, '缺失:'+','.join(miss_t) if miss_t else 'OK')
# 分析 Tab 的 7 个筛选维度
anf = re.findall(r'<select id="(filter[A-Za-z]+)"><option[^>]*>([^<]+)</option>', h)
anf = [x for x in anf if x[0] != 'filterAgreementType']
rec('看板内容', f'低频用户数据分析 筛选维度 {len(anf)} 个', len(anf)>=7,
    ', '.join(f'{i}({t})' for i,t in anf))
for kw in ('全部电池产品','全部代理商','全部城市','全部区域','全部街道','全部社区','全部流通季度'):
    rec('看板内容', f'筛选项「{kw}」', kw in h, 'OK' if kw in h else '缺失')
for bid,nm in (('btnCsv','导出当前筛选(名单)'),('btnCsvAll','导出全部(名单)'),
               ('btnAnalysisCsv','导出当前筛选(分析)'),('btnAnalysisCsvAll','导出全部(分析)')):
    rec('看板内容', nm, f'id="{bid}"' in h, 'OK' if f'id="{bid}"' in h else '缺失')
rec('看板内容', '__DATA__ 已替换', '__DATA__' not in h, '无残留占位符')
# 横杠统计（抽样前 5 万字符的可视区，避免把数据区算进来）
head = h[:200000]
rec('看板内容', '模板区无 -- 占位', head.count('>--<') < 5, f'">{head.count(">--<")}" 处')

# ---------- 11. bat 引用 ----------
print("\n【模块组 11】.bat → 目标文件存在性")
for bf in sorted(glob.glob('*.bat')):
    t = io.open(bf,encoding='utf-8',errors='replace').read()
    tg = re.findall(r'(?:python\w*\.exe|python|py)\s+[^\r\n]*?([A-Za-z_][A-Za-z0-9_]*\.py)', t)
    miss = [x for x in set(tg) if not os.path.exists(x)]
    rec('bat完整性', bf, not miss, f'引用 {sorted(set(tg))}' if tg else '无 .py 引用')

# ---------- 12. 关键业务数据（基于本次 Mock 跑出的 records.json）----------
print("\n【模块组 12】业务数据健康度（本次 Mock 跑出结果）")
try:
    d = json.load(io.open(os.path.join('out','records.json'),encoding='utf-8'))
    rows = d.get('rows') or []
    rec('业务数据', 'records 条数', len(rows) > 0, f'{len(rows):,} 条')
    rec('业务数据', '低频用户 > 0', sum(1 for r in rows if r.get('lf')) > 0,
        f"{sum(1 for r in rows if r.get('lf')):,} 条")
    rec('业务数据', '可回访 followable > 0', sum(1 for r in rows if r.get('followable')) > 0,
        f"{sum(1 for r in rows if r.get('followable')):,} 条  ← 名单能否生成的关键")
    rec('业务数据', '欠租催收 > 0', sum(1 for r in rows if r.get('owe')) > 0,
        f"{sum(1 for r in rows if r.get('owe')):,} 条")
    dash = {k: sum(1 for r in rows if str(r.get(k,'')).strip() in ('','-')) for k in ('pkg','vol','cur','dep','soc')}
    worst = max(dash.values())
    rec('业务数据', '关键列横杠率', worst < len(rows)*0.5,
        ' / '.join(f'{k}:{v:,}' for k,v in dash.items()))
except Exception as e:
    rec('业务数据', 'records.json 读取', False, str(e))

# ---------- 汇总 ----------
print("\n" + "="*80)
ok_n = sum(1 for x in R if x[2]); bad_n = len(R)-ok_n
print(f"  自检汇总：通过 {ok_n} 项 ｜ 失败 {bad_n} 项")
if bad_n:
    print("  失败明细：")
    for m,i,ok_,n in R:
        if not ok_: print(f"    ❌ [{m}] {i} -> {n}")
json.dump([{'mod':m,'item':i,'ok':o,'note':n} for m,i,o,n in R],
          io.open(os.path.join('out','selfcheck.json'),'w',encoding='utf-8'), ensure_ascii=False, indent=2)
print("  明细已写出 out/selfcheck.json")
print("="*80)
sys.exit(1 if bad_n else 0)
