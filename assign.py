# -*- coding: utf-8 -*-
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
"""
低频用户 · 回访自动分配引擎
============================
读取 out/records.json（低频用户 + 接待明细），结合 out/staff.json / out/baseline.json，
将「尚未分配的低频用户」按 负载均衡 分给接待人（每人每日上限可配），
并为「未接通」结果的回访自动生成 +N 天的再次回访任务。
结果写入 out/assignments.json。

v10.24 改动（2026-08-25）：回访排班新增字段透传 —— 手机号归属地(城市名,pcity)/距今未换电天数(按电池最后记录时间,dnr)/车辆最后定位地址(cloc, 待 GPS 数据源接入后回填)。
v10.22 改动（2026-08-24）：回访排班新增字段透传 —— 月均换电频次(swf)/换电周期(scy)/未换电天数(dns)/本地外地(ploc)/电池最后定位(bloc)/流通季度(cq)。
v10.21.2 改动（2026-08-20）：
  1) 修复「同一协议同一天分配给不同接待人」的重复拨打 bug：新增 _dedup_items()，
     load_assignments() 加载时按 (agreement_id, created_date, source) 去重，保留 created_at 最新一条，
     避免历史残留或混合使用「清空重生成 + 追加排班」时出现重复条目（手动任务无 aid，跳过去重）。
v10.21 改动（2026-08-20）：
  1) 「清空重生成」改为按计划日期全量清空当日所有任务后重新生成（真正实现"全部清空待回访名单后生成"）。
  2) 7 天冷却修复：last_visit_by_aid 纳入所有带接待时间的记录（仅排除纯系统类 back_validate/sync_order_status/offline_verify），
     使"待再次回访"等真实接触也能触发冷却，近 N 天内已回访的协议不再进今日名单。
  3) 15 天换电过滤修正：recent_swap_filter_days 默认 15（db_conf.json 可改），改为「生成时」过滤（不放 followable），
     避免已分配任务在清重生成时消失/减少。
  4) 读 db_conf.json 的 recent_swap_filter_days，生成时排除近 N 天换过电（rcnd）的协议。

v10.20 改动（2026-08-20）：
  1) 追加排班：新增 mode='extra' 分支 + extra_solvers 参数
     - 仅对 extra_solvers 中的人员按各自配额分配，原名单完全不动
     - 已分配协议排除（含已回访/已作废），冷却窗口与优先级排序仍生效
     - 解决"追加排班导致单人回访数量翻倍"问题
  2) 任务构造抽到 _build_auto_item 函数，force/append/extra 三模式共用，字段一致

v10.19 改动：
  1) 候选列表按优先级排序——电量<25% 优先、未回访过的优先、最近回访时间远的优先
  2) 冷却窗口：N 天内已回访过的协议不再进今日名单（默认 5 天，可配 recall_cooldown_days）
  3) run_assignment 改用 mode='force'|'append'|'sync' 三分支语义（替换旧的 force_all:bool）
     - force=清空当日 auto/recall 任务但保留已 visited 任务后重生成
     - append=增量（保留原名单）
     - sync=仅对【待回访】任务按当前 active_staff+quota 重新平衡归属（不增不删）

运行：由 sync_local.py 第 5 步自动调用；也可单独 python assign.py 重新分配。
"""
import json, os, datetime, urllib.request, ssl, re

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, 'out')

DEFAULT_STAFF = ["邓志远", "王日威", "胡选婉", "陈名扬", "史苏梅", "黄连霞", "华平平", "黄凯瑜"]
DEFAULT_DAILY_QUOTA = 30
DEFAULT_RECALL_DAYS = 3
# v10.19：N 天内已回访过（人工类）的协议不再进入今日回访名单——避免昨天才回访过未联系上的今天又被排进去
DEFAULT_RECALL_COOLDOWN_DAYS = 5
POWER_LOW_THRESHOLD = 25  # 与 db_conf.json lowfreq_power_threshold 对齐：电量<25% 优先
# v10.19：人工回访 type 白名单——cb_reception_log 含系统类（back_validate/sync_order_status 等），
# 这些不算"已回访"，不能用来触发冷却
REAL_VISIT_TYPES = (
    'book_user_visit', 'manual_call', 'user_visit', 'phone_visit', 'outbound_call',
    'call_visit', 'callback', 'recall', 'visit', 'reception',
)
# v10.21：冷却窗口只排除纯系统类接待（柜端自动校验/订单状态同步/线下核销），
# 其余任意"有接待时间"的记录都计入最近回访日期，避免"待再次回访"等真实接触不触发冷却。
SYSTEM_RT_BLACKLIST = ('back_validate', 'sync_order_status', 'offline_verify')

# v10.21：读 db_conf.json 的 recent_swap_filter_days（近 N 天换过电不进生成名单；默认 15）
def _load_db_conf():
    try:
        with open(os.path.join(BASE, 'db_conf.json'), encoding='utf-8') as _f:
            return json.load(_f)
    except Exception:
        return {}
_DB_CONF = _load_db_conf()
RECENT_SWAP_FILTER_DAYS = int((_DB_CONF or {}).get('recent_swap_filter_days', 15) or 15)


def parse_soc(v):
    """解析 soc 字段为整数。兼容 '54%' / '54' / '' / None，返回 int 或 None。"""
    if v is None:
        return None
    s = str(v).strip().rstrip('%').strip()
    if not s:
        return None
    m = re.match(r'\d+', s)
    return int(m.group()) if m else None


def is_real_visit_type(rty):
    """判断 rty 是否为「人工回访类」（用于冷却窗口的 rt 来源过滤）。"""
    if not rty:
        return False
    t = str(rty).strip().lower()
    return any(k in t for k in REAL_VISIT_TYPES)


def parse_visited_at(s):
    """解析 visited_at 为日期对象。容忍 16 位（'YYYY-MM-DD HH:MM'）和 19 位（'YYYY-MM-DD HH:MM:SS'）两种格式。"""
    if not s:
        return None
    s = str(s).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try:
            return datetime.datetime.strptime(s[:19], fmt).date()
        except Exception:
            continue
    return None

# 触发「+N 天再次回访」的结果标签（未接通类）
UNREACHABLE = {"外呼未接通", "未接听", "联系不上", "空号", "停机", "非本人接听", "表明身份挂机"}

# ---- 回访接待内容分类体系（10 类，可扩展）----
# rec_category 取值为该体系的 key；need_recall=True 表示需再次回访（触发 +N 天再次回访）。
# 若要新增/调整类别，可在 out/rec_categories.json 写一份覆盖列表（字段：key/name/need_recall/kw）。
REC_CATEGORIES = [
    {"key": "01", "name": "用户接通但挂断，需再次回访", "need_recall": True,
     "kw": ["挂断", "挂机", "接通后挂", "说了一句挂", "直接挂", "接了就挂", "接通后挂断", "直接挂断"]},
    {"key": "02", "name": "用户未接通，需再次回访", "need_recall": True,
     "kw": ["未接通", "无人接听", "没人接", "不接", "拒接", "呼叫转移", "无法接通", "关机", "不在服务区", "已关机", "关機"]},
    {"key": "03", "name": "空号，联系不上", "need_recall": True,
     "kw": ["空号", "是空号", "空号码", "已成空号", "空号停机"]},
    {"key": "04", "name": "停机，联系不上", "need_recall": True,
     "kw": ["停机", "已停机", "暂停服务", "号码停用", "已报停"]},
    {"key": "05", "name": "已告知用户进行换电", "need_recall": False,
     "kw": ["告知换电", "已告知换电", "去换电", "已换电", "安排换电", "让用户换电", "提醒换电", "通知换电"]},
    {"key": "06", "name": "用户反馈车辆/电池被偷", "need_recall": False,
     "kw": ["被偷", "被盗", "偷了", "车被偷", "电池被偷", "车没了", "丢失", "车丢了"]},
    {"key": "07", "name": "合作门店，已告知业务员跟进", "need_recall": False,
     "kw": ["门店", "合作门店", "到店", "店里", "网点", "门店跟进"]},
    {"key": "08", "name": "物业公关，已告知业务员跟进", "need_recall": False,
     "kw": ["物业", "物业公关", "小区物业", "物业那边", "物业协调"]},
    {"key": "09", "name": "用户近期无法换电，已告知业务员进行协助换电", "need_recall": False,
     "kw": ["协助换电", "帮忙换电", "无法换电", "近期无法换电", "业务员换电", "安排人换", "代换", "帮忙换"]},
    {"key": "10", "name": "系统数据错误", "need_recall": False,
     "kw": ["数据错误", "系统错误", "信息错误", "号码错误", "资料错误", "错号", "录入错误"]},
]
DEFAULT_CAT = "00"  # 其他 / 未匹配
NEED_RECALL_CATS = [c["key"] for c in REC_CATEGORIES if c["need_recall"]]
# 兼容旧逻辑：旧 outcomes 标签若命中"未接通类"也视为需再次回访
UNREACHABLE |= {"空号", "停机"}

_cat_cache = {}

NOFOLLOWUP_FILE = os.path.join(OUT, 'no_followup.json')

def load_no_followup_aids():
    """加载已标记为无需回访的协议ID集合，避免再次分配。"""
    if not os.path.exists(NOFOLLOWUP_FILE):
        return set()
    try:
        data = json.load(open(NOFOLLOWUP_FILE, encoding='utf-8'))
        if isinstance(data, list):
            return set(x.get('agreement_id') for x in data if x.get('agreement_id'))
    except Exception:
        pass
    return set()


def load_categories():
    """加载分类体系：out/rec_categories.json 若存在且为有效列表则覆盖内置默认（可扩展）。带文件缓存。"""
    fp = os.path.join(OUT, 'rec_categories.json')
    mtime = os.path.getmtime(fp) if os.path.exists(fp) else 0
    if fp in _cat_cache and _cat_cache[fp][0] == mtime:
        return _cat_cache[fp][1]
    cats = REC_CATEGORIES
    if os.path.exists(fp):
        try:
            data = json.load(open(fp, encoding='utf-8'))
            if isinstance(data, list) and data:
                loaded = []
                for c in data:
                    if not isinstance(c, dict):
                        continue
                    key = str(c.get('key') or '').strip()
                    name = str(c.get('name') or '').strip()
                    if not key or not name:
                        continue
                    loaded.append({
                        'key': key,
                        'name': name,
                        'need_recall': bool(c.get('need_recall', False)),
                        'kw': [str(x) for x in (c.get('kw') or [])],
                    })
                if loaded:
                    cats = loaded
        except Exception:
            pass
    _cat_cache[fp] = (mtime, cats)
    return cats


def classify_recall_rule(text, rty=''):
    """基于关键词规则归类回访接待内容，返回分类 key。未匹配返回 DEFAULT_CAT（其他）。"""
    t = (text or '').strip()
    if not t:
        return DEFAULT_CAT
    for c in load_categories():
        for k in c.get('kw') or []:
            if k and k in t:
                return c['key']
    return DEFAULT_CAT


def classify_recall_llm(text, rty=''):
    """可选：若 out/ai_conf.json 配置了大模型，则调用其分类，返回分类 key；未配置/失败返回 None。"""
    fp = os.path.join(OUT, 'ai_conf.json')
    if not os.path.exists(fp):
        return None
    try:
        conf = json.load(open(fp, encoding='utf-8'))
    except Exception:
        return None
    key = conf.get('api_key') or conf.get('key')
    if not key:
        return None
    base = (conf.get('base_url') or 'https://api.openai.com/v1').rstrip('/')
    model = conf.get('model') or 'gpt-4o-mini'
    cats = load_categories()
    prompt = ("你是客服回访内容分类助手。请将下面的「回访接待内容」归类到给定分类之一，只返回分类编号（如 03）。\n"
              "分类清单：\n" + "\n".join(f"{c['key']}. {c['name']}" for c in cats)
              + f"\n\n接待类型：{rty or '未知'}\n回访接待内容：{text or '（空）'}\n只返回编号：")
    try:
        body = json.dumps({"model": model,
                           "messages": [{"role": "user", "content": prompt}],
                           "temperature": 0}, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(base + '/chat/completions', data=body,
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer " + key})
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        content = data['choices'][0]['message']['content'].strip()
        m = re.search(r'\d{1,2}', content)
        if m:
            code = m.group(0).zfill(2)
            if any(c['key'] == code for c in cats):
                return code
    except Exception:
        return None
    return None


def classify_recall(text, rty='', use_llm=True):
    """主入口：优先 LLM（若配置 ai_conf.json），否则规则。返回分类 key。"""
    if use_llm:
        r = classify_recall_llm(text, rty)
        if r:
            return r
    return classify_recall_rule(text, rty)


def p(path, default):
    fp = os.path.join(OUT, path)
    if os.path.exists(fp):
        try:
            return json.load(open(fp, encoding='utf-8'))
        except Exception:
            return default
    return default


# ---------------------------------------------------------------------------
# v10.28.57：records.json 内存缓存
#   背景：records.json 已达 30MB+（12 万协议），json.load 一次约 1.5~3s。
#   原先「生成回访名单」一次操作里会重复读多次（run_assignment →
#   auto_update_visit_status → get_replace_candidates），光解析就 5~9s，
#   用户体感就是「生成回访名单越来越慢」。
#   现按「路径 + mtime」缓存解析结果：同步后 mtime 变化自动失效，不会读到旧数据。
# ---------------------------------------------------------------------------
_REC_CACHE = {"path": None, "mtime": 0.0, "data": None}


def load_records(force=False):
    """带缓存读取 out/records.json。同步后文件 mtime 变化会自动重新解析。"""
    fp = os.path.join(OUT, 'records.json')
    try:
        mt = os.path.getmtime(fp)
    except Exception:
        mt = 0.0
    if (not force and _REC_CACHE["path"] == fp and _REC_CACHE["mtime"] == mt
            and _REC_CACHE["data"] is not None):
        return _REC_CACHE["data"]
    try:
        d = json.load(open(fp, encoding='utf-8'))
    except Exception:
        return None
    _REC_CACHE["path"] = fp
    _REC_CACHE["mtime"] = mt
    _REC_CACHE["data"] = d
    return d


def save(path, obj):
    os.makedirs(OUT, exist_ok=True)
    fp = os.path.join(OUT, path)
    json.dump(obj, open(fp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def today_str():
    return datetime.date.today().isoformat()


def add_days(datestr, n):
    d = datetime.date.fromisoformat(datestr)
    return (d + datetime.timedelta(days=n)).isoformat()


def gen_id(aid, ts):
    s = ts.replace(' ', '_').replace(':', '').replace('-', '')
    return f"a{aid}_{s}"


def save_dispatch_history(date, staff, quotas, assignments):
    """保存每日排班快照，用于历史查询。"""
    hist = p('dispatch_history.json', {})
    hist[date] = {
        'created_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'staff': list(staff),
        'quotas': dict(quotas),
        'assignments': list(assignments),
    }
    save('dispatch_history.json', hist)
    print(f"[OK] 已保存 {date} 排班快照，共 {len(assignments)} 条")


def load_config():
    cfg = p('staff.json', None)
    if cfg is None:
        cfg = {'staff': list(DEFAULT_STAFF), 'daily_quota': DEFAULT_DAILY_QUOTA, 'recall_days': DEFAULT_RECALL_DAYS,
               'recall_cooldown_days': DEFAULT_RECALL_COOLDOWN_DAYS,
               'today_staff': [], 'quotas': {}}
        save('staff.json', cfg)
    cfg.setdefault('staff', list(DEFAULT_STAFF))
    cfg.setdefault('daily_quota', DEFAULT_DAILY_QUOTA)
    cfg.setdefault('recall_days', DEFAULT_RECALL_DAYS)
    # v10.19：N 天内已回访过的协议不进今日回访名单
    cfg.setdefault('recall_cooldown_days', DEFAULT_RECALL_COOLDOWN_DAYS)
    cfg.setdefault('today_staff', [])
    cfg.setdefault('quotas', {})
    cfg.setdefault('gen_filter', {})
    # v10.11 起回访名单默认包含个人+企业协议；若历史配置残留 single（仅个人），重置为 all
    if cfg['gen_filter'].get('agreement_type') in (None, '', 'single'):
        cfg['gen_filter']['agreement_type'] = 'all'
    if not cfg['staff']:
        cfg['staff'] = list(DEFAULT_STAFF)
    return cfg


def _dedup_items(items):
    """v10.21.2：去重「同协议 + 同日期 + 同来源」的多条任务，保留 created_at 最新的。

    背景：v10.21 的「清空重生成」按日期全清后重生 + 追加排班混合使用时，
    偶尔会在 assignments.json 里残留同一 (agreement_id, created_date) 的多条记录
    （不同接待人 / 不同 created_at），导致同一协议同一天被拨多次。
    去重键： (agreement_id, created_date, source) —— 不同 source（如 auto vs recall）
    视为不同任务，保留。手动任务（无 agreement_id）也保留。
    """
    seen = {}
    dup = 0
    for it in items:
        aid = it.get('agreement_id')
        if aid is None:
            continue  # 手动任务/历史任务，无 aid，跳过去重
        key = (aid, it.get('created_date', ''), it.get('source', ''))
        cur = seen.get(key)
        if cur is None:
            seen[key] = it
        elif (it.get('created_at') or '') > (cur.get('created_at') or ''):
            seen[key] = it
            dup += 1
        else:
            dup += 1
    manual = [it for it in items if it.get('agreement_id') is None]
    if dup:
        print(f"[INFO] 去重 {dup} 条重复分配任务（同协议+同日期+同来源，保留最新）")
    return list(seen.values()) + manual


def load_assignments():
    d = p('assignments.json', None)
    if not d or 'items' not in d:
        d = {'items': []}
    # 向后兼容：补全新字段默认值
    for it in d.get('items', []):
        it.setdefault('is_lf', 0)
        it.setdefault('is_owe', 0)
        it.setdefault('pkg', '')
        it.setdefault('bsn', '')
        it.setdefault('bcl', '')
        it.setdefault('bco', '')
        it.setdefault('bcv', 0)
        it.setdefault('cabn', '')
        it.setdefault('soc', '')
        it.setdefault('online', '')
        it.setdefault('bat_anomaly', False)
        it.setdefault('visit_result', 'pending')
        it.setdefault('visited_at', None)
        it.setdefault('rec_category', DEFAULT_CAT)
        it.setdefault('agreement_status', '')
        it.setdefault('deposit_status', '')
        it.setdefault('agreement_type', '')
        it.setdefault('agreement_type_raw', '')
    # v10.21.2：去重（同一协议+同日期+同来源 只保留最新一条），避免「同一协议同一天分配给不同接待人」
    d['items'] = _dedup_items(d.get('items', []))
    return d


def auto_update_visit_status(data=None):
    """根据 records.json 中的最新接待记录，自动推断待回访任务是否已回访。
    规则：任务状态为 待回访 且 planned_time 之后存在接待记录（rt），则标记为 visited。
    不覆盖手动标记为 visited 的状态（如需覆盖可后续扩展）。"""
    asg = load_assignments()
    items = asg.get('items', [])
    if not items:
        return
    if data is None:
        data = load_records()
    if not data or 'rows' not in data:
        return
    rec_by_id = {}
    for r in data['rows']:
        if r.get('id') is not None:
            rec_by_id[r['id']] = r
    updated = 0
    for it in items:
        if it.get('status') != '待回访':
            continue
        # 仅当当前为 pending 时才自动推断；已手动标记为 visited 的不覆盖
        if it.get('visit_result') == 'visited':
            continue
        rec = rec_by_id.get(it.get('agreement_id'))
        if not rec:
            continue
        rt = rec.get('rt', '')
        if not rt:
            continue
        planned = it.get('planned_time', '')
        try:
            if planned and rt > planned:
                it['visit_result'] = 'visited'
                it['visited_at'] = rt
                updated += 1
        except Exception:
            pass
    if updated:
        save('assignments.json', asg)
        print(f"[OK] 自动推断回访状态：{updated} 条任务标记为已回访")


def _build_auto_item(r, solver, gen_date, now):
    """v10.20：把 records.json 紧凑字段映射成一条【待回访】自动任务。
    force / append / extra 三种 mode 共用，字段一致。
    """
    return {
        'id': gen_id(r['id'], now),
        'user_id': r.get('uid'),
        'consumer_id': r.get('cid') or r.get('uid'),
        'agreement_id': r['id'],
        'phone': r.get('ph', ''),
        'cur_phone': r.get('cph', ''),  # v10.20：当前手机号（cb_user 取，前端可显示）
        'assigned_solver': solver,
        'planned_time': gen_date,
        'status': '待回访',
        'source': 'auto',
        'created_date': gen_date,
        'created_at': now,
        'tags': {'L1': [], 'L2': [], 'L3': [], 'outcomes': []},
        'tagged_at': None,
        'tagged_by': None,
        'last_rec_time': r.get('rt', ''),
        'last_rec_solver': r.get('rs', ''),
        'last_rec_detail': r.get('rd', ''),
        'parent_id': None,
        # 筛选维度（与低频用户看板对齐）
        'province': r.get('pr', ''),
        'city': r.get('ci', ''),
        'area': r.get('ar', ''),
        'street': r.get('st', ''),
        'community': r.get('co', ''),
        'product': r.get('pd', ''),
        'agent': r.get('ag', ''),
        'agreement_status': r.get('status', ''),
        'deposit_status': r.get('dst', ''),
        'agreement_type': r.get('at', ''),
        'agreement_type_raw': r.get('atr', ''),
        'level': r.get('lv', 0),
        'lname': r.get('ln', ''),
        'use_days': r.get('days'),
        # 用户类型标记（前端联动筛选用）
        'is_lf': bool(r.get('lf')),
        'is_owe': bool(r.get('owe')),
        # 电池与套餐信息（今日待分配表格展示用）
        'pkg': r.get('pkg', ''),
        'bsn': r.get('bsn', ''),
        'bcl': r.get('bcl', ''),
        'bco': r.get('bco', ''),
        'bcv': r.get('bcv', 0),
        'cabn': r.get('cabn', ''),
        'soc': r.get('soc', ''),
        'online': r.get('onl', ''),
        'bat_anomaly': bool(r.get('ba')),
        # v10.22：换电频次/周期/未换电天数/本地外地/电池定位/流通季度
        'swf': r.get('swf', ''),
        'scy': r.get('scy', ''),
        'dns': r.get('dns', ''),
        'ploc': r.get('ploc', ''),
        'bloc': r.get('bloc', ''),
        'cq': r.get('cq', ''),
        # v10.24：手机号归属地(城市名)/距今未换电天数(按电池最后记录时间)/车辆最后定位地址
        'pcity': r.get('pcity', ''),
        'dnr': r.get('dnr', ''),
        'cloc': r.get('cloc', ''),
        # v10.26：电池最后记录毫秒戳(前端按 planDate 实时算 dnr) / 归属地来源标记
        'lcts': r.get('lcts', 0),
        'psrc': r.get('psrc', ''),
        # v10.28：电池 cb_battery 表"最后一次有效定位"地址 + 毫秒戳
        'lla': r.get('lla', ''),
        'llt': r.get('llt', 0),
        # v10.25：下次预计换电日（基于该协议历次换电的中位间距推算 = 末次换电 + 中位间距）
        'nse': r.get('nse', ''),
        # 回访结果追踪
        'visit_result': 'pending',
        'visited_at': None,
        # 回访接待内容智能分类（默认规则，看板可一键 AI 重分类）
        'rec_category': classify_recall(r.get('rd', ''), r.get('rty', ''), use_llm=False),
    }


def run_assignment(mode='force', gen_date=None, extra_solvers=None):
    """生成回访名单。

    mode 语义（v10.19 / v10.20）：
      - 'force'  : 清空当日 auto/recall 的【待回访】任务后重新生成（保留已 visited 任务与手动任务）
      - 'append' : 增量模式，保留原名单不变，仅补充尚未分配的协议
      - 'sync'   : 仅对当日【待回访】任务按当前 active_staff+quota 重新平衡归属（不增不删，保留已回访/已作废）
      - 'extra'  : v10.20 追加排班专用 — 仅对 extra_solvers 中的人员按各自配额分配，
                   已分配协议排除（assigned_aids + nof_aids），冷却窗口与优先级排序仍生效；
                   原名单完全不动，避免给已分配人员再补一份把回访数量翻倍。
                   extra_solvers 形如 {'张三': 10, '李四': 8}，未列出的接待人不分配任务。
    """
    data = load_records()
    if not data or 'rows' not in data:
        print("[FAIL] 未找到 out/records.json，请先同步数据库。")
        return
    rows = data['rows']
    print(f"ℹ records.json 总记录数: {len(rows)}")

    cfg = load_config()
    staff = cfg['staff']
    # 今日排班人员：若 today_staff 非空则使用，否则回退到全部人员
    active_staff = [s for s in cfg.get('today_staff', []) if s in staff]
    if not active_staff:
        active_staff = list(staff)
    # 按人配额，未设置则回退到全局 daily_quota
    default_quota = int(cfg.get('daily_quota', DEFAULT_DAILY_QUOTA))
    quotas = cfg.get('quotas', {}) or {}
    def quota_of(s):
        try:
            v = quotas.get(s, default_quota)
            return max(1, int(v))
        except Exception:
            return default_quota
    recall_days = int(cfg.get('recall_days', DEFAULT_RECALL_DAYS))
    # v10.19：冷却窗口——N 天内已回访过的不进今日名单（默认 5 天，可配）
    cd_days = int(cfg.get('recall_cooldown_days', DEFAULT_RECALL_COOLDOWN_DAYS))
    print(f"ℹ 总接待人员: {staff} | 今日排班: {active_staff} | 再次回访间隔: {recall_days}天 | 冷却窗口: {cd_days}天")

    # 自动推断回访状态（基于最新 records.json 接待记录），先保存
    # v10.28.57：复用上面已解析的 data，避免再读一次 30MB
    auto_update_visit_status(data)
    # 重新加载，确保 items 引用最新状态
    asg = load_assignments()
    items = asg.setdefault('items', [])

    # v10.19：融合 records.json 的人工类 rt 与 assignments.json 的 visited_at，
    # 得到每个协议"最近一次真实回访日期"（用于冷却窗口过滤 + 排序优先级）。
    # ① records.json 侧：纳入所有"有接待时间"的记录（仅排除纯系统自动类），用于冷却窗口与排序优先级
    last_visit_by_aid = {}
    for r in rows:
        aid = r.get('id')
        if aid is None:
            continue
        _rty = (r.get('rty') or '').strip().lower()
        if _rty in SYSTEM_RT_BLACKLIST:
            continue
        if r.get('rt'):
            d = parse_visited_at(r.get('rt', ''))
            if d:
                prev = last_visit_by_aid.get(aid)
                if prev is None or d > prev:
                    last_visit_by_aid[aid] = d
    # ② assignments.json 侧：已标记 visited 的任务（本地手动标记不回写数据库，必须从这里取）
    for x in items:
        aid = x.get('agreement_id')
        if aid is None or x.get('visit_result') != 'visited':
            continue
        d = parse_visited_at(x.get('visited_at') or '')
        if d:
            prev = last_visit_by_aid.get(aid)
            if prev is None or d > prev:
                last_visit_by_aid[aid] = d
    print(f"ℹ 已回访冷却查表（最近一次真实回访日期）协议数: {len(last_visit_by_aid)}")

    # 已分配协议：以 assignments.json 中实际存在的任务为准（按协议ID去重），并排除已标记无需回访的协议
    nof_aids = load_no_followup_aids()
    assigned_aids = set(x['agreement_id'] for x in items if x.get('agreement_id')) | nof_aids
    print(f"ℹ assignments.json 已有任务数: {len(items)} | 已分配协议ID数: {len(assigned_aids)-len(nof_aids)} | 无需回访: {len(nof_aids)}")

    # 今日已分配数（每人），用于负载均衡 + 每日上限
    today = today_str()
    gen_date = gen_date or today
    today_count = {s: 0 for s in active_staff}
    for x in items:
        if x.get('created_date') == gen_date and x.get('assigned_solver') in today_count:
            today_count[x['assigned_solver']] += 1

    # 用户类型筛选：低频 / 欠租催收（多选取并集；默认低频）
    user_types = cfg.get('gen_filter', {}).get('user_types') or ['lf']
    if not isinstance(user_types, list):
        user_types = [user_types]
    valid_types = set(user_types) & {'lf', 'owe'}
    if not valid_types:
        valid_types = {'lf'}
    def match_user_type(r):
        if 'lf' in valid_types and r.get('lf'):
            return True
        if 'owe' in valid_types and r.get('owe'):
            return True
        return False
    type_label = '/'.join(sorted(valid_types))
    print(f"ℹ 用户类型筛选: {type_label}")

    # 所有候选协议（records.json 中为紧凑字段）。
    # v10.18.6：除用户类型筛选（低频/欠租）【或】电池状态异常外，必须用 followable 过滤——
    #   排除 流通异常 / 柜内归还无电池 / 空号(无需回访) 的协议（这些 is_lf 可能仍为True但不可回访）。
    candidates = [r for r in rows if (match_user_type(r) or r.get('ba')) and r.get('followable')]
    print(f"ℹ records.json 中候选协议数 (followable, {type_label}): {len(candidates)}")

    if mode == 'force':
        # v10.28.43【保护名单】—— 只清空「指定 gen_date 当日 + 待回访 + 非手动」的任务，
        #   保留其他日期的名单（昨天/明天/上周的「待回访」不动）+ 保留已回访/已作废历史
        #   解决之前 v10.28.20 误清「所有待回访历史任务」导致用户反映"每次打开看板名单就被清空"的问题
        before = len(items)
        items[:] = [x for x in items
                    if not (x.get('created_date') == gen_date
                            and x.get('status') == '待回访'
                            and not x.get('manual'))]
        removed_today = before - len(items)
        # v10.28.43：assigned_aids 包含已存在的「当日待回访（即使已清空）」—— 用于防重复
        #   历史非当日「待回访」不动，所以其 aid 仍算「已占用」，避免重复分配
        assigned_aids = set(nof_aids)
        for _x in items:
            _cd = _x.get('created_date')
            _st = _x.get('status')
            if _cd != gen_date and _st == '待回访':
                assigned_aids.add(_x.get('aid') or _x.get('agr'))
            elif _st in ('已回访', '已作废') and _cd == gen_date:
                # 当日已回访/已作废的任务不再重复分配
                assigned_aids.add(_x.get('aid') or _x.get('agr'))
        print(f"[v10.28.43] 清空重生成模式（保护名单）：")
        print(f"  - 清空当日「待回访+非手动」 {removed_today} 条")
        print(f"  - 保留：其他日期的「待回访」+ 全部「已回访/已作废/手动」 {len(items)} 条（历史查询）")
        print(f"  - assigned_aids={len(assigned_aids)}（含其他日期待回访 + 当日已回访 + 无需回访）")
        print(f"  - 产品口径：低频用户【无论之前是否分配过】都进回访名单（除非在冷却期/已回访/已作废）")
    elif mode == 'sync':
        # v10.19：仅对当日【待回访】任务按当前 active_staff + quota 重新平衡归属/配额，不增不删，保留已回访/已作废记录
        print(f"[INFO] 同步刷新模式：仅重新平衡 {gen_date} 当日【待回访】任务的归属/配额，不增不删")
        sync_rebalance(items, active_staff, quota_of, gen_date, today_str())
        save('assignments.json', asg)
        save_dispatch_history(gen_date, active_staff, {s: quota_of(s) for s in active_staff}, [])
        n_pending = sum(1 for x in items if x.get('status') == '待回访' and x.get('created_date') == gen_date)
        print(f"[OK] 同步刷新完成：当前 {gen_date} 待回访任务共 {n_pending} 个")
        return
    elif mode == 'extra':
        # v10.20 追加排班：仅对 extra_solvers 中的人员按各自配额分配
        #  - 原名单完全不动（不读 today_staff，不读 cfg.quotas）
        #  - 已分配协议排除（含【待回访】/已回访/已作废/无需回访），冷却窗口与优先级排序仍生效
        #  - 块分配：按 extra_solvers 顺序依次取 quota 条分配给对应人员
        if not extra_solvers:
            print("[FAIL] mode='extra' 必须提供 extra_solvers 参数（格式：{name: quota}）。")
            return
        # 规范化参数：过滤非接待人、过滤非正整数配额
        norm_extra = []
        for name, q in extra_solvers.items():
            if not name or name not in staff:
                continue
            try:
                q = max(1, int(q))
            except Exception:
                continue
            norm_extra.append((name, q))
        if not norm_extra:
            print(f"[FAIL] extra_solvers 未匹配到任何已配置的接待人（可选：{staff}）")
            return
        # 候选：与 force/append 共享同一逻辑（已分配协议排除 + followable）
        lf_x = [r for r in rows if match_user_type(r) and r.get('followable') and r.get('id') not in assigned_aids]
        # v10.21：生成时过滤——近 N 天换过电(rcnd)的不进名单
        if RECENT_SWAP_FILTER_DAYS > 0:
            lf_x = [r for r in lf_x if not r.get('rcnd')]
        # 生成名单筛选
        gf_x = cfg.get('gen_filter') or {}
        gf_x = {k: v for k, v in gf_x.items() if v and k != 'user_types'}
        if gf_x:
            def _match_filter_x(r, gf=gf_x):
                if gf.get('product') and r.get('pd') != gf['product']: return False
                if gf.get('agent') and r.get('ag', r.get('at')) != gf['agent']: return False
                if gf.get('city') and r.get('ci') != gf['city']: return False
                if gf.get('area') and r.get('ar') != gf['area']: return False
                if gf.get('street') and r.get('st') != gf['street']: return False
                if gf.get('community') and r.get('co') != gf['community']: return False
                if gf.get('agreement_type') and gf['agreement_type'] != 'all':
                    raw = r.get('atr') or r.get('at') or ''
                    want = gf['agreement_type']
                    if want == 'single' and raw not in ('single', '个人'): return False
                    if want == 'company' and raw not in ('company', '企业'): return False
                return True
            lf_x = [r for r in lf_x if _match_filter_x(r)]
        # 冷却窗口
        cd_today = datetime.date.today()
        lf_x = [r for r in lf_x if not (lambda aid: (cd_today - last_visit_by_aid[aid]).days < cd_days if last_visit_by_aid.get(aid) else False)(r.get('id'))]
        # 优先级排序（v10.28.43：增加电池最后流通时间维度）
        def _prio_x(r):
            soc_num = parse_soc(r.get('soc', ''))
            lv = last_visit_by_aid.get(r.get('id'))
            has_visit = 0 if lv is None else 1
            low_power = 0 if (soc_num is not None and soc_num < POWER_LOW_THRESHOLD) else 1
            circ = (r.get('circ_last') or '').strip()
            circ_key = (0 if not circ else 1, circ)
            return (circ_key, low_power, has_visit, str(lv or ''))
        lf_x.sort(key=_prio_x)
        # 块分配
        idx_x = 0
        n_new_x = 0
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        new_items_x = []
        extra_summary = []
        for name, q in norm_extra:
            chunk = lf_x[idx_x:idx_x + q]
            idx_x += q
            if not chunk:
                extra_summary.append(f"{name}:0")
                continue
            extra_summary.append(f"{name}:{len(chunk)}")
            for r in chunk:
                it = _build_auto_item(r, name, gen_date, now)
                new_items_x.append(it)
                assigned_aids.add(r.get('id'))
                n_new_x += 1
        items.extend(new_items_x)
        save('assignments.json', asg)
        # 保存历史快照（active_staff 用本次追加的名单，不污染主 cfg）
        only_extra_names = [n for n, _ in norm_extra]
        save_dispatch_history(gen_date, only_extra_names,
                              {n: q for n, q in norm_extra}, new_items_x)
        date_desc = '今天' if gen_date == today else gen_date
        msg = f"[OK] 追加排班完成：新增 {n_new_x} 个任务（{date_desc}｜按 {extra_summary}）。原名单完全保留。"
        if idx_x < len(lf_x):
            msg += f" 剩余 {len(lf_x) - idx_x} 个候选协议因配额用尽未分配，可再次追加。"
        print(msg)
        print(f"ℹ 当前 assignments.json 总任务数: {len(items)}")
        return
    # append（及其他未识别值）模式：保留原名单（无任何清空），仅补未分配协议（走下方 lf 分配逻辑）

    lf = [r for r in rows if match_user_type(r) and r.get('followable') and r.get('id') not in assigned_aids]
    print(f"ℹ 尚未分配的候选协议数 (followable): {len(lf)}")

    # v10.21：生成时过滤——近 N 天换过电(rcnd)的协议不进今日名单（仅影响新生成，已存在于 assignments.json 的任务不受影响，故不会让已分配名单消失）
    if RECENT_SWAP_FILTER_DAYS > 0:
        lf = [r for r in lf if not r.get('rcnd')]
        print(f"ℹ 应用近 {RECENT_SWAP_FILTER_DAYS} 天换电过滤后待分配协议数: {len(lf)}")

    # 生成名单筛选（电池产品/代理商/地理）：仅保留匹配 gen_filter 的协议
    gf = cfg.get('gen_filter') or {}
    # user_types 不进入字段匹配，单独处理
    gf = {k: v for k, v in gf.items() if v and k != 'user_types'}
    if gf:
        def match_filter(r):
            if gf.get('product') and r.get('pd') != gf['product']:
                return False
            if gf.get('agent') and r.get('ag', r.get('at')) != gf['agent']:
                return False
            if gf.get('city') and r.get('ci') != gf['city']:
                return False
            if gf.get('area') and r.get('ar') != gf['area']:
                return False
            if gf.get('street') and r.get('st') != gf['street']:
                return False
            if gf.get('community') and r.get('co') != gf['community']:
                return False
            if gf.get('agreement_type') and gf['agreement_type'] != 'all':
                # 兼容中文标签与原始值
                raw = r.get('atr') or r.get('at') or ''
                want = gf['agreement_type']
                if want == 'single' and raw not in ('single', '个人'):
                    return False
                if want == 'company' and raw not in ('company', '企业'):
                    return False
            return True
        lf = [r for r in lf if match_filter(r)]
        gf_desc = ' | '.join(f"{k}={v}" for k, v in gf.items())
        print(f"ℹ 应用生成筛选（{gf_desc}）后待分配协议数: {len(lf)}")

    # v10.19：冷却窗口过滤——N 天内已回访过的协议不进今日名单
    # （昨天才回访过且未联系上的，今天不再纳入；需再过 cd_days 天后才再次回访）
    lf_before_cd = len(lf)
    today_d = datetime.date.today()
    def _in_cooldown(aid):
        d = last_visit_by_aid.get(aid)
        if d is None:
            return False
        try:
            return (today_d - d).days < cd_days
        except Exception:
            return False
    lf = [r for r in lf if not _in_cooldown(r.get('id'))]
    print(f"ℹ 应用冷却窗口({cd_days}天)后待分配协议数: {len(lf)}（剔除近 {cd_days} 天内已回访的 {lf_before_cd - len(lf)} 个）")

    # v10.19：优先级排序——电量<25% 优先、未回访过的优先、最近回访时间远的优先
    # v10.28.43【电池最后流通时间排序】—— 把 circ_last（电池最后一次换电时间）作为最高优先级：
    #   · 排序规则：① circ_last ASC（NULL=最优先，因为从未流通=长期沉默）
    #                ② 电量<25% 优先
    #                ③ 未回访过的优先
    #                ④ 最近回访时间远的优先
    #   · 9月1日排班：circ_last ≤ 2026-07-01（≥2 个月未换电）会排在最前
    #   · 10月1日排班：circ_last ≤ 2026-08-01（≥2 个月未换电）会排在最前
    #   · 实现：把 circ_last 字符串当主排序键，越早越小；NULL 用 (0, '') 表示最优先
    def _prio_key(r):
        soc_num = parse_soc(r.get('soc', ''))
        lv = last_visit_by_aid.get(r.get('id'))
        has_visit = 0 if lv is None else 1
        low_power = 0 if (soc_num is not None and soc_num < POWER_LOW_THRESHOLD) else 1
        circ = (r.get('circ_last') or '').strip()
        # circ_key=(flag, str) flag=0 表示"无记录=最优先"；flag=1 表示"有记录按时间升序"
        circ_key = (0 if not circ else 1, circ)
        return (circ_key, low_power, has_visit, str(lv or ''))
    lf.sort(key=_prio_key)
    print(f"ℹ[v10.28.43] 已按优先级排序：① 电池最后流通时间 ASC（NULL=最优先）→ ② 电量<{POWER_LOW_THRESHOLD}%优先 → ③ 未回访优先 → ④ 回访时间远优先")

    # 连续块分配：按 active_staff 顺序依次取 quota 条记录全部分给当前人员
    idx = 0
    n_new = 0
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    new_items = []
    for s in active_staff:
        q = quota_of(s)
        chunk = lf[idx:idx + q]
        if not chunk:
            break
        idx += q
        for r in chunk:
            it = _build_auto_item(r, s, gen_date, now)
            new_items.append(it)
            assigned_aids.add(r.get('id'))
            n_new += 1

    items.extend(new_items)
    save('assignments.json', asg)

    # 保存每日排班快照（供历史查询）
    save_dispatch_history(gen_date, active_staff, {s: quota_of(s) for s in active_staff}, new_items)

    quota_summary = ', '.join(f"{s}:{quota_of(s)}" for s in active_staff)
    date_desc = '今天' if gen_date == today else gen_date
    msg = f"[OK] 自动分配完成：本次新增 {n_new} 个任务（计划日期 {date_desc}｜排班 {len(active_staff)} 人，配额 {quota_summary}）。"
    if idx < len(lf):
        msg += f" 剩余 {len(lf) - idx} 个候选协议因排班人员配额已用尽未分配。"
    print(msg)
    print(f"ℹ 当前 assignments.json 总任务数: {len(items)}")


def sync_rebalance(items, active_staff, quota_of, gen_date, today):
    """v10.19：对当日【待回访】任务按当前 active_staff + quota 重新平衡归属/配额。

    仅修改待回访任务的 assigned_solver / planned_time / created_date / source，
    不增不删、不改动已回访/已作废任务。返回本次处理的待回访任务数。
    """
    if not active_staff:
        return 0
    pending = [x for x in items if x.get('status') == '待回访'
               and x.get('source') in ('auto', 'recall')
               and x.get('created_date') == gen_date]
    if not pending:
        return 0
    # 按当前优先级（电量<25% 优先、未回访优先、回访远优先）重新排序后依次分给 active_staff
    def _prio_key(x):
        soc_num = parse_soc(x.get('soc', ''))
        lv = x.get('visited_at') or x.get('last_rec_time') or ''
        has_visit = 0 if (parse_visited_at(lv) is None) else 1
        low_power = 0 if (soc_num is not None and soc_num < POWER_LOW_THRESHOLD) else 1
        return (low_power, has_visit, str(lv or ''))
    pending.sort(key=_prio_key)
    # 重置每人当日已分配计数（sync 模式下以"待回访"任务为基准重排）
    today_count = {s: 0 for s in active_staff}
    idx = 0
    for s in active_staff:
        q = quota_of(s)
        for _ in range(q):
            if idx >= len(pending):
                break
            t = pending[idx]
            # 仅当原承接人与新承接人不同或配额有变时才更新（保持 id/agreement_id/user_id 不变）
            if t.get('assigned_solver') != s or t.get('planned_time') != gen_date:
                t['assigned_solver'] = s
                t['planned_time'] = gen_date
                t['created_date'] = gen_date
                t['source'] = 'auto'
            today_count[s] += 1
            idx += 1
    return len(pending)


# ---- 替换分配：将某条回访任务替换为其他符合条件的用户 ----
def copy_record_fields(target, rec):
    """将 records.json 的用户字段覆盖到任务对象（保留任务自身的排班/标签/状态字段）。"""
    target['agreement_id'] = rec.get('id')
    target['user_id'] = rec.get('uid')
    target['consumer_id'] = rec.get('cid') or rec.get('uid')
    target['phone'] = rec.get('ph', '')
    target['last_rec_time'] = rec.get('rt', '')
    target['last_rec_solver'] = rec.get('rs', '')
    target['last_rec_detail'] = rec.get('rd', '')
    target['province'] = rec.get('pr', '')
    target['city'] = rec.get('ci', '')
    target['area'] = rec.get('ar', '')
    target['street'] = rec.get('st', '')
    target['community'] = rec.get('co', '')
    target['product'] = rec.get('pd', '')
    target['agent'] = rec.get('ag', '')
    target['agreement_status'] = rec.get('status', '')
    target['deposit_status'] = rec.get('dst', '')
    target['agreement_type'] = rec.get('at', '')
    target['agreement_type_raw'] = rec.get('atr', '')
    target['level'] = rec.get('lv', 0)
    target['lname'] = rec.get('ln', '')
    target['use_days'] = rec.get('days')
    target['is_lf'] = bool(rec.get('lf'))
    target['is_owe'] = bool(rec.get('owe'))
    target['pkg'] = rec.get('pkg', '')
    target['bsn'] = rec.get('bsn', '')
    target['bcl'] = rec.get('bcl', '')
    target['bco'] = rec.get('bco', '')
    target['bcv'] = rec.get('bcv', 0)
    target['cabn'] = rec.get('cabn', '')
    target['soc'] = rec.get('soc', '')
    target['online'] = rec.get('onl', '')
    target['bat_anomaly'] = bool(rec.get('ba'))
    # v10.22：换电频次/周期/未换电天数/本地外地/电池定位/流通季度
    target['swf'] = rec.get('swf', '')
    target['scy'] = rec.get('scy', '')
    target['dns'] = rec.get('dns', '')
    target['ploc'] = rec.get('ploc', '')
    target['bloc'] = rec.get('bloc', '')
    target['cq'] = rec.get('cq', '')
    # v10.24：手机号归属地(城市名)/距今未换电天数(按电池最后记录时间)/车辆最后定位地址
    target['pcity'] = rec.get('pcity', '')
    target['dnr'] = rec.get('dnr', '')
    target['cloc'] = rec.get('cloc', '')
    # v10.26：lcts / psrc 透传
    target['lcts'] = rec.get('lcts', 0)
    target['psrc'] = rec.get('psrc', '')
    # v10.28：lla / llt 透传
    target['lla'] = rec.get('lla', '')
    target['llt'] = rec.get('llt', 0)
    # v10.25：下次预计换电日
    target['nse'] = rec.get('nse', '')
    target['rty'] = rec.get('rty', '')
    target['rec_category'] = classify_recall(rec.get('rd', ''), rec.get('rty', ''), use_llm=False)
    return target


def get_replace_candidates(task_id, kw=''):
    """返回可替换的候选用户：与被替换任务同类型（低频/欠租）且满足当前生成筛选/电池异常，
    且尚未分配（不在其它回访任务中）。"""
    asg = load_assignments()
    items = asg.setdefault('items', [])
    target = next((x for x in items if x.get('id') == task_id), None)
    if not target:
        return {'ok': False, 'msg': '未找到该回访任务', 'candidates': []}
    data = load_records()
    if not data or 'rows' not in data:
        return {'ok': False, 'msg': '未找到 records.json，请先同步数据库', 'candidates': []}
    rows = data['rows']
    cfg = load_config()
    # 目标类型：与被替换任务一致（低频任务替换为低频候选，欠租同理）
    want_lf = bool(target.get('is_lf'))
    want_owe = bool(target.get('is_owe'))
    def match_user_type(r):
        if want_lf and r.get('lf'):
            return True
        if want_owe and r.get('owe'):
            return True
        return False
    # 生成筛选（电池产品/代理商/地理）
    gf = cfg.get('gen_filter') or {}
    gf = {k: v for k, v in gf.items() if v and k != 'user_types'}
    def match_filter(r):
        if gf.get('product') and r.get('pd') != gf['product']:
            return False
        if gf.get('agent') and r.get('ag', r.get('at')) != gf['agent']:
            return False
        if gf.get('city') and r.get('ci') != gf['city']:
            return False
        if gf.get('area') and r.get('ar') != gf['area']:
            return False
        if gf.get('street') and r.get('st') != gf['street']:
            return False
        if gf.get('community') and r.get('co') != gf['community']:
            return False
        if gf.get('agreement_type') and gf['agreement_type'] != 'all':
            raw = r.get('atr') or r.get('at') or ''
            want = gf['agreement_type']
            if want == 'single' and raw not in ('single', '个人'):
                return False
            if want == 'company' and raw not in ('company', '企业'):
                return False
        return True
    # 已分配协议ID（排除当前任务本身、当前任务自身占用的协议，以及已标记无需回访的协议）
    cur_aid = target.get('agreement_id')
    used_aids = set(x.get('agreement_id') for x in items
                    if x.get('id') != task_id and x.get('agreement_id'))
    used_aids |= load_no_followup_aids()
    if cur_aid is not None:
        used_aids.add(cur_aid)
    kw = (kw or '').strip().lower()
    out = []
    for r in rows:
        if not (match_user_type(r) or r.get('ba')):
            continue
        if not r.get('followable'):
            continue
        if not match_filter(r):
            continue
        aid = r.get('id')
        if aid in used_aids:
            continue
        if kw:
            hay = f"{aid} {r.get('ph', '')}".lower()
            if kw not in hay:
                continue
        out.append({
            'id': aid, 'phone': r.get('ph', ''),
            'product': r.get('pd', ''), 'city': r.get('ci', ''), 'area': r.get('ar', ''),
            'soc': r.get('soc', ''), 'online': r.get('onl', ''),
            'cabn': r.get('cabn', ''), 'level': r.get('lv', 0), 'lname': r.get('ln', ''),
            'is_lf': bool(r.get('lf')), 'is_owe': bool(r.get('owe')),
        })
    # 排序：有异常原因的优先，其次按电量升序（电量低的更需跟进）
    def _key(x):
        return (0 if x.get('cabn') else 1, -(int(str(x.get('soc', '0')).strip('%').split('.')[0]) if str(x.get('soc', '')).strip().rstrip('%').isdigit() else 0))
    out.sort(key=_key)
    cur = {'id': target.get('agreement_id'), 'phone': target.get('phone', ''),
           'product': target.get('product', ''), 'city': target.get('city', ''),
           'is_lf': want_lf, 'is_owe': want_owe}
    return {'ok': True, 'candidates': out, 'count': len(out), 'current': cur}


def replace_assignment(task_id, new_agreement_id):
    """将某条回访任务（task_id）替换为 records.json 中 new_agreement_id 对应的用户。"""
    asg = load_assignments()
    items = asg.setdefault('items', [])
    target = next((x for x in items if x.get('id') == task_id), None)
    if not target:
        return {'ok': False, 'msg': '未找到该回访任务'}
    data = load_records()
    if not data or 'rows' not in data:
        return {'ok': False, 'msg': '未找到 records.json，请先同步数据库'}
    rec = next((r for r in data['rows'] if r.get('id') == new_agreement_id), None)
    if not rec:
        return {'ok': False, 'msg': '未找到替换目标用户（协议ID=%s）' % new_agreement_id}
    # 防止替换成已被其它任务占用的用户（含当前任务自身占用的协议）
    cur_aid = target.get('agreement_id')
    used_aids = set(x.get('agreement_id') for x in items
                    if x.get('id') != task_id and x.get('agreement_id'))
    if cur_aid is not None:
        used_aids.add(cur_aid)
    if rec.get('id') in used_aids:
        return {'ok': False, 'msg': '该用户已在其他回访任务中，请换一个'}
    copy_record_fields(target, rec)
    target['replaced_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    save('assignments.json', asg)
    return {'ok': True, 'agreement_id': new_agreement_id, 'phone': target.get('phone')}


def create_recall(parent, recall_days=None):
    """根据父任务生成 +recall_days 天的再次回访任务。成功返回新任务，否则 None。"""
    asg = load_assignments()
    items = asg['items']
    # 避免重复：已有同源未完成 re-call 则不重复生成
    for x in items:
        if x.get('parent_id') == parent.get('id') and x.get('source') == 'recall' \
                and x.get('status') in ('待回访',):
            return None
    if recall_days is None:
        cfg = load_config()
        recall_days = int(cfg.get('recall_days', DEFAULT_RECALL_DAYS))
    base_date = parent.get('planned_time') or parent.get('created_date') or today_str()
    try:
        planned = add_days(base_date, recall_days)
    except Exception:
        planned = today_str()
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    new = {
        'id': gen_id(parent.get('agreement_id'), now),
        'user_id': parent.get('user_id'),
        'consumer_id': parent.get('consumer_id') or parent.get('user_id'),
        'agreement_id': parent.get('agreement_id'),
        'phone': parent.get('phone', ''),
        'assigned_solver': parent.get('assigned_solver'),
        'planned_time': planned,
        'status': '待回访',
        'source': 'recall',
        'created_date': today_str(),
        'created_at': now,
        'tags': {'L1': [], 'L2': [], 'L3': [], 'outcomes': []},
        'tagged_at': None,
        'tagged_by': None,
        'last_rec_time': parent.get('last_rec_time', ''),
        'last_rec_solver': parent.get('last_rec_solver', ''),
        'last_rec_detail': parent.get('last_rec_detail', ''),
        'parent_id': parent.get('id'),
        # 继承用户类型/电池/套餐/回访状态字段
        'is_lf': parent.get('is_lf', 0),
        'is_owe': parent.get('is_owe', 0),
        'agreement_status': parent.get('agreement_status', ''),
        'deposit_status': parent.get('deposit_status', ''),
        'agreement_type': parent.get('agreement_type', ''),
        'agreement_type_raw': parent.get('agreement_type_raw', ''),
        'pkg': parent.get('pkg', ''),
        'bsn': parent.get('bsn', ''),
        'bcl': parent.get('bcl', ''),
        'bco': parent.get('bco', ''),
        'bcv': parent.get('bcv', 0),
        'cabn': parent.get('cabn', ''),
        'soc': parent.get('soc', ''),
        'online': parent.get('online', ''),
        'bat_anomaly': parent.get('bat_anomaly', False),
        'visit_result': 'pending',
        'visited_at': None,
        'rec_category': parent.get('rec_category', DEFAULT_CAT),
    }
    items.append(new)
    save('assignments.json', asg)
    return new


if __name__ == '__main__':
    run_assignment(mode='force')
