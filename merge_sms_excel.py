# -*- coding: utf-8 -*-
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
# 把两份短信发送记录Excel(按手机号)合并进 records.json
import openpyxl, json, os, re
BASE = os.path.dirname(os.path.abspath(__file__))
XLSX_DIR = os.path.join(BASE, 'uploads_sms')

def norm_ph(p):
    if not p: return ''
    s = re.sub(r'\D', '', str(p))          # 去非数字
    if s.startswith('86') and len(s) > 11:  # 去掉国家码86
        s = s[2:]
    return s

def load_xlsx(path):
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    hdr = [str(h).strip() for h in rows[0]]
    idx_ph = hdr.index('手机号码')
    idx_t  = hdr.index('接收时间') if '接收时间' in hdr else None
    idx_r  = hdr.index('发送结果') if '发送结果' in hdr else None
    idx_f  = hdr.index('失败原因') if '失败原因' in hdr else None
    out = {}
    for r in rows[1:]:
        if not r or r[idx_ph] is None: continue
        ph = norm_ph(r[idx_ph])
        if not ph: continue
        res = str(r[idx_r]).strip() if idx_r is not None and r[idx_r] is not None else ''
        fail= str(r[idx_f]).strip() if idx_f is not None and r[idx_f] is not None else ''
        t   = str(r[idx_t]).strip() if idx_t is not None and r[idx_t] is not None else ''
        out[ph] = {'smsr': res, 'smsf': fail, 'smst': t}
    return out

# 先加载较早的(7-29)，再用较晚的(8-12)覆盖 -> 重复号取最新
p1 = os.path.join(XLSX_DIR, 'export1.xlsx')
p2 = os.path.join(XLSX_DIR, 'export2.xlsx')
if not (os.path.exists(p1) and os.path.exists(p2)):
    print('[WARN] 未找到短信Excel：请将两份导出的短信记录放到 uploads_sms/ 目录（export1.xlsx / export2.xlsx），本次跳过短信合并。')
    d1 = d2 = {}
else:
    d1 = load_xlsx(p1)   # 7-29
    d2 = load_xlsx(p2)   # 8-12
merged = {}
merged.update(d1)
merged.update(d2)   # 8-12 覆盖 7-29 的重复号
print(f'Excel去重手机号: 文件1={len(d1)} 文件2={len(d2)} 合并后={len(merged)}')

# 并入 records.json
rec = json.load(open(os.path.join(BASE, 'out', 'records.json'), encoding='utf-8'))
rows = rec['rows']
phset = set()
for r in rows:
    p = norm_ph(r.get('ph'))
    phset.add(p)
    if p in merged:
        m = merged[p]
        r['smsr'] = m['smsr']
        r['smsf'] = m['smsf']
        r['smst'] = m['smst']

matched = sum(1 for r in rows if r.get('smsr'))
print(f'看板总记录: {len(rows)} | 匹配到短信结果: {matched} | 未匹配: {len(rows)-matched}')

rec['sms_merged'] = True
json.dump(rec, open(os.path.join(BASE, 'out', 'records.json'),'w',encoding='utf-8'), ensure_ascii=False)
print('已写回 out/records.json')
