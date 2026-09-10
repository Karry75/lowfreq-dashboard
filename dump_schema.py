# -*- coding: utf-8 -*-
"""
表结构 / 字段取值 一键导出（只读，绝不改数据）
=============================================
用途：把线上库的真实表结构、字段非空率、以及 records.json 的候选漏斗
      一次性导出到 out/schema_report.txt，便于定位「页面全是 — / 名单 0 条」。

用法（在看板根目录，双击 dump_schema.bat 或命令行）：
    python -X utf8 dump_schema.py

只读安全：本脚本只执行 SHOW / SELECT COUNT，不做任何 INSERT/UPDATE/DELETE。
输出到文件用 UTF-8；控制台输出用纯 ASCII（避免 GBK cmd 乱码）。
"""

import os
import sys
import json
import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, 'out')
REPORT = os.path.join(OUT, 'schema_report.txt')

# 需要导出的表（按依赖顺序）
TARGET_TABLES = [
    'cb_exchange_agreement',
    'cb_reception_log',
    'cb_battery',
    'cb_battery_status',
    'cb_battery_circulate_log',
    'cb_exchange_order',
    'cb_user',
    'cb_user_mobile',
    'cb_bike_battery_bind_log',
]

SAMPLE_LIMIT = 100000

_lines = []


def w(s=''):
    """写到报告缓冲（UTF-8）"""
    _lines.append(s)
    try:
        # 控制台只输出 ASCII，避免 GBK 乱码
        print(s.encode('ascii', 'replace').decode('ascii'))
    except Exception:
        pass


def hr(title=''):
    w('')
    w('=' * 74)
    if title:
        w('  ' + title)
        w('=' * 74)


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT, exist_ok=True)

    w('# schema_report  (generated %s)' % datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    w('# mode: READ-ONLY  (SHOW / SELECT COUNT only)')

    # ---------- 1. 连接 ----------
    hr('1. CONNECT')
    conf_path = os.path.join(BASE, 'db_conf.json')
    if not os.path.exists(conf_path):
        w('[FAIL] db_conf.json not found at %s' % conf_path)
        flush_report()
        sys.exit(1)
    conf = json.load(open(conf_path, encoding='utf-8'))
    w('  host     : %s' % conf.get('host'))
    w('  port     : %s' % conf.get('port'))
    w('  user     : %s' % conf.get('user'))
    w('  database : %s' % conf.get('database'))
    w('  password : %s' % ('*' * len(str(conf.get('password') or ''))))

    try:
        import pymysql
    except Exception as e:
        w('[FAIL] pymysql not installed: %s' % e)
        w('        run: pip install pymysql')
        flush_report()
        sys.exit(1)

    try:
        conn = pymysql.connect(
            host=conf.get('host'), port=int(conf.get('port') or 3306),
            user=conf.get('user'), password=conf.get('password'),
            database=conf.get('database'), charset='utf8mb4',
            connect_timeout=int(conf.get('connect_timeout') or 30),
            read_timeout=int(conf.get('read_timeout') or 300),
            write_timeout=int(conf.get('write_timeout') or 60),
            cursorclass=pymysql.cursors.DictCursor)
    except Exception as e:
        w('[FAIL] connect error %s: %s' % (type(e).__name__, e))
        w('')
        w('  HINT 2013 -> IP not in ADB whitelist (add this machine public IP)')
        w('  HINT 2003 -> host placeholder / DNS failure')
        w('  HINT 1045 -> wrong user or password')
        w('  HINT 1049 -> database does not exist')
        flush_report()
        sys.exit(1)

    cur = conn.cursor()
    w('[OK] connected')

    # ---------- 2. 表清单 ----------
    hr('2. TABLES IN DATABASE')
    try:
        cur.execute('SHOW TABLES')
        all_tables = [list(r.values())[0] for r in cur.fetchall()]
    except Exception as e:
        w('[FAIL] SHOW TABLES: %s' % e)
        all_tables = []
    w('  total tables: %d' % len(all_tables))
    w('  cb_* tables : %d' % len([t for t in all_tables if str(t).startswith('cb_')]))
    missing = [t for t in TARGET_TABLES if t not in all_tables]
    if missing:
        w('')
        w('  [!!] TARGET TABLES MISSING: %s' % ', '.join(missing))
        near = {}
        for m in missing:
            key = m.replace('cb_', '')[:8]
            near[m] = [t for t in all_tables if key in str(t)][:5]
        for m, cand in near.items():
            w('       %-28s similar: %s' % (m, ', '.join(map(str, cand)) or 'none'))
    else:
        w('  [OK] all %d target tables present' % len(TARGET_TABLES))

    # ---------- 3. 逐表结构 ----------
    hr('3. TABLE SCHEMA + COLUMN FILL RATE')
    for t in TARGET_TABLES:
        if t not in all_tables:
            w('')
            w('--- %s  [TABLE NOT FOUND - SKIPPED]' % t)
            continue
        try:
            cur.execute('SHOW FULL COLUMNS FROM `%s`' % t)
            cols = cur.fetchall()
        except Exception as e:
            w('')
            w('--- %s  [SHOW COLUMNS FAILED: %s]' % (t, e))
            continue

        # 行数
        try:
            cur.execute('SELECT COUNT(*) c FROM `%s`' % t)
            total = (cur.fetchone() or {}).get('c', 0)
        except Exception:
            total = -1

        w('')
        w('--- %s   rows=%s   columns=%d' % (t, total, len(cols)))
        w('    %-30s %-22s %-5s %s' % ('COLUMN', 'TYPE', 'NULL', 'COMMENT'))
        col_names = []
        for c in cols:
            cn = c.get('Field')
            col_names.append(cn)
            w('    %-30s %-22s %-5s %s' % (
                cn, (c.get('Type') or '')[:22],
                'YES' if c.get('Null') == 'YES' else 'NO',
                (c.get('Comment') or '')[:40]))

        # 非空率（采样）
        if total and total > 0:
            w('    -- fill rate (sample %d rows) --' % SAMPLE_LIMIT)
            for cn in col_names:
                try:
                    cur.execute(
                        "SELECT SUM(CASE WHEN `%s` IS NOT NULL AND `%s`<>'' THEN 1 ELSE 0 END) nn, "
                        "COUNT(*) tt FROM (SELECT `%s` FROM `%s` LIMIT %d) s"
                        % (cn, cn, cn, t, SAMPLE_LIMIT))
                    r = cur.fetchone() or {}
                    nn = int(r.get('nn') or 0)
                    tt = int(r.get('tt') or 0)
                    pct = (nn * 100.0 / tt) if tt else 0.0
                    if pct >= 99.5:
                        flag = 'FULL'
                    elif pct >= 50:
                        flag = 'ok'
                    elif nn > 0:
                        flag = 'SPARSE'
                    else:
                        flag = 'EMPTY'
                    w('    %-30s %7d/%-7d %6.1f%%  %s' % (cn, nn, tt, pct, flag))
                except Exception as e:
                    w('    %-30s fill-rate error: %s' % (cn, str(e)[:60]))

    # ---------- 4. 关键关联口径核对 ----------
    hr('4. JOIN KEY SANITY CHECK (does reception.agreement_id match agreement.id?)')
    try:
        if 'cb_reception_log' in all_tables and 'cb_exchange_agreement' in all_tables:
            cur.execute("""
                SELECT COUNT(*) matched FROM (
                    SELECT DISTINCT r.agreement_id FROM cb_reception_log r
                    WHERE r.agreement_id IN (SELECT id FROM cb_exchange_agreement LIMIT 200000)
                    LIMIT 200000
                ) x
            """)
            m = (cur.fetchone() or {}).get('matched', 0)
            w('  distinct reception.agreement_id that EXISTS in agreement.id : %s' % m)

            cur.execute("""
                SELECT COUNT(DISTINCT agreement_id) d FROM (
                    SELECT agreement_id FROM cb_reception_log WHERE agreement_id IS NOT NULL LIMIT 200000
                ) y
            """)
            d = (cur.fetchone() or {}).get('d', 0)
            w('  distinct reception.agreement_id total (sample)             : %s' % d)
            if d:
                w('  ==> match rate: %.1f%%' % (m * 100.0 / d))
                if m * 100.0 / d < 20:
                    w('  [!!] LOW MATCH -> "last reception time/content" will be blank for most rows')
                    w('       the two tables likely use DIFFERENT id semantics')
            w('')
            w('  sample reception rows (latest 3):')
            try:
                cur.execute("SELECT * FROM cb_reception_log ORDER BY create_time DESC LIMIT 3")
                for row in cur.fetchall():
                    w('    ' + json.dumps({k: (str(v)[:40] if v is not None else None)
                                          for k, v in list(row.items())[:12]},
                                         ensure_ascii=False))
            except Exception as e:
                w('    sample failed: %s' % e)
    except Exception as e:
        w('  join check failed: %s' % e)

    # 电池 SN 口径核对
    try:
        if 'cb_battery' in all_tables and 'cb_battery_circulate_log' in all_tables:
            w('')
            w('  battery SN column check:')
            cur.execute('SHOW COLUMNS FROM cb_battery')
            bcols = {c.get('Field') for c in cur.fetchall()}
            w('    cb_battery columns containing "sn": %s'
              % (', '.join(sorted(x for x in bcols if 'sn' in x.lower())) or 'NONE'))
            cur.execute('SHOW COLUMNS FROM cb_battery_circulate_log')
            ccols = {c.get('Field') for c in cur.fetchall()}
            w('    cb_battery_circulate_log columns containing "sn": %s'
              % (', '.join(sorted(x for x in ccols if 'sn' in x.lower())) or 'NONE'))
            w('    cb_battery columns containing "location": %s'
              % (', '.join(sorted(x for x in bcols if 'location' in x.lower())) or 'NONE'))
    except Exception as e:
        w('  battery SN check failed: %s' % e)

    conn.close()

    # ---------- 5. records.json 漏斗 ----------
    hr('5. records.json CANDIDATE FUNNEL')
    rec = os.path.join(OUT, 'records.json')
    if not os.path.exists(rec):
        w('  [SKIP] out/records.json not found (run fix_and_sync.bat first)')
    else:
        try:
            d = json.load(open(rec, encoding='utf-8'))
            rows = d.get('rows') or []
            size = os.path.getsize(rec)
            w('  records.json size: %.1f MB | rows: %d' % (size / 1024.0 / 1024, len(rows)))
            if not rows:
                w('  [!!] rows is EMPTY -> run fix_and_sync.bat to pull data')
            else:
                def cnt(p):
                    return sum(1 for r in rows if p(r))
                n_all = len(rows)
                n_lf = cnt(lambda r: r.get('lf'))
                n_owe = cnt(lambda r: r.get('owe'))
                n_ba = cnt(lambda r: r.get('ba'))
                n_type = cnt(lambda r: r.get('lf') or r.get('owe') or r.get('ba'))
                n_f = cnt(lambda r: r.get('followable'))
                n_nf = cnt(lambda r: r.get('need_followup'))
                n_excl = cnt(lambda r: r.get('excluded'))
                n_tf = cnt(lambda r: (r.get('lf') or r.get('owe') or r.get('ba')) and r.get('followable'))
                n_rcnd = cnt(lambda r: (r.get('lf') or r.get('owe') or r.get('ba'))
                             and r.get('followable') and r.get('rcnd'))
                n_final = n_tf - n_rcnd
                w('  [0] total rows                 : %d' % n_all)
                w('  [1] lf=1 / owe=1 / ba=1        : %d / %d / %d' % (n_lf, n_owe, n_ba))
                w('  [2] type hit (lf|owe|ba)       : %d' % n_type)
                w('  [3] followable=1               : %d' % n_f)
                w('        need_followup=1          : %d' % n_nf)
                w('        excluded non-empty       : %d' % n_excl)
                w('  [4] type hit AND followable    : %d   <-- candidate pool' % n_tf)
                w('  [5] of which rcnd=1 (excluded) : %d' % n_rcnd)
                w('  [6] FINAL can enter today list : %d' % n_final)
                w('  ' + '-' * 60)
                if n_all == 0:
                    w('  ==> BLOCKER: records.json empty. Run fix_and_sync.bat.')
                elif n_type == 0:
                    w('  ==> BLOCKER at [2]: no lf/owe/ba hit. Check lowfreq_thresholds.')
                elif n_f == 0:
                    w('  ==> BLOCKER at [3]: followable all 0.')
                elif n_tf == 0:
                    w('  ==> BLOCKER at [4]: type hit but followable all 0 (mutually exclusive).')
                elif n_final <= 0:
                    w('  ==> BLOCKER at [5]: all candidates filtered by rcnd (recent swap).')
                else:
                    w('  ==> OK: %d candidates available.' % n_final)

                # excluded 原因分布
                reasons = {}
                for r in rows:
                    e = r.get('excluded')
                    if e:
                        key = e if isinstance(e, str) else ';'.join(map(str, e))
                        reasons[key] = reasons.get(key, 0) + 1
                if reasons:
                    w('')
                    w('  top "excluded" reasons:')
                    for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])[:10]:
                        w('    %6d  %s' % (v, k[:90]))

                # 显示字段空值率
                w('')
                w('  display field emptiness (these cause the "dashes" on screen):')
                for k in ('pcity', 'lla', 'llt', 'psrc', 'bsn', 'rt', 'rs', 'rd',
                          'rty', 'rc', 'cloc', 'soc', 'pd', 'ci'):
                    present = sum(1 for r in rows if k in r)
                    empty = sum(1 for r in rows if r.get(k) in (None, '', 0))
                    w('    %-8s present=%-6d empty=%-6d (%s)'
                      % (k, present, empty,
                         ('%.0f%%' % (empty * 100.0 / len(rows))) if rows else '-'))
        except Exception as e:
            w('  [FAIL] parse records.json: %s' % e)

    flush_report()
    try:
        sys.stdout.write('REPORT_WRITTEN:%s' % REPORT)
    except Exception:
        pass


def flush_report():
    try:
        with open(REPORT, 'w', encoding='utf-8') as f:
            f.write('\n'.join(_lines) + '\n')
    except Exception as e:
        print('write report failed: %s' % e)


if __name__ == '__main__':
    main()
