# -*- coding: utf-8 -*-
# 版本：v10.28 · 2026-08-25（离线号段版 + 真实定位字段接入）
#   v10.28：① 接入 cb_battery.last_location_address / last_location_time
#            —— 「车辆最后定位地址」改读 it.lla(cb_battery.last_location_address)，回退 it.cloc
#            —— 新增「最后有效定位时间」列（it.llt 毫秒戳 → yyyy-MM-dd HH:mm:ss）
#   v10.27：同步 build_lists.py v10.27 离线号段版（仅本地 phone.dat，锁死关闭 ip138）。
#   v10.26：归属地升级 + dnr 按计划回访日 + 月均频次格式化
#     ① 手机号归属地：支持 --use-ip138（号段库查不到时调 ip138.com Web 接口，输出字段新增 psrc 标记来源 seg/ip138）
#     ② 距今未换电天数(dnr)：公式改为 计划回访日期 − 电池最新一条流通记录时间（lcts 毫秒戳）。
#        build 输出 lcts，前端用 (planDate - new Date(lcts))/86400000 实时算；planDate 变化时表格自动重算
#     ③ 月均换电频次：渲染统一格式化为 "X.X次/月"（swf 数值不变）
#   v10.25：数据为空根因修复 + 换电周期预判
#     ① 根因：v10.22/v10.24 字段在 build_lists.py 用「长键」写出（monthly_swap_freq/swap_cycle_days/...），
#        assign.py 读「短键」（swf/scy/...），键名对不上导致 5 个字段全空。统一为短键后正常。
#     ② 换电周期 = 同一协议历次归还的中位间距（天），比首末差更稳健
#     ③ 新增「下次预计换电日」= 末次换电 + 中位间距
#     ④ 新增 SQL 取每个协议全量 back_battery_time 序列（aid_swap_times）
#   v10.24：回访排班指标升级
#     ① 手机号归属地：直接显示城市名（如「深圳」「茂名」），不与租赁省做本地/外地对比（替代 v10.22 的 ploc）
#     ② 距今未换电天数：公式改为 今天 − 电池最新一条「任意」流通记录时间（替代 v10.22 的 dns）
#     ③ 车辆最后定位地址：新增列，位于「电池SN」之后（来源 cb_battery_circulate_log.addr；DB 探测后回填，
#        当前表内无 addr 字段时回退 loc 网点名）
#     ④ 月均换电频次 + 换电周期：移到归属地之后（不依赖 v10.22 的本地/外地对比）
#   v10.23：①回访看板-底部明细列 chip 后加 (N) 计数（标签按 TS_TAG_MAP 合并大类） ②回访看板-新增「导出当前接待名单 CSV」
#         ③排班总览-顶部新增「回访结果标签数量统计」（已回访/待回访 × outcome 聚合，点击下钻）
#   v10.22：回访排班新增指标 —— 月均换电频次 / 换电周期(天) / 未换电天数 / 当前手机号本地·外地(内置号段库比租赁省份) /
#           电池最后定位(最新流通网点) / 新增「流通季度」筛选维度
#   v10.21.6：实时同步（解决「同事同步数据库/追加排班，主服务器看不到」）
#             后端写操作（同步数据库/追加排班/分配/清空调度）后 bump DATA_VERSION；前端每 5s 轮询 /api/version，
#             版本变化即自动 loadDispatch() 刷新，主服务器与所有客户端共享同一份 out/ 数据，操作互相可见。
#   v10.21.5：电池电量实时刷新（解决「电量显示不是当前的」）
#             build_lists.py 只在生成名单时一次性快照 cb_battery_status.power，之后不再更新，
#             导致服务台 64%、看板 0%。新增 /api/battery_now?sn=... 实时端点（同服务台口径取最新一条），
#             前端 dispatch 系列视图首屏 + 每 30s 增量拉取，按 SN 覆盖 dData.items 的 soc/onl 然后 render。
#   v10.21.2：
#     - 配合后端修复：assign.py 新增 _dedup_items + load_assignments 去重（同一协议+同日期+同来源
#       保留 created_at 最新），前端不需要改；运行后端后重复分配记录自动消失。
#   v10.21.1：
#     - 修复按人权限失效：深链 IIFE 同步读 dData.staff.user_permissions，但 staff 由 fetch 异步填充，
#       导致同步读永远为空、命中 fallback（仅 dispatch+dispatch_schedule 两个 tab），
#       配置的可见模块（回访看板等）显示不出。改为异步 applyDeepLink() 先 fetch /api/staff 再应用权限，
#       并在应用后重新 render。
#   v10.21：
#     - 冻结「今日待分配」「回访调度」表头（.tbl-scroll 容器，纵向/横向滚动列名固定）。
#     - 「清空重生成」按计划日期全量清空当日任务后重生。
#     - 7 天冷却修复：纳入所有带接待时间的记录（仅排除纯系统类），"待再次回访"真实接触也触发冷却。
#     - 电池异常原因重做：取流通表最新一条记录展示「时间 因【操作类型】流通至【位置】」；新增「最后流通类型」筛选维度。
#     - 按人权限：新增「人员权限」弹窗，按人配置可见模块+可同步，生成 ?user= 专属链接；共享模式按人限制模块，can_sync 放行同步按钮。
#   v10.20：
#     - 协议状态文字全站统一：「生效中 / 欠租 / 退订中」（不再叫「正常」）。
#     - 新增「当前手机号」列：5 个菜单（全部活跃协议/欠租催收/低频用户/回访排班/回访调度）展示；
#       数据来自 cb_user.mobile / cb_user.phone（3 档 try / 退化 cb_exchange_agreement.user_phone）。
#     - 追加排班重构：点 ➕追加排班 → 弹窗选人 + 各自接待数量 → 后端 mode='extra' 仅对这几个人分配，
#       原名单完全不动（彻底解决"单人回访数量翻倍"）。
#     - 「近 N 天换电过滤」可通过 db_conf.json::recent_swap_filter_days 开启（默认 0 不过滤）。
#   v10.19.2：
#     - 「标记为无需回访」下拉新增「空号联系不上」「系统数据错误·4814电池」两个 reason，
#       与 nofollow 黑名单联动：选了某 reason 后该 aid 自动进 NO_FOLLOWUP_AIDS，
#       下次同步数据库后不再进入回访名单（同类排除）；并归入「无需回访」Tab 明细里。
#   - 回访名单优先级排序：电量<25% 优先 → 未回访过优先 → 最近回访时间远优先
#   - 冷却窗口（默认5天）：N 天内已回访的协议不进今日名单
#   - 三种生成模式：🟢生成回访名单(增量) / ➕追加排班(增量) / 🔄清空重生成(覆盖) / 🔄同步刷新(仅重平衡待回访)
__VERSION__ = 'v10.28.57'  # v10.28.57：rows 改列式+字典编码+base64 位打包，看板 HTML 28.8MB → 2.1MB
# v10.28.55：注入手机号归属地 fallback 字典到 window.__PHONE_FALLBACK
import json as _json  # 注：文件下方有 `import json, os`，本行为局部别名避免依赖
try:
    from phone_fallback import (
        _PHONE_FALLBACK as _BL_FB7,
        _PHONE_FALLBACK_5 as _BL_FB5,
        _PHONE_FALLBACK_3 as _BL_FB3,
    )
    _PHONE_FB_JSON = _json.dumps({'f7': _BL_FB7 or {}, 'f5': _BL_FB5 or {}, 'f3': _BL_FB3 or {}}, ensure_ascii=False, separators=(',',':'))
    print(f'[v10.28.55] 注入归属地 fallback: f7={len(_BL_FB7)} f5={len(_BL_FB5)} f3={len(_BL_FB3)} (共 {len(_PHONE_FB_JSON)//1024} KB)')
except Exception as _e_fb:
    print(f'[v10.28.55] fallback 字典加载失败: {_e_fb}')
    _PHONE_FB_JSON = '{"f7":{},"f5":{},"f3":{}}'
# 版本：v10.28.55 · 2026-09-09
#   ① 手机号归属地修复：内置号段 fallback（7位→5位→3位 三级回退），
#      phone.dat 二分查不到时也能给出城市名，覆盖所有页面（接单、全部活跃、回访排班、回访效果、低频用户、低频用户数据分析）
#   ② 接待人/标签搜索交互重做：默认只显示已选 chip + 搜索建议下拉；点选即时切换；再点取消；无需 Ctrl 多选
#   ③ 布局重排：接待人/标签容器固定 220px（和接待时间、效果、协议状态等宽），接待时间字段加宽；
#      重置/导出/计数 同行右对齐
#   距今未换电天数口径修正：record.lcts 改用协议维度（aid_swap_times[aid][-1]），
#   与客服服务台"换电操作日志"对齐。前端 calcDnr() 直接读 it.lcts，自动正确。
# 版本：v10.28.55 · 2026-09-05
#   ① 接待人/标签筛选多选 ② 排行/标签名称不再显示 0/1 序号 ③ 流通异常全量识别
#   ④ 末次流通统一格式展示 ⑤ 员工取电池/设备识别失败场景覆盖
# 版本：v10.28.55 · 2026-09-04
#   ① 接待人字段多选改造（后端 solvers 数组 + 前端筛选/分组/明细展示多值展开）
#   ② 接待人促成排行显示真实姓名（solver 存员工 ID → 后端映射 cb_admin/cb_staff 姓名）
#   ③ 退订归类校准：拆「退订中」(S10) 与「已退订·挽回失败」(S7)；user_status 同步

import sys
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
import json, os, time
BASE = os.path.dirname(os.path.abspath(__file__))
# v10.28.55：records.json 读不到/损坏时给空兜底，避免整脚本崩溃导致「打开一直加载/白屏」。
try:
    d = json.load(open(os.path.join(BASE, 'out', 'records.json'), encoding='utf-8'))
    if not isinstance(d, dict) or 'rows' not in d:
        d = {"rows": []}
except Exception as e:
    print(f"[WARN] records.json 读取失败，使用空数据兜底：{e}")
    d = {"rows": []}

# v10.28.57：records.json 注入策略大改 ——
#   保留 records.json 全量数据给其它脚本（assign.py / serve.py 仍读它）
#   dashboard.html 只注入精简 KPI 字段（22 字段）—— HTML 体积从 30MB → 8MB 左右
#   首屏解析从 5s+ → <1s
_KEEP = {
    'id','uid','cid','ph','cph','days','pd','pid','ag','pr','ci','ar','st','co','ctf',
    'status','at','atr','ac','re','dep','dst','dpw','pkg','bsn','vol','cur','soc','onl',
    'bcl','bco','bcv','cabn','ba','battery_in_storage','battery_in_storage_loc',
    'battery_in_storage_reason','priority_score','c15','c30','c45','c60','mf','sw',
    'swf','scy','dns','nse','ploc','bloc','cq','pcity','dnr','cloc','lcts','bsn_lcts',
    'aid_last_swap_ms','psrc','lla','llt','rt','rs','rty','rd','rc','lf','lv','ln',
    'owe','tags','excluded','followable','rc15','rcnd','cot','nf','socr','socc','soage','sost',
}
def _trim_row(r):
    if not isinstance(r, dict):
        return r
    return {k: r[k] for k in _KEEP if k in r}

# ============================================================================
# v10.28.57 性能核心：rows 列式 + 字典编码
#   原方案：123k 行 × 78 字段 的行式 JSON，每行重复 78 个 key（约 700B 纯 key 开销）
#   → records.json 30MB / dashboard.html 25MB+ → 启动慢、同步慢、生成慢
#   新方案：
#     ① 常量列（全省只有一个取值）→ {"k":值}
#     ② 低基数列（城市/状态/产品/接待人…）→ 字典 + base64 位打包索引（1~2 字符/行）
#     ③ 高基数列（手机号/电池编号）→ 原样数组
#     实测 28.5MB → 1.9MB（内联）/ 294KB（gzip 传输）
# ============================================================================
_B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'


def _pack_idx(idx, nuniq):
    """把索引数组打包成 base64 字符串；基数超 262144 返回 None"""
    if nuniq <= 64:
        w = 1
    elif nuniq <= 4096:
        w = 2
    elif nuniq <= 262144:
        w = 3
    else:
        return None
    out = []
    B = _B64
    for j in idx:
        s = ''
        x = j
        for _ in range(w):
            s = B[x & 63] + s
            x >>= 6
        out.append(s)
    return ''.join(out), w


def encode_cols(rows):
    if not rows:
        return {'n': 0, 'c': {}}
    keys = []
    seen = set()
    for r in rows:
        for k in r:
            if k not in seen:
                seen.add(k)
                keys.append(k)
    n = len(rows)
    out = {}
    for k in keys:
        vals = [r.get(k) for r in rows]
        if any(isinstance(v, (list, dict)) for v in vals):
            strs = [json.dumps(v, ensure_ascii=False) for v in vals]
            d = []
            di = {}
            idx = []
            for s in strs:
                j = di.get(s)
                if j is None:
                    j = len(d)
                    di[s] = j
                    d.append(s)
                idx.append(j)
            col = {'d': d, 'j': 1}
            p = _pack_idx(idx, len(d)) if len(d) <= 262144 else None
            if p:
                col['s'] = p[0]
                col['w'] = p[1]
            else:
                col['i'] = idx
            out[k] = col
            continue
        keyed = []
        di = {}
        idx = []
        for v in vals:
            if v is None:
                key = '\x00n'
            elif v is True:
                key = '\x00t'
            elif v is False:
                key = '\x00f'
            elif isinstance(v, (int, float)):
                key = '#' + repr(v)
            else:
                key = '$' + str(v)
            j = di.get(key)
            if j is None:
                j = len(keyed)
                di[key] = j
                keyed.append(v)
            idx.append(j)
        if len(keyed) == 1:
            out[k] = {'k': vals[0]}
            continue
        raw_cost = sum(len(json.dumps(v, ensure_ascii=False)) + 1 for v in vals)
        dict_cost = sum(len(json.dumps(v, ensure_ascii=False)) + 2 for v in keyed) + len(idx) * 3
        if dict_cost < raw_cost * 0.92:
            col = {'d': keyed}
            p = _pack_idx(idx, len(keyed)) if len(keyed) <= 262144 else None
            if p:
                col['s'] = p[0]
                col['w'] = p[1]
            else:
                col['i'] = idx
            out[k] = col
        else:
            out[k] = {'v': vals}
    return {'n': n, 'c': out}

# v10.28.57：reception_detail 不再注入 HTML（最多 1.4MB，但用户数据 5x 大后会到 7MB）
#   由前端在切到「回访看板」Tab 时按需 fetch /api/reception_detail
_trimmed_rows = [_trim_row(r) for r in (d.get('rows', []) or [])]
_t0 = time.time()
COLS = encode_cols(_trimmed_rows)
COLS_JSON = json.dumps(COLS, ensure_ascii=False, separators=(',', ':')).replace('</script>', '<\\/script>')
print('[v10.28.57] 列式编码：%d 行 × %d 列 → %s（%.1f KB，gzip 前）'
      % (COLS['n'], len(COLS['c']),
         ('%d 列常量/%d 列打包/%d 列原样' % (
             sum(1 for v in COLS['c'].values() if 'k' in v),
             sum(1 for v in COLS['c'].values() if 's' in v),
             sum(1 for v in COLS['c'].values() if 'v' in v))),
         len(COLS_JSON.encode('utf-8')) / 1024.0))

_d_dashboard = dict(d)
_d_dashboard['rows'] = []                 # v10.28.57：明细不再内联，改由 __COLS__ 列式展开
# v10.28.57：reception_detail 内联进 HTML（仅 166 条，约几十 KB），
#   既保证静态发布（无后端）时明细视图可用，本地服务也可经 /api/reception_detail 刷新。
# v10.28.57-hotfix：records.json 里 reception_detail 实际是 dict{id:row}，前端用 .filter/.flatMap 会报
#   "is not a function"。这里统一转 list，确保 DATA.reception_detail 是数组。
_rd = d.get('reception_detail')
if isinstance(_rd, dict):
    _d_dashboard['reception_detail'] = list(_rd.values())
elif isinstance(_rd, list):
    _d_dashboard['reception_detail'] = _rd
else:
    _d_dashboard['reception_detail'] = []
_d_dashboard['_colsn'] = COLS['n']

records_summary = {
    'now': d.get('now', ''),
    'total': d.get('total', 0),
    '_meta': d.get('_meta', {}),
}
RECORDS_SUMMARY_JSON = json.dumps(records_summary, ensure_ascii=False, separators=(',', ':')).replace('</script>', '<\\/script>')

DATA_JSON = json.dumps(_d_dashboard, ensure_ascii=False, separators=(',', ':')).replace('</script>', '<\\/script>')

HTML = r"""<!DOCTYPE html>
<!-- v10.28.55 force_v4 NUCLEAR：fmtSolver 兜底提前到 <!DOCTYPE> 之前——浏览器解析到第二行就有 fmtSolver 定义 -->
<script>window.fmtSolver=window.fmtSolver||function(n){if(n==null||n==='')return'—';var s=String(n);return/^\d{1,6}$/.test(s)?'员工#'+s:s;};window.solverSortKey=window.solverSortKey||function(n){return String(n||'').replace(/^员工#/,'￿');};window._storageBadge=window._storageBadge||function(){return '';};window.__forceV4=true;</script>
<!-- v10.28.56：手机号归属地三级兜底 ①数据自带 pcity ②phoneCityFallback 离线字典 ③fetch 在线调用 ip138.com（用户浏览器有网时自动补全） -->
<script>
window.__PHONE_FB_VERSION__='v10.28.56';
window.__PHONE_FALLBACK=__PHONE_FB__;
window.__PHONE_ONLINE_CACHE=window.__PHONE_ONLINE_CACHE||{};   // 浏览器 sessionStorage 缓存防重复请求
try{var _stored=sessionStorage.getItem('__PHONE_ONLINE_CACHE__'); if(_stored){ for(var k in JSON.parse(_stored)) window.__PHONE_ONLINE_CACHE[k]=JSON.parse(_stored)[k]; }}catch(e){}
window._pcSaveCache=function(){try{sessionStorage.setItem('__PHONE_ONLINE_CACHE__', JSON.stringify(window.__PHONE_ONLINE_CACHE));}catch(e){}};
window.phoneCityOffline=function(num){
  if(!num) return '';
  var s=String(num).replace(/\D/g,'');
  if(s.length<3) return '';
  var fb=window.__PHONE_FALLBACK||{f7:{},f5:{},f3:{}};
  if(s.length>=7 && fb.f7[s.substring(0,7)]) return fb.f7[s.substring(0,7)];
  if(s.length>=5 && fb.f5[s.substring(0,5)]) return fb.f5[s.substring(0,5)];
  return fb.f3[s.substring(0,3)]||'';
};
// 在线兜底：ip138.com（无需 key，CORS 允许），失败回退百度 / 360
window.phoneCityOnline=function(num){
  return new Promise(function(resolve){
    if(!num){resolve('');return;}
    var s=String(num).replace(/\D/g,'');
    if(s.length<7){resolve('');return;}
    var key='pc_'+s.substring(0,7);
    if(window.__PHONE_ONLINE_CACHE[key]){resolve(window.__PHONE_ONLINE_CACHE[key]);return;}
    // 优先 ip138：返回 HTML，正则匹配归属地
    fetch('https://www.ip138.com/mobile.asp?mobile='+s.substring(0,7), {mode:'cors',cache:'no-store'})
      .then(function(r){return r.text();})
      .then(function(html){
        var m=html.match(/手机号码归属地[\s\S]*?<td[^>]*>([\u4e00-\u9fa5]+)/);
        var city=(m && m[1]) || window.phoneCityOffline(s.substring(0,7));
        window.__PHONE_ONLINE_CACHE[key]=city;
        window._pcSaveCache();
        resolve(city);
      })
      .catch(function(){
        // 回退 360：api.viptv.wiki 等
        fetch('https://mobsec-dianhua.shouji.360.cn/phoneaddressdetail/index?number='+s.substring(0,7)+'&type=mobile')
          .then(function(r){return r.json();})
          .then(function(j){
            var city=(j && j.data && j.data.province_city && j.data.province_city.replace(/^\s*|\s*$/g,'')) || window.phoneCityOffline(s.substring(0,7));
            window.__PHONE_ONLINE_CACHE[key]=city;
            window._pcSaveCache();
            resolve(city);
          })
          .catch(function(){resolve(window.phoneCityOffline(s.substring(0,7)));});
      });
  });
};
window.fmtPcity=function(r){
  // 1. 优先数据自带 pcity
  if(r && r.pcity) return r.pcity;
  var ph=(r&&(r.ph||r.cph||''))||'';
  // 2. 离线字典（同步）
  var off=window.phoneCityOffline(ph);
  if(off) return off;
  // 3. 在线兜底（异步，init 时后台触发）
  return '—';
};
// v10.28.56：页面加载后对所有缺归属地的记录发起一次在线补全
window._pcEnrich=function(rows){
  if(!rows || !rows.length) return;
  var seen={};
  rows.forEach(function(r){
    if(r.pcity){return;}
    var ph=String(r.ph||r.cph||'').replace(/\D/g,'');
    if(ph.length<7){return;}
    var k=ph.substring(0,7);
    if(seen[k]){if(!r.pcity) r.pcity=window.__PHONE_ONLINE_CACHE[k]||''; return;}
    seen[k]=1;
    if(window.__PHONE_ONLINE_CACHE[k]){r.pcity=window.__PHONE_ONLINE_CACHE[k]; return;}
    window.phoneCityOnline(ph).then(function(city){ r.pcity=city; });
  });
};
</script>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>低频用户 · 欠租催收回访看板</title>
<!-- v10.28.55 hotfix3 / force_v4：浏览器/中间层缓存兜底——四道防线
     ① 立即定义 fmtSolver / solverSortKey / _storageBadge 等关键函数（防 ReferenceError）
     ② 检测到旧版 HTML 标记（"v10.28.55 新增"）自动强刷一次（绕过 HTTP 缓存）
     ③ 检测 window.__forceV4 标记——如果未定义说明命中了更老的 HTML，立即强刷
     ④ sessionStorage 防重入，避免极端情况下无限刷新
     即便浏览器/CDN/反代层命中旧 HTML，也能自我修复到 v10.28.55 -->
<script>
(function(){
  try {
    // ① 关键函数兜底（数字 ID 直接显示为「员工#N」）
    if (typeof window.fmtSolver !== 'function') {
      window.fmtSolver = function(name){
        if (name == null || name === '') return '—';
        var s = String(name);
        if (/^\d{1,6}$/.test(s)) return '员工#' + s;
        return s;
      };
    }
    if (typeof window.solverSortKey !== 'function') {
      window.solverSortKey = function(name){
        return String(name || '').replace(/^员工#/, '￿');
      };
    }
    if (typeof window._storageBadge !== 'function') {
      window._storageBadge = function(){ return ''; };
    }
    // ②③ 自动强刷：检测到旧版本 HTML 标识字符串 / 未定义 __forceV4 标记就强刷一次
    var __vTag = document.documentElement.outerHTML || '';
    var __isOld = (__vTag.indexOf('v10.28.55 新增') >= 0) ||
                  (__vTag.indexOf('fmtSolver is not defined') >= 0) ||
                  (typeof window.__forceV4 === 'undefined');
    if (__isOld) {
      var __k = '__lowfreq_force_reload__';
      var __cnt = parseInt(sessionStorage.getItem(__k) || '0', 10);
      if (__cnt < 3) {
        sessionStorage.setItem(__k, String(__cnt + 1));
        var u = location.href.split('#')[0];
        u += (u.indexOf('?') >= 0 ? '&' : '?') + 'cb=' + Date.now();
        location.replace(u);
      }
    } else {
      try { sessionStorage.removeItem('__lowfreq_force_reload__'); } catch(e) {}
    }
  } catch (e) { /* 兜底脚本不能失败 */ }
})();
</script>
<style>
:root{--blue:#1F4E78;--red:#C0392B;--org:#E67E22;--green:#16a34a;--bg:#f0f3f7;--card:#fff;--line:#e1e6ec;--muted:#8a94a6}
*{box-sizing:border-box;font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;color:#222;margin:0}
body{background:var(--bg)}
.topbar{background:linear-gradient(135deg,#1F4E78,#2c5282);color:#fff;padding:16px 22px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;box-shadow:0 2px 10px rgba(31,78,120,.18)}
.topbar .title{font-size:19px;font-weight:800;letter-spacing:.5px}
.topbar .meta{font-size:12px;opacity:.9}
.tabs{display:flex;gap:6px;padding:10px 22px 0;overflow-x:auto;background:#f0f4f9}
.tabs button{border:none;background:transparent;color:#445;padding:9px 18px;font-size:13.5px;cursor:pointer;border-radius:10px 10px 0 0;white-space:nowrap;font-weight:600;transition:.15s}
.tabs button:hover{background:rgba(31,78,120,0.06);color:var(--blue)}
.tabs button.active{background:#fff;color:var(--blue);font-weight:800;box-shadow:0 -2px 8px rgba(31,78,120,.1)}
.tabs::-webkit-scrollbar{height:6px}
.filters{background:var(--card);padding:14px 22px;border-bottom:1px solid var(--line)}
.filters-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px 14px}
.filters label{display:flex;flex-direction:column;font-size:12px;color:#666;gap:4px}
.filters select,.filters input{width:100%;padding:7px 9px;border:1px solid var(--line);border-radius:8px;font-size:13px;background:#fff}
.filters-actions{display:flex;gap:10px;justify-content:flex-end;margin-top:12px}
.filters .primary{background:var(--blue);color:#fff;border:none;padding:9px 18px;border-radius:8px;cursor:pointer;font-size:13px}
.filters #btnReset{background:#f1f5f9;color:#445;border:1px solid var(--line);padding:9px 16px;border-radius:8px;cursor:pointer;font-size:13px}
.kpis{display:flex;flex-flow:row nowrap;gap:12px;padding:14px 22px;align-items:stretch;width:100%;box-sizing:border-box}
.kpi{flex:1 1 25%;max-width:25%;min-width:0;position:relative;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;box-shadow:0 2px 8px rgba(31,78,120,.06);overflow:hidden;display:flex;flex-direction:column;justify-content:space-between}
.kpi::before{content:'';position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--blue)}
.kpi.red::before{background:var(--red)}
.kpi.org::before{background:var(--org)}
.kpi.vio::before{background:#7c3aed}
.kpi .ic{position:absolute;right:14px;top:14px;width:30px;height:30px;border-radius:9px;display:flex;align-items:center;justify-content:center}
.kpi .ic svg{width:18px;height:18px;fill:#fff}
.kpi.blue .ic{background:var(--blue)}.kpi.red .ic{background:var(--red)}.kpi.org .ic{background:var(--org)}.kpi.vio .ic{background:#7c3aed}
.kpi .n{font-size:clamp(22px,2.8vw,30px);font-weight:800;line-height:1.1;color:var(--blue);letter-spacing:-.5px;white-space:nowrap}.kpi.red .n{color:var(--red)}.kpi.org .n{color:var(--org)}.kpi.vio .n{color:#7c3aed}
.kpi .t{font-size:13px;color:#555;margin-top:4px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kpi .src{font-size:11px;color:var(--muted);margin-top:8px;line-height:1.5;white-space:normal;word-break:break-word;max-height:3.1em;overflow:hidden}
.charts{display:flex;gap:14px;flex-wrap:wrap;padding:0 22px 14px}
.card{flex:1;min-width:280px;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;box-shadow:0 2px 8px rgba(31,78,120,.05)}
.card h3{font-size:13px;margin-bottom:10px;color:#333;font-weight:700}
.bar{display:flex;align-items:center;gap:8px;margin:5px 0;font-size:12px}
.bar .bl{height:13px;border-radius:3px;display:inline-block}
.bar b{width:120px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bar i{font-style:normal;color:#555;width:48px;text-align:right}
.tablewrap{padding:0 22px 24px}
.tblmeta{font-size:12px;color:#666;margin:6px 2px}
table{width:100%;border-collapse:collapse;background:#fff;font-size:12px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
th,td{padding:6px 10px;border-bottom:1px solid #eef1f5;text-align:left;white-space:nowrap}
th{background:#f3f6fa;color:#555;font-weight:600;cursor:pointer;position:sticky;top:0;z-index:2;user-select:none}
th:hover{color:var(--blue)}
th:first-child,td:first-child{position:sticky;left:0;z-index:1}
th:first-child{top:0;left:0;z-index:3;background:#eef2f7}
td:first-child{background:#fff;font-weight:700}
tr.lv1 td:first-child{box-shadow:inset 4px 0 0 var(--red)}
tr.lv2 td:first-child{box-shadow:inset 4px 0 0 var(--org)}
tr.lv3 td:first-child{box-shadow:inset 4px 0 0 #d4a017}
tr.lv4 td:first-child{box-shadow:inset 4px 0 0 var(--green)}
td.ph{color:#C0392B;font-weight:700;font-family:Menlo,Consolas,monospace;letter-spacing:.5px}
tr.lv1{background:#fdeaea}tr.lv2{background:#fdf2e8}tr.lv3{background:#fef9e6}tr.lv4{background:#eef7ee}
.badge{padding:1px 7px;border-radius:4px;font-size:11px}.badge.owe{background:#fde0e0;color:#C0392B}.badge.lf{background:#fff0d6;color:#b8740a}.badge.unsub{background:#e8e8f7;color:#5b4db5}
input.fu{width:100%;border:1px solid #e3e3e3;border-radius:4px;padding:3px 5px;font-size:12px}
.pager{display:flex;gap:6px;align-items:center;margin-top:10px;font-size:13px}
.pager button{border:1px solid #cfd8e3;background:#fff;border-radius:6px;padding:5px 12px;cursor:pointer}
.pager button:disabled{opacity:.4;cursor:default}
.kpi .src{font-size:11px;color:#888;margin-top:6px;line-height:1.4;white-space:normal}
.stats-panel{background:var(--card);border:1px solid var(--line);border-radius:14px;margin:0 22px 14px;overflow:hidden;box-shadow:0 2px 8px rgba(31,78,120,.05)}
.stats-toggle{width:100%;display:flex;justify-content:space-between;align-items:center;padding:13px 18px;background:#f7f9fc;border:none;cursor:pointer;font-size:14px;font-weight:700;color:var(--blue)}
.stats-toggle .chev{transition:transform .2s;font-size:12px;color:var(--muted)}
.stats-panel.open .stats-toggle .chev{transform:rotate(90deg)}
.stats-body{padding:14px 18px;font-size:12px;line-height:1.7;color:#555;display:none}
.stats-panel.open .stats-body{display:block}
.stats-body h4{font-size:13px;color:var(--blue);margin-bottom:8px}
.stats-body code{font-family:Menlo,Consolas,monospace;background:#f3f6fa;padding:1px 4px;border-radius:3px;color:#333;font-size:11px}
.stats-body ul{margin:6px 0 0 18px;padding:0}
.stats-body li{margin:3px 0}
.foot{padding:10px 22px 30px;font-size:11px;color:#9aa}
.reception-filters{display:flex;gap:14px;flex-wrap:nowrap;align-items:flex-end;padding:12px 0;border-bottom:1px dashed var(--line);margin-bottom:6px}
.reception-filters label{display:flex;flex-direction:column;font-size:12px;color:#666;gap:4px;flex:0 0 auto}
.reception-filters label.rSolverLabel{flex:1 1 auto;min-width:220px}
.reception-filters input,.reception-filters select{padding:7px 9px;border:1px solid var(--line);border-radius:8px;font-size:13px}
.reception-filters #rReset{background:#f1f5f9;color:#445;border:1px solid var(--line);padding:9px 16px;border-radius:8px;cursor:pointer;font-size:13px;white-space:nowrap}
#rSolver{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:4px 8px}
#rSolver .tg{display:flex;align-items:center;gap:5px;font-size:12px;color:#555;cursor:pointer;user-select:none;padding:4px 6px;border-radius:4px}
#rSolver .tg:hover{background:#f4f8fc}
#rSolver .tg span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}
#rSolver .tg input{accent-color:var(--blue);width:13px;height:13px;cursor:pointer;flex-shrink:0}
.ms-wrap{position:relative;width:100%}
.ms-trigger{width:100%;text-align:left;padding:7px 9px;border:1px solid var(--line);border-radius:8px;font-size:13px;background:#fff;cursor:pointer;color:#445;position:relative}
.ms-trigger::after{content:'▾';position:absolute;right:10px;top:50%;transform:translateY(-50%);color:#8a94a6}
.ms-panel{position:absolute;top:100%;left:0;right:0;z-index:50;margin-top:4px;background:#fff;border:1px solid var(--line);border-radius:8px;box-shadow:0 4px 14px rgba(31,78,120,.15);padding:6px;max-height:260px;overflow:auto}
.ms-search{width:100%;padding:6px 8px;border:1px solid #e3e3e3;border-radius:6px;font-size:13px;margin-bottom:6px;box-sizing:border-box}
.ms-options .tg{display:flex;align-items:center;gap:5px;font-size:12px;color:#555;cursor:pointer;user-select:none;padding:4px 4px;border-radius:4px}
.ms-options .tg:hover{background:#f4f8fc}
.ms-options .tg input{accent-color:var(--blue);width:13px;height:13px;cursor:pointer}
.btn-mini{border:1px solid var(--line);background:#f3f6fa;border-radius:5px;padding:3px 9px;font-size:12px;cursor:pointer;color:#445}
.btn-mini:hover{background:#e8eef5}
.tagfilter{display:flex;flex-wrap:wrap;align-items:center;gap:6px 14px;padding:8px 0 4px;border-top:1px dashed var(--line);margin-top:4px}
.tagfilter .tg-lead{font-size:12px;color:#666;font-weight:600;margin-right:2px}
.tagfilter .tg{display:flex;align-items:center;gap:3px;font-size:12px;color:#555;cursor:pointer;user-select:none}
.tagfilter .tg input{accent-color:var(--blue);width:13px;height:13px;cursor:pointer}
.tagfilter .tg:hover{color:var(--blue)}
.tagfilter .tg.active{color:var(--blue);font-weight:700}
.tagcol{color:#1F4E78;font-size:11px;max-width:240px;white-space:normal;line-height:1.4}
.tg-chip{display:inline-block;background:#eef3fa;color:#1F4E78;border-radius:4px;padding:0 5px;margin:1px 2px;font-size:11px;white-space:nowrap;cursor:pointer}
.tg-chip .tg-name{margin-right:2px}
.tg-chip .tg-count{display:inline-block;background:#1F4E78;color:#fff;border-radius:9px;padding:0 5px;margin-left:3px;font-size:10px;line-height:14px;font-weight:600;min-width:14px;text-align:center}
.tg-chip:hover .tg-count{background:#c0392b}
.other-drill{color:var(--blue);font-weight:700;cursor:pointer;text-decoration:underline}
.other-drill:hover{color:#144a85}
.other-drill.zero{color:#999;font-weight:400;text-decoration:none;cursor:default}
#rectbl tbody tr{cursor:pointer}
#rectbl tbody tr:hover{background:#f4f8fc}
#recDetailTbl td.detail{white-space:normal;max-width:520px;color:#444;line-height:1.5}
#recDetailWrap{background:#fafcff;border:1px solid var(--line);border-radius:12px;padding:10px 14px}
.tagstat{background:var(--card);border:1px solid var(--line);border-radius:14px;margin:0 0 14px;overflow:hidden;box-shadow:0 2px 8px rgba(31,78,120,.05)}
.tagstat-h{padding:12px 16px;background:#f7f9fc;font-size:14px;font-weight:700;color:var(--blue);border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center}
.tagstat-h .btn{background:var(--blue);color:#fff;border:none;padding:6px 14px;border-radius:7px;cursor:pointer;font-size:12px;font-weight:600}
.tagstat-h .btn:hover{opacity:.9}
.tagstat-body{padding:12px 16px}
.tagstat-body .ts-sum{font-size:12px;color:#666;margin-bottom:10px}
.tagstat-body .bar b{width:auto;min-width:90px;max-width:200px}
.topbar-right{display:flex;align-items:center;gap:14px;flex-wrap:wrap;justify-content:flex-end}
.sync-btn{background:#fff;color:var(--blue);border:none;padding:8px 16px;border-radius:9px;cursor:pointer;font-size:13px;font-weight:700;white-space:nowrap;box-shadow:0 2px 6px rgba(0,0,0,.12);transition:.15s}
.sync-btn:hover{background:#eaf1fb;transform:translateY(-1px)}
.sync-btn:disabled{opacity:.6;cursor:default;transform:none}
.sync-btn.busy{background:#ffe9d6;color:#b8740a}
.sync-modal{position:fixed;inset:0;background:rgba(15,23,42,.55);display:none;align-items:center;justify-content:center;z-index:999}
.sync-modal.show{display:flex}
.sync-box{background:#fff;border-radius:14px;padding:22px 24px;width:min(460px,92vw);box-shadow:0 12px 40px rgba(0,0,0,.3)}
.sync-box h3{font-size:15px;margin-bottom:10px;color:var(--blue)}
.sync-box .log{background:#0f172a;color:#cbd5e1;font-size:12px;line-height:1.6;padding:10px 12px;border-radius:8px;max-height:240px;overflow:auto;white-space:pre-wrap;font-family:Menlo,Consolas,monospace;margin-top:8px}
.sync-box .bar{height:6px;background:#e6edf5;border-radius:4px;overflow:hidden;margin:10px 0}
.sync-box .bar i{display:block;height:100%;background:var(--blue);width:0;transition:width .4s}

/* 回访排班 */
.dispatch-cfg,.dispatch-card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-bottom:14px;overflow-x:auto}
.dispatch-cfg h3,.dispatch-card h3{font-size:14px;margin:0 0 10px;color:var(--blue)}
.cfg-row{display:flex;gap:14px;flex-wrap:wrap;align-items:flex-end}
.cfg-row label{display:flex;flex-direction:column;font-size:12px;color:#666;gap:4px;flex:1 1 200px}
.cfg-row textarea,.cfg-row input{padding:7px 9px;border:1px solid var(--line);border-radius:8px;font-size:13px;font-family:inherit}

/* 配置区块分隔 */
.cfg-section{border-top:1px dashed var(--line);padding-top:14px;margin-top:14px}
.cfg-section:first-of-type{border-top:none;padding-top:0;margin-top:0}
.cfg-section-title{font-size:13px;font-weight:700;color:#334155;margin-bottom:10px;display:flex;align-items:center;gap:6px}
.cfg-section-title .num{display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;background:var(--blue);color:#fff;font-size:11px}

/* 生成名单筛选卡片 */
.filter-card{background:#f8fafc;border:1px solid #dde3eb;border-radius:10px;padding:12px 14px;margin-top:8px}
.filter-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px 12px}
.filter-label{display:flex;flex-direction:column;gap:4px;font-size:12px;color:#555;font-weight:600}
.filter-label select,.filter-label input{width:100%;padding:8px 10px;border:1px solid #cbd5e1;border-radius:8px;font-size:13px;background:#fff;color:#334155;outline:none;transition:.15s}
.filter-label select:focus,.filter-label input:focus{border-color:var(--blue);box-shadow:0 0 0 3px rgba(31,78,120,.08)}
.filter-label select{appearance:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24'%3E%3Cpath fill='%238a94a6' d='M7 10l5 5 5-5z'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 10px center;padding-right:28px}
.filter-hint{font-size:11px;color:#94a3b8;margin-top:2px;font-weight:400}

/* 用户类型选择 */
.type-select{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.type-option{display:inline-flex;align-items:center;gap:8px;background:#fff;border:1px solid #cbd5e1;border-radius:8px;padding:7px 12px;cursor:pointer;user-select:none;transition:.12s}
.type-option:hover{border-color:#94a3b8;background:#f8fafc}
.type-option input[type=checkbox]{width:16px;height:16px;accent-color:var(--blue);margin:0;cursor:pointer}
.type-option .name{font-size:13px;color:#334155;font-weight:600}
.type-option.checked{border-color:var(--blue);background:#eff6ff;box-shadow:0 0 0 1px var(--blue)}
.type-option.checked .name{color:var(--blue)}
.type-hint{font-size:12px;color:#94a3b8;margin-left:4px}
.dispatch-tip{font-size:12px;color:#b8740a;margin-top:8px;min-height:14px}
.cat-stat{margin:10px 0 14px;padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:#fbfcfe}
.cat-stat-title{font-size:13px;color:#333;margin-bottom:8px;font-weight:600}
.cat-stat-row{display:flex;flex-wrap:wrap;gap:8px}
.cat-pill{display:flex;flex-direction:column;align-items:flex-start;min-width:98px;padding:6px 10px;border:1px solid var(--line);border-radius:9px;background:#fff;cursor:pointer;line-height:1.25;transition:.12s}
.cat-pill:hover{box-shadow:0 2px 8px rgba(0,0,0,.06)}
.cat-pill.active{border-color:var(--c);background:#f5f9ff}
.cat-pill b{font-size:18px;color:var(--c)}
.cat-pill span{font-size:11px;color:#666;white-space:nowrap}
.cat-badge{display:inline-block;padding:2px 7px;border-radius:6px;font-size:11px;white-space:nowrap;vertical-align:middle}
.city-badge{display:inline-block;background:#e8f5e9;color:#1b5e20;border:1px solid #c8e6c9;border-radius:4px;padding:1px 7px;font-size:11px;font-weight:600;cursor:default}
.cfg-row label .sub{font-size:11px;color:#999;font-weight:normal}
.staff-row{display:flex;flex-wrap:wrap;gap:10px;padding:6px 0;align-items:center}
.staff-card{display:inline-flex;align-items:center;gap:8px;background:#f8fafc;border:1px solid var(--line);border-radius:8px;padding:6px 10px;cursor:pointer;user-select:none}
.staff-card input{margin:0}
.staff-card .name{font-size:13px;color:#334155;min-width:48px}
.staff-card .qinput{width:66px;padding:4px 6px;border:1px solid #cbd5e1;border-radius:6px;font-size:12px}
.staff-card.disabled{opacity:.45;background:#f1f5f9}
.staff-card.disabled .qinput{display:none}
.cfg-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:8px}
.dispatch-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media (max-width:900px){.dispatch-grid{grid-template-columns:1fr}}
.meta-line{font-size:12px;color:#888;margin-bottom:8px}
.history-bar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:10px}
.history-badges{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}
.badge{background:#eef4fb;color:#1F4E78;border:1px solid #cfe0f3;border-radius:20px;padding:4px 10px;font-size:12px}
.badge.empty{color:#94a3b8;background:#f8fafc;border-color:#e2e8f0}
.prio-tag{display:inline-block;background:#C0392B;color:#fff;border-radius:4px;font-size:11px;font-weight:700;padding:1px 5px;margin-right:4px}
#schedTbl tr:has(.prio-tag){background:#fff5f4}
.filters-inline{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:10px;font-size:12px}
.filters-inline select,.filters-inline input{padding:6px 8px;border:1px solid var(--line);border-radius:7px;font-size:13px}
#todayTbl,#schedTbl,#allTbl{font-size:12px}
#todayTbl th,#schedTbl th,#allTbl th{background:#f1f5f9;position:sticky;top:0}
/* v10.21：冻结表头容器——纵向滚动时列名固定，横向滚动时首列+表头均固定 */
.tbl-scroll{position:relative;max-height:62vh;overflow:auto;border:1px solid var(--line);border-radius:10px}
#todayTbl,#schedTbl{min-width:1480px}
.tbl-scroll th{position:sticky;top:0;z-index:3}
.tbl-scroll thead th:first-child,.tbl-scroll tbody td:first-child{position:sticky;left:0;z-index:2;background:#f1f5f9}
.tbl-scroll thead th:first-child{z-index:4}
.btn{background:var(--blue);color:#fff;border:none;padding:8px 14px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:700}
.btn-ghost{background:#f1f5f9;color:#445;border:1px solid var(--line);padding:7px 12px;border-radius:8px;cursor:pointer;font-size:12px}
.mini{background:#eef4fb;color:var(--blue);border:1px solid #cfe0f3;padding:3px 9px;border-radius:6px;cursor:pointer;font-size:12px}
.ef-multi-btns{display:inline-flex;flex-direction:column;gap:2px;align-self:flex-end;margin-left:-6px}
.link-btn{background:none;border:none;color:var(--blue);cursor:pointer;font-size:11px;padding:0 2px;text-decoration:underline;line-height:1.4}
.link-btn:hover{color:#0a8a3a}
.lst{color:#888;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
/* v10.28.55：更新条紧凑+可折叠、多选框更醒目 */
.update-banner{padding:6px 14px;background:linear-gradient(90deg,#eaf3ff,#fff7e6);border-bottom:2px solid #f5a623;position:sticky;top:0;z-index:9999;box-shadow:0 4px 12px rgba(0,0,0,.06)}
.update-banner.collapsed .update-row2{display:none}
.update-banner .update-toggle{background:none;border:1px solid #d0d8e5;color:var(--blue);border-radius:5px;padding:1px 8px;cursor:pointer;font-size:12px;margin-left:6px}
.update-banner .update-toggle:hover{background:#dbe7f7}
.update-row1{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.update-row2{display:flex;align-items:center;gap:8px;margin-top:4px;flex-wrap:wrap}
.update-row2 input{flex:1 1 280px;min-width:200px;padding:5px 9px;border:1px solid var(--line);border-radius:6px;font-size:12px}
/* v10.28.55：筛选容器视觉统一 —— 与 .filters label 完全等宽等高，
   默认和「接待时间 / 效果 / 协议状态」一致，不加蓝边/阴影 */
.ef-multiselect{display:flex;flex-direction:column;font-size:12px;color:#666;gap:4px;min-width:0;width:100%}
.ef-multiselect>label{display:flex;align-items:center;gap:4px;font-size:12px;color:#666}
.ef-multiselect>select,.ef-multiselect>input{padding:7px 9px;border:1px solid var(--line);border-radius:8px;font-size:13px;background:#fff;color:#222}
.ef-multiselect .ef-hint{font-size:10px;color:#888;font-weight:400;margin-left:4px}
.ef-multiselect .ef-actions{display:flex;gap:4px;margin-top:2px;font-size:11px}
.ef-multiselect .ef-actions button{flex:1;background:#f1f5f9;color:#445;border:1px solid var(--line);border-radius:4px;padding:2px 6px;cursor:pointer;font-weight:600}
.ef-multiselect .ef-actions button:hover{background:#e2e8f0;color:#1F4E78}
.ef-multiselect .ef-search{padding:5px 9px;font-size:12px;background:#fff;color:#333;margin-bottom:0}
.ef-multiselect .ef-search:focus{border-color:#0a6cff;outline:none}
.ef-multiselect .ef-search::placeholder{color:#aab;font-size:11px}
/* v10.28.55: chip+推荐下拉 */
.ef-multiselect .ef-chips{display:flex;flex-wrap:wrap;gap:3px;min-height:0;max-height:54px;overflow-y:auto;padding:1px 0}
.ef-multiselect .ef-chips:empty{display:none}
.ef-multiselect .ef-chip-tag{display:inline-flex;align-items:center;gap:3px;background:#dbeafe;color:#1e40af;border:1px solid #93c5fd;border-radius:10px;padding:1px 6px 1px 8px;font-size:11px;line-height:18px;cursor:pointer;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ef-multiselect .ef-chip-tag:hover{background:#bfdbfe;border-color:#60a5fa;color:#1e3a8a}
.ef-multiselect .ef-chip-tag .ef-x{font-weight:bold;opacity:.5;font-size:10px}
.ef-multiselect .ef-chip-tag:hover .ef-x{opacity:1}
.ef-multiselect .ef-input-wrap{position:relative}
.ef-multiselect .ef-suggest{position:absolute;left:0;right:0;top:100%;background:#fff;border:1px solid var(--line);border-radius:6px;box-shadow:0 4px 12px rgba(15,99,170,.12);max-height:200px;overflow-y:auto;z-index:100;margin-top:2px}
.ef-multiselect .ef-suggest[hidden]{display:none}
.ef-multiselect .ef-suggest .ef-sg{display:flex;align-items:center;gap:6px;padding:5px 9px;cursor:pointer;font-size:12px;color:#1f2937;border-bottom:1px solid #f1f5f9}
.ef-multiselect .ef-suggest .ef-sg:last-child{border-bottom:none}
.ef-multiselect .ef-suggest .ef-sg:hover{background:#eff6ff;color:#1F4E78}
.ef-multiselect .ef-suggest .ef-sg.sel{background:#dbeafe;color:#1e40af;font-weight:600}
.ef-multiselect .ef-suggest .ef-sg .ef-check{margin-left:auto;color:#0a6cff;font-weight:bold;width:14px}
.filters-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;align-items:start}
/* 标签弹窗 */
.tag-modal{position:fixed;inset:0;background:rgba(15,23,42,.55);display:none;align-items:center;justify-content:center;z-index:1000}
.tag-modal.show{display:flex}
.tag-box{background:#fff;border-radius:14px;padding:20px 22px;width:min(520px,94vw);box-shadow:0 12px 40px rgba(0,0,0,.3)}
.tag-box h3{font-size:15px;margin:0 0 12px;color:var(--blue)}
.tag-tabs{display:flex;gap:6px;margin-bottom:12px}
.tag-tabs button{border:none;background:#e2e8f0;color:#445;padding:7px 14px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600}
.tag-tabs button.active{background:var(--blue);color:#fff}
.tag-options{display:flex;flex-wrap:wrap;gap:8px;max-height:260px;overflow:auto;padding:4px 0}
.tag-options label{display:flex;align-items:center;gap:5px;background:#f3f6fa;border:1px solid var(--line);padding:6px 10px;border-radius:8px;font-size:13px;cursor:pointer;user-select:none}
.tag-options input{accent-color:var(--blue)}
.tag-actions{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:14px;font-size:12px}
.tag-actions select,.tag-actions input{padding:6px 8px;border:1px solid var(--line);border-radius:7px;font-size:13px}
/* 替换用户弹窗 */
.rep-search{margin:8px 0}
.rep-search input{width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:8px;font-size:13px}
.rep-tip{font-size:12px;color:#666;margin:6px 0}
.rep-list{max-height:340px;overflow:auto;margin:8px 0;border:1px solid var(--line);border-radius:8px}
.rep-item{padding:8px 10px;border-bottom:1px solid #f0f3f7;cursor:pointer}
.rep-item:last-child{border-bottom:none}
.rep-item:hover{background:#f4f8fc}
.rep-main{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.rep-phone{font-weight:700;color:#C0392B;font-family:Menlo,Consolas,monospace;letter-spacing:.5px}
.rep-meta{font-size:12px;color:#888}
.rep-sub{font-size:12px;color:#666;margin-top:2px}
.rep-abn{font-size:11px;color:#c0392b;margin-top:2px}
.rep-btn{background:#fff;color:#b8740a;border:1px solid #f0c08a;padding:3px 9px;border-radius:6px;cursor:pointer;font-size:12px;font-weight:600}
.rep-btn:hover{background:#fff7ed}

@media (max-width:1024px){.filters-grid{grid-template-columns:repeat(auto-fill,minmax(150px,1fr))}}
@media (max-width:768px){.topbar .meta{font-size:11px}.filters-grid{grid-template-columns:repeat(2,1fr)}.card{min-width:100%}}
@media (max-width:480px){.filters-grid{grid-template-columns:1fr}.tablewrap{-webkit-overflow-scrolling:touch}.topbar{padding:12px 14px}.filters,.kpis,.charts{padding-left:14px;padding-right:14px}.stats-panel{margin-left:14px;margin-right:14px}.tabs{padding-left:14px}.kpi{padding:12px 13px}.kpi .n{font-size:clamp(18px,5vw,24px)}.kpi .t{font-size:12px}.kpi .src{display:none}}
/* 共享查看模式：隐藏批量改派勾选列 */
body.shared .batch-sel{display:none!important}
body.shared #aiClassifyBtn,body.shared #aiClassifyTip,body.shared .rep-btn{display:none!important}
body.shared .rep-btn{display:none!important}
/* v10.28.55：分析面板 + KPI 卡 视觉优化 */
.panel{background:linear-gradient(180deg,#ffffff 0%,#fafcff 100%);border:1px solid #e2e8f0;border-radius:10px;padding:14px 16px;box-shadow:0 1px 3px rgba(15,23,42,.04);transition:box-shadow .15s}
.panel:hover{box-shadow:0 2px 8px rgba(15,23,42,.08)}
.panel .ph{color:#1F4E78;font-size:13px;font-weight:700;margin-bottom:8px;padding-bottom:6px;border-bottom:1px dashed #d6e1ee;display:flex;align-items:center;gap:6px}
.panel .ph::before{content:'';display:inline-block;width:3px;height:14px;background:linear-gradient(180deg,#1F4E78,#3a5a8c);border-radius:2px}
#efKpi .kpi-card{background:linear-gradient(180deg,#ffffff 0%,#f7faff 100%);transition:transform .15s,box-shadow .15s}
#efKpi .kpi-card:hover{transform:translateY(-1px);box-shadow:0 3px 10px rgba(15,99,170,.12)}
/* v10.28.55：接待人/标签筛选容器由 min-width:200px 改为 width:100% 与其他 label 等宽 */
</style></head>
<body>
<div id="noServeBanner" style="display:none;background:#c0392b;color:#fff;padding:10px 16px;font-size:14px;line-height:1.6;text-align:center;position:sticky;top:0;z-index:10000">
  [WARN]️ <b>你正在直接双击打开本地 HTML 文件</b>，因此「同步数据库」按钮不可用、回访排班无数据。<br>
  请<b>关闭本页</b>，回到文件夹双击 <b>start.bat</b>（推荐，会自动打开浏览器）或 <b>run_serve.bat</b>（前台运行）启动本地服务。
</div>
<div id="lanAccessBanner" style="display:none;background:#e8f5e9;color:#1b5e20;border-bottom:1px solid #a5d6a7;padding:8px 16px;font-size:13px;line-height:1.6">
  <b>同事访问：</b><span id="lanAccessUrls" style="font-family:monospace;word-break:break-all"></span>
  <button id="copyLanLinkBtn" class="btn-ghost" style="margin-left:8px;padding:2px 10px;font-size:12px;color:#1b5e20;border-color:#a5d6a7">复制</button>
  <span id="lanAccessTip" style="color:#666;margin-left:8px"></span>
</div>
<div class="update-banner" id="updateBanner" style="background:linear-gradient(90deg,#eaf3ff,#fff7e6);border-bottom:1px solid #f5a623;padding:6px 14px;position:sticky;top:0;z-index:9999">
    <div class="update-row1">
      <span style="font-weight:700;color:#1a73e8;font-size:13px;white-space:nowrap">🔄 系统更新</span>
      <span style="color:#666;font-size:11px;white-space:nowrap" id="updateHint">粘贴更新包直链 → 一键升级（保留数据与配置）</span>
      <span style="flex:1"></span>
      <button id="updateFoldBtn" type="button" title="收起/展开更新条">▾ 收起</button>
    </div>
    <div class="update-row2">
      <input id="updateUrl" type="text" value="__DEFAULT_UPDATE_URL__" placeholder="https://…/lowfreq_local_latest.zip">
      <button id="updateBtn" class="btn" style="background:#1a7f37;padding:5px 12px;font-size:13px;white-space:nowrap">检查并更新</button>
    </div>
    <div id="updateTip" class="dispatch-tip" style="margin-top:4px;font-size:12px"></div>
  </div>
<div class="topbar">
  <div class="title">低频用户 · 欠租催收回访看板 <span id="vTag" style="font-size:12px;color:#888;font-weight:400;border:1px solid #ddd;border-radius:10px;padding:1px 8px;margin-left:6px">__VTAG__</span></div>
    <div class="topbar-right">
    <button id="btnSync" class="sync-btn">[SYNC] 同步数据库</button>
    <div class="meta">数据截止 <span id="now"></span> ｜ 本地服务模式，右上角 [SYNC] 可刷新 ｜ 手机号未脱敏</div>
  </div>
</div>
<div class="sync-modal" id="syncModal"><div class="sync-box">
  <h3 id="syncTitle">正在同步数据库…</h3>
  <div class="log" id="syncLog">准备中…</div>
  <div class="bar"><i id="syncBar"></i></div>
  <div id="syncErrWrap" style="display:none;margin-top:10px">
    <div style="font-size:12px;color:#991b1b;margin-bottom:4px">详细错误日志（可点击下方按钮复制，发给技术支持）：</div>
    <div class="log" id="syncErr" style="background:#fef2f2;color:#7f1d1d;border:1px solid #fecaca;max-height:220px"></div>
  </div>
  <div style="font-size:12px;color:#888;text-align:right;margin-top:10px" id="syncHint">请勿关闭本页 / 服务窗口</div>
  <div style="text-align:right;margin-top:10px;display:none" id="syncErrActions">
    <button class="btn" id="btnCopyErr" style="background:#555">[COPY] 复制错误日志</button>
    <button class="btn" id="btnCloseModal" style="background:#999">关闭</button>
  </div>
</div></div>
<div class="tabs" id="tabs">
  <button data-v="all" class="active">全部活跃协议</button>
  <button data-v="owe">欠租催收</button>
  <button data-v="lf">低频用户</button>
  <button data-v="analysis">低频用户数据分析</button>
  <button data-v="reception">回访看板</button>
  <button data-v="effect">回访效果</button>
  <button data-v="dispatch">回访排班</button>
  <button data-v="dispatch_schedule">回访调度</button>
  <button data-v="dispatch_overview">排班总览</button>
  <button data-v="dispatch_history">历史排班</button>
  <button data-v="no_followup">无需回访</button>
</div>
<div id="serveStatusBar" style="display:none;background:#fff3cd;color:#7c2d12;border-bottom:1px solid #f5c518;padding:8px 14px;font-size:13px;line-height:1.6;position:relative;z-index:9998">
  <span id="serveStatusIcon" style="margin-right:6px">⚠</span>
  <b id="serveStatusText">本地服务连接异常</b>
  <span id="serveStatusDetail" style="margin-left:8px;color:#7c2d12"></span>
  <button id="serveStatusRetry" class="btn" style="margin-left:12px;background:#fff;border:1px solid #f5c518;color:#7c2d12;padding:2px 10px;font-size:12px">↻ 立即重试</button>
  <button id="serveStatusHowto" class="btn btn-ghost" style="margin-left:6px;padding:2px 10px;font-size:12px">如何修复？</button>
  <span id="serveStatusHowtoBody" style="display:none;margin-top:6px;padding:8px;background:#fff8e1;border-radius:6px;border:1px dashed #f5c518">
    <b>步骤：</b>①关掉本页 ②回到 lowfreq 文件夹双击 <code>start.bat</code>（推荐，会自动打开浏览器）<br>
    ③等弹出黑色窗口显示 <code>SERVE v10.28.55 listening on 0.0.0.0:8173</code><br>
    ④浏览器访问 <code>http://127.0.0.1:8173</code>（本机）或同事给的 <code>http://&lt;你的 IP&gt;:8173/?token=...</code>（同网段）<br>
    ⑤仍异常→访问 <code>/api/diag</code> 看诊断，或访问 <code>/api/health</code> 应返回 <code>{"ok":true,"version":"v10.28.55"}</code>
  </span>
</div>
<div id="sharedBanner" style="display:none;background:#e8f0fe;color:#1a3a5f;border:1px solid #b8d2f5;padding:8px 12px;border-radius:8px;margin:8px 0;font-size:13px">共享查看模式：你仅能看到管理员授权开放的模块，且无法修改排班配置。如需操作请使用本机管理端。</div>
<div class="filters">
  <div class="filters-grid">
    <label>省份<select id="fProvince"><option value="">全部省份</option></select></label>
    <label>城市<select id="fCity"><option value="">全部城市</option></select></label>
    <label>区域<select id="fArea"><option value="">全部区域</option></select></label>
    <label>街道<select id="fStreet"><option value="">全部街道</option></select></label>
    <label>电池产品<select id="fProduct"></select></label>
    <label>协议状态<select id="fStatus"><option value="">全部</option><option value="working">working·生效中</option><option value="owe_rent">owe_rent·欠租</option><option value="unsubscribing">unsubscribing·退订中</option></select></label>
    <label>协议类型<select id="fAgreementType"><option value="">全部</option><option value="single">个人</option><option value="company">企业</option></select></label>
    <label>是否低频<select id="fIsLf"><option value="">全部</option><option value="1">是</option><option value="0">否</option></select></label>
    <label>低频档位<select id="fLevel"><option value="">全部</option><option value="1">L1·15~30天(&lt;1)</option><option value="2">L2·30~45天(&lt;2)</option><option value="3">L3·45~60天(&lt;3)</option><option value="4">L4·&gt;60天(&lt;4)</option><option value="5">L5·电量&lt;25%</option></select></label>
    <label>操作类型<select id="fBco"><option value="">全部</option><option value="柜内借出电池">柜内借出电池</option><option value="柜内归还电池">柜内归还电池</option><option value="_empty">未记录</option></select></label>
    <label>是否流通<select id="fBcv"><option value="">全部</option><option value="1">在流通</option><option value="0">暂无电池</option></select></label>
    <label>最后流通类型<select id="fCircOpType"><option value="">全部</option><option value="柜内借出">柜内借出</option><option value="换电-还电池">换电-还电池</option><option value="调拨-回收">调拨-回收</option><option value="柜内归还">柜内归还</option><option value="其他">其他</option><option value="未知">未记录</option></select></label>
    <label>发送结果<select id="fSmsr"><option value="">全部</option></select></label>
    <label>使用天数（多选·可反选）
      <div class="ms-wrap" id="fDaysWrap">
        <button type="button" class="ms-trigger" id="fDaysTrigger">全部</button>
        <div class="ms-panel" id="fDaysPanel" style="display:none">
          <div style="display:flex;gap:6px;margin-bottom:6px">
            <button type="button" class="btn-mini" id="fDaysAll">全选</button>
            <button type="button" class="btn-mini" id="fDaysInv">反选</button>
            <button type="button" class="btn-mini" id="fDaysClear">清空</button>
          </div>
          <div class="ms-options" id="fDays"></div>
        </div>
      </div>
    </label>
    <label>协议ID（精确/包含）<input id="fAgreement" placeholder="如 70023"></label>
    <label>消费者手机号（精确/包含）<input id="fPhone" placeholder="如 137 / 1380013"></label>
    <label>关键词（手机/昵称）<input id="fKw" placeholder="手机号或昵称"></label>
  </div>
  <div class="tagfilter" id="tagFilter"><span class="tg-lead">回访标签（多选·OR）：</span></div>
  <div class="filters-actions">
    <button id="btnReset">重置</button>
    <button id="btnCsv" class="primary">导出当前筛选 CSV</button>
    <button id="btnCsvAll" class="primary" style="background:#5b21b6" title="忽略所有筛选条件，导出全部记录（当前 Tab 口径）">导出全部数据 CSV</button>
  </div>
</div>
<div class="kpis" id="kpis"></div>
<div class="stats-panel" id="statsPanel">
  <button class="stats-toggle" id="statsToggle" aria-expanded="false"><span>统计口径与计算依据</span><span class="chev">▸</span></button>
  <div class="stats-body" id="statsNote"></div>
</div>
<div class="charts">
  <div class="card"><h3>低频档位分布（当前筛选）</h3><div id="chartLevel"></div></div>
  <div class="card"><h3>电池产品分布 Top10（当前筛选）</h3><div id="chartProduct"></div></div>
  <div class="card"><h3>城市分布 Top10（当前筛选）</h3><div id="chartCity"></div></div>
</div>
<div class="tablewrap" id="tblWrap">
  <div class="tblmeta" id="tblmeta"></div>
  <table id="tbl"><thead><tr>
    <th data-k="id">协议ID</th><th data-k="uid">用户ID</th><th data-k="ph">手机号</th><th data-k="cph">当前手机号</th><th data-k="smst">接收时间</th><th data-k="smsr">发送结果</th><th data-k="smsf">失败原因</th><th data-k="days">使用天数</th>
    <th data-k="pd">电池产品</th><th data-k="bsn">电池SN</th><th data-k="bcl">电池最后流通时间</th><th data-k="bco">操作类型</th><th data-k="bcv">是否流通</th><th data-k="vol">电压(V)</th><th data-k="cur">电流(A)</th><th data-k="soc">电量</th><th data-k="onl">在线状态</th><th data-k="dep">押金(元)</th><th data-k="dst">押金划扣状态</th><th data-k="pkg">租赁套餐</th>
    <th data-k="pr">省份</th><th data-k="ci">城市</th><th data-k="ar">区域</th><th data-k="st">街道</th><th data-k="co">社区</th>
    <th data-k="at">协议类型</th><th data-k="status">协议状态</th><th data-k="ac">激活时间</th><th data-k="re">租金到期</th><th data-k="c15">15天</th><th data-k="c30">30天</th>
    <th data-k="c45">45天</th><th data-k="c60">60天</th><th data-k="mf">月均</th><th data-k="lf">是否低频</th>
    <th data-k="ln">档位</th><th data-k="rt">最近接待</th><th data-k="rs">接待人</th><th data-k="rty">接待类型</th><th data-k="rd">接待内容</th>    <th data-k="fu1">跟进人</th><th data-k="fu2">跟进状态</th><th data-k="fu3">跟进备注</th><th data-k="tags">标签</th><th data-k="pcity">手机号归属地</th><th data-k="dnr">距今未换电天数</th><th data-k="swf">月均换电频次</th><th data-k="scy">换电周期(天)</th><th data-k="dns">未换电天数</th><th data-k="ploc">本地/外地</th><th data-k="bloc">电池最后定位</th><th data-k="cq">流通季度</th>
  </tr></thead><tbody id="tbody"></tbody></table>
  <div class="pager" id="pager"></div>
</div>
<div class="tablewrap" id="analysis" style="display:none">
  <div class="tblmeta" style="background:#fffbe6;border-left:3px solid #f59e0b;padding:6px 10px;margin-bottom:8px;font-size:12px">
    📊 <b>低频用户数据分析</b> · 7 个筛选维度 + 双模式导出（按筛选 / 全部 43 列全字段）。电池最后定位优先取真实地址（cb_battery.last_location_address），回退柜子编号。
  </div>
  <div class="filters" id="analysisFilters" style="display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;padding:10px 12px;background:#f8fafc;border:1px solid var(--line);border-radius:8px;margin-bottom:8px">
    <label style="display:flex;flex-direction:column;font-size:12px;color:#475569">电池产品
      <select id="aProduct" style="min-width:140px;padding:4px 6px;border:1px solid var(--line);border-radius:6px;margin-top:2px"><option value="">全部电池产品</option></select>
    </label>
    <label style="display:flex;flex-direction:column;font-size:12px;color:#475569">协议状态
      <select id="aStatus" style="min-width:140px;padding:4px 6px;border:1px solid var(--line);border-radius:6px;margin-top:2px">
        <option value="">全部</option><option value="working">working·生效中</option><option value="owe_rent">owe_rent·欠租</option><option value="unsubscribing">unsubscribing·退订中</option>
      </select>
    </label>
    <label style="display:flex;flex-direction:column;font-size:12px;color:#475569">协议类型
      <select id="aAgreementType" style="min-width:120px;padding:4px 6px;border:1px solid var(--line);border-radius:6px;margin-top:2px">
        <option value="">全部</option><option value="single">个人</option><option value="company">企业</option>
      </select>
    </label>
    <label style="display:flex;flex-direction:column;font-size:12px;color:#475569">是否低频
      <select id="aIsLf" style="min-width:100px;padding:4px 6px;border:1px solid var(--line);border-radius:6px;margin-top:2px">
        <option value="">全部</option><option value="1">是</option><option value="0">否</option>
      </select>
    </label>
    <label style="display:flex;flex-direction:column;font-size:12px;color:#475569">低频档位
      <select id="aLevel" style="min-width:140px;padding:4px 6px;border:1px solid var(--line);border-radius:6px;margin-top:2px">
        <option value="">全部</option><option value="1">L1·15~30天(&lt;1)</option><option value="2">L2·30~45天(&lt;2)</option><option value="3">L3·45~60天(&lt;3)</option><option value="4">L4·&gt;60天(&lt;4)</option><option value="5">L5·电量&lt;25%</option>
      </select>
    </label>
    <label style="display:flex;flex-direction:column;font-size:12px;color:#475569">协议ID（精确/包含）
      <input id="aAgreement" placeholder="如 70023" style="min-width:140px;padding:4px 6px;border:1px solid var(--line);border-radius:6px;margin-top:2px">
    </label>
    <label style="display:flex;flex-direction:column;font-size:12px;color:#475569">消费者手机号（精确/包含）
      <input id="aPhone" placeholder="如 137 / 1380013" style="min-width:160px;padding:4px 6px;border:1px solid var(--line);border-radius:6px;margin-top:2px">
    </label>
    <button id="aReset" style="padding:6px 14px;background:#fff;border:1px solid var(--line);border-radius:6px;cursor:pointer;font-size:12px">↺ 重置</button>
    <!-- v10.28.55：导出按钮挪到筛选条内（紧邻重置按钮），与 7 维度筛选条同屏可见 -->
    <button id="btnAnalysisCsv" class="primary" style="padding:6px 14px" title="按当前 7 个筛选条件导出 CSV">⤓ 导出筛选结果 CSV</button>
    <button id="btnAnalysisCsvAll" class="primary" style="padding:6px 14px;background:#5b21b6" title="忽略 7 个筛选维度，导出全部低频用户数据（43 列全字段）">⤓ 导出全部 CSV（43列）</button>
    <!-- v10.28.55：新增 Excel 导出（服务端 openpyxl 生成 .xlsx，数值列自动转数值） -->
    <button id="btnAnalysisXlsx" class="primary" style="padding:6px 14px;background:#166534" title="按当前 7 个筛选条件导出 Excel">⤓ 导出筛选结果 Excel</button>
    <button id="btnAnalysisXlsxAll" class="primary" style="padding:6px 14px;background:#15803d" title="忽略 7 个筛选维度，导出全部低频用户数据（43 列全字段）Excel">⤓ 导出全部 Excel（43列）</button>
  </div>
  <div class="tblmeta" id="analysisMeta"></div>
  <table id="analysisTable"><thead><tr>
    <th>协议ID</th><th>用户ID</th><th>手机号</th><th>当前手机号</th><th>租赁套餐</th><th>电池SN</th><th>电池最后流通时间</th><th>手机号归属地</th><th>距今未换电天数</th><th>月均换电频次</th><th>换电周期(天)</th><th>协议类型</th><th>协议状态</th><th>激活时间</th><th>租金到期时间</th><th>本地/外地</th><th>电池最后定位</th><th>流通季度</th><th>操作类型</th><th>是否流通</th><th>使用天数</th><th>电池产品</th><th>电压(V)</th><th>电流(A)</th><th>电量</th><th>电池状态</th><th>押金(元)</th><th>押金划扣状态</th><th>省份</th><th>城市</th><th>区域</th><th>街道</th><th>社区</th><th>15天</th><th>30天</th><th>45天</th><th>60天</th><th>月均</th><th>是否低频</th><th>档位</th><th>最近接待</th><th>接待人</th><th>接待类型</th><th>接待内容</th>
  </tr></thead><tbody id="analysisBody"></tbody></table>
  <div class="pager" id="analysisPager"></div>
</div>
<div class="tablewrap" id="reception" style="display:none">
  <div class="reception-filters">
    <label>接待开始日期<input type="date" id="rStart"></label>
    <label>接待结束日期<input type="date" id="rEnd"></label>
    <label class="rSolverLabel">接待人（多选·可搜索）
      <div class="ms-wrap" id="rSolverWrap">
        <button type="button" class="ms-trigger" id="rSolverTrigger">全部接待人</button>
        <div class="ms-panel" id="rSolverPanel" style="display:none">
          <input type="text" class="ms-search" id="rSolverSearch" placeholder="搜索接待人…">
          <div class="ms-options" id="rSolver"></div>
          <div style="display:flex;gap:6px;align-items:center;padding:8px 4px 4px;border-top:1px dashed var(--line);margin-top:6px">
            <input type="text" id="rSolverAddInput" placeholder="新增接待人姓名…" style="flex:1;min-width:0;padding:5px 8px;border:1px solid var(--line);border-radius:6px;font-size:12px">
            <button type="button" id="rSolverAddBtn" class="btn-ghost" style="padding:4px 10px;font-size:12px">+新增</button>
          </div>
          <div id="rSolverAddMsg" style="font-size:11px;color:#888;min-height:14px;padding:2px 4px"></div>
        </div>
      </div>
    </label>
    <button id="rReset">重置</button>
    <!-- v10.23：导出当前筛选的接待名单（按所选日期范围 + 接待人 + 标签） -->
    <button id="btnRecExport" class="primary" style="margin-left:6px">导出当前接待名单 CSV</button>
  </div>
  <div class="tagfilter" id="recTagFilter"><span class="tg-lead">标签（多选·OR）：</span></div>
  <div class="tagstat" id="tagStat">
    <div class="tagstat-h"><span>标签数量统计（按所选接待时间范围）</span><button class="btn" id="btnTagStat">统计</button></div>
    <div class="tagstat-body">
      <div class="ts-sum" id="tsSum">选择上方「接待开始/结束日期」与「接待人」后点击「统计」，将按接待记录统计各标签数量。</div>
      <div id="tsChart"></div>
    </div>
  </div>
  <div class="tblmeta" id="rectblmeta"></div>
  <table id="rectbl"><thead><tr>
    <th data-k="solver">接待人</th><th data-k="count">接待次数</th><th data-k="users">接待人数(去重)</th>
    <th data-k="book">回访预约</th><th data-k="owe">欠租跟进</th><th data-k="silent">沉默唤醒</th><th data-k="other">其他（点击拆分）</th><th data-k="drill">明细</th>
  </tr></thead><tbody id="rectbody"></tbody></table>
  <div id="recOtherWrap" style="display:none;margin-top:14px">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
      <div class="tblmeta" id="recOtherMeta"></div>
      <button class="btn-mini" id="recOtherClose">关闭</button>
    </div>
    <div id="recOtherStat" style="margin:6px 0"></div>
    <table id="recOtherTbl"><thead><tr>
      <th data-k="time">接待时间</th><th data-k="aid">协议ID</th><th data-k="uid">用户ID</th><th data-k="phone">手机号</th>
      <th data-k="bct">电池最后流通时间</th><th data-k="astatus">协议状态</th><th data-k="ustatus">用户状态</th>
      <th>标签</th><th>接待内容</th>
    </tr></thead><tbody id="recOtherBody"></tbody></table>
    <div class="pager" id="recOtherPager"></div>
  </div>
  <div id="recDetailWrap" style="display:none;margin-top:14px">
    <div class="tblmeta" id="recDetailMeta"></div>
    <table id="recDetailTbl"><thead><tr>
      <th data-k="time">接待时间</th><th data-k="aid">协议ID</th><th data-k="uid">用户ID</th><th data-k="phone">手机号</th>
      <th data-k="bct">电池最后流通时间</th><th data-k="astatus">协议状态</th>      <th data-k="ustatus">用户状态</th><th data-k="nf">是否需要回访</th>
      <th data-k="type">类型</th><th>标签</th><th>接待内容</th>
    </tr></thead><tbody id="recDetailBody"></tbody></table>
    <div class="pager" id="recDetailPager"></div>
  </div>
</div>

<!-- ============ v10.28.55 回访效果 Tab ============ -->
<div class="tablewrap" id="effect" style="display:none">
  <div style="margin-bottom:10px;font-size:13px;color:#444;line-height:1.6">
    📈 <b>回访实际效果</b> · 将「接待时间」与「电池借出时间」对比，结合协议状态判定用户业务状态。
    口径：接待后 90 天内发生<b>借出电池</b>才算有效促成（S1~S4）；接待后借出又归还的，仍按借出时间计为促成。
  </div>

  <!-- ① 筛选条（v10.28.55 重构：接待人/标签容器与时间/效果/状态等宽等高；重置/导出同行） -->
  <div class="filters" style="margin-bottom:10px">
    <div class="filters-grid" style="grid-template-columns:repeat(auto-fill,minmax(200px,1fr));align-items:start">
      <label>接待时间起<input type="date" id="efDateFrom"></label>
      <label>接待时间止<input type="date" id="efDateTo"></label>
      <div class="ef-multiselect ef-chip" data-multiselect>
        <label>接待人 <span class="ef-hint">搜索即选·点 chip 移除</span></label>
        <div class="ef-chips" id="efSolverChips"></div>
        <div class="ef-input-wrap">
          <input type="text" class="ef-search" data-target="efSolver" placeholder="🔍 输入姓名搜索…" autocomplete="off">
          <div class="ef-suggest" id="efSolverSuggest" hidden></div>
        </div>
        <select id="efSolver" multiple style="display:none"></select>
        <div class="ef-actions">
          <button type="button" data-sel="efSolver" data-act="all">全选</button>
          <button type="button" data-sel="efSolver" data-act="none">清空</button>
        </div>
      </div>
      <div class="ef-multiselect ef-chip" data-multiselect>
        <label>标签 <span class="ef-hint">搜索即选·点 chip 移除</span></label>
        <div class="ef-chips" id="efTagChips"></div>
        <div class="ef-input-wrap">
          <input type="text" class="ef-search" data-target="efTag" placeholder="🔍 输入标签搜索…" autocomplete="off">
          <div class="ef-suggest" id="efTagSuggest" hidden></div>
        </div>
        <select id="efTag" multiple style="display:none"></select>
        <div class="ef-actions">
          <button type="button" data-sel="efTag" data-act="all">全选</button>
          <button type="button" data-sel="efTag" data-act="none">清空</button>
        </div>
      </div>
      <label>效果<select id="efGrade"><option value="">全部效果</option></select></label>
      <label>协议状态<select id="efStatus"><option value="">全部状态</option></select></label>
      <!-- v10.28.55：重置/导出与筛选同一行 -->
      <div class="ef-actions-group" style="display:flex;flex-direction:column;gap:4px;min-width:0;width:100%">
        <label style="font-size:12px;color:#666">操作</label>
        <div style="display:flex;gap:6px;flex-wrap:wrap">
          <button class="btn" id="efReset" title="重置全部筛选条件">↻ 重置</button>
          <button class="btn" id="efExportCsv" title="导出当前筛选结果为 CSV">📄 CSV</button>
          <button class="btn" id="efExportXlsx" title="导出当前筛选结果为 Excel">📊 Excel</button>
        </div>
        <span style="font-size:11px;color:#888" id="efCount"></span>
      </div>
    </div>
  </div>

  <!-- ② 数据就绪度横幅（v10.28.55）-->
  <div id="efReady" style="display:none"></div>

  <!-- ③ KPI 卡（点击自动套用筛选）-->
  <div id="efKpi" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:12px"></div>

  <!-- ④ 分析面板 v10.28.55：左列 stack 漏斗→分布→接待人排行；右列 stack 按日/周/月→标签排行 -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px">
    <div style="display:flex;flex-direction:column;gap:12px">
      <div class="panel"><div class="ph">转化漏斗（按效果档位，点击筛选）</div><div id="efFunnel"></div></div>
      <div class="panel"><div class="ph">促成时间分布（累计）</div><div id="efDist"></div></div>
      <div class="panel"><div class="ph">接待人促成排行（点击筛选）</div><div id="efSolverRank"></div></div>
    </div>
    <div style="display:flex;flex-direction:column;gap:12px">
      <div class="panel"><div class="ph">按日/周/月统计（v10.28.55 扩展：今日/昨日/最近3天/7天/30天/本周/本月/全部）</div><div id="efPeriod"></div></div>
      <div class="panel"><div class="ph">标签促成效果</div><div id="efTagRank"></div></div>
    </div>
  </div>

  <!-- ④ 明细表 -->
  <div class="panel">
    <div class="ph">效果明细（点击行展开时间轴）</div>
    <div style="overflow-x:auto">
      <table class="tbl" id="efDetailTbl">
        <thead><tr>
          <th>用户ID</th><th>用户手机号</th><th>协议ID</th><th>接待时间</th><th>接待人</th>
          <th>标签</th><th>协议状态</th><th>首次借出</th><th>第N天</th>
          <th>末次流通</th><th>效果</th><th>产品ID</th><th>接待内容</th>
        </tr></thead>
        <tbody id="efDetailBody"></tbody>
      </table>
    </div>
    <div class="pager" id="efDetailPager"></div>
  </div>
</div>

<!-- ============ 回访排班 / 回访调度 Tab（共用配置区） ============ -->
<div class="tablewrap" id="dispatch" style="display:none">
  <div class="dispatch-cfg">
    <!-- 1. 今日排班与配额 -->
    <div class="cfg-section">
      <div class="cfg-section-title"><span class="num">1</span>今日排班与配额</div>
      <div class="cfg-row">
        <label style="flex:1 1 100%">今日排班人员（勾选上班人员并填写数量，未勾选不参与分配）
          <div id="todayStaffWrap" class="staff-row"></div>
        </label>
      </div>
    </div>

    <!-- 2. 生成名单筛选 -->
    <div class="cfg-section">
      <div class="cfg-section-title"><span class="num">2</span>生成名单筛选</div>
      <div class="filter-card">
        <div class="filter-grid">
          <label class="filter-label">电池产品
            <select id="filterProduct"><option value="">全部电池产品</option></select>
            <span class="filter-hint">留空表示不限制</span>
          </label>
          <label class="filter-label">代理商
            <select id="filterAgent"><option value="">全部代理商</option></select>
          </label>
          <label class="filter-label">城市
            <select id="filterCity"><option value="">全部城市</option></select>
          </label>
          <label class="filter-label">区域
            <select id="filterArea"><option value="">全部区域</option></select>
          </label>
          <label class="filter-label">街道
            <select id="filterStreet"><option value="">全部街道</option></select>
          </label>
          <label class="filter-label">社区
            <select id="filterCommunity"><option value="">全部社区</option></select>
          </label>
          <label class="filter-label">电池流通季度
            <select id="filterCircQuarter"><option value="">全部流通季度</option></select>
          </label>
          <label class="filter-label">协议类型
            <select id="filterAgreementType"><option value="all" selected>全部（个人+企业）</option><option value="single">个人</option><option value="company">企业</option></select>
            <span class="filter-hint">默认个人与企业协议都包含</span>
          </label>
        </div>
      </div>

      <div class="cfg-section-title" style="margin-top:12px;margin-bottom:8px">用户类型</div>
      <div class="type-select">
        <label class="type-option checked"><input type="checkbox" id="filterTypeLf" value="lf" checked> <span class="name">低频用户</span></label>
        <label class="type-option"><input type="checkbox" id="filterTypeOwe" value="owe"> <span class="name">欠租催收用户</span></label>
        <span class="type-hint">多选为并集；至少勾选一个</span>
      </div>
    </div>

    <!-- 生成回访名单主按钮（筛选区下方，醒目位置） -->
    <div class="gen-btn-row" style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:14px 0 6px">
      <button id="btnGenMain" class="btn" style="background:#1a7f37;font-size:15px;padding:12px 26px;font-weight:600">🟢 生成回访名单</button>
      <span class="cfg-tip" style="font-size:12px;color:#555">按上方「排班人员 + 回访数量 + 电池产品」生成名单，<b>保留原名单</b>，仅补充未分配的协议（中途加人用这个）。生成后名单会进入下方「今日待分配」，并与「② 回访调度」联动。</span>
    </div>

    <!-- 3. 排班参数 -->
    <div class="cfg-section">
      <div class="cfg-section-title"><span class="num">3</span>排班参数</div>
      <div class="cfg-row">
        <label>全局默认每日上限<input id="quotaDefault" type="number" min="1" value="30"></label>
        <label>未接通再次回访间隔（天）<input id="recallInput" type="number" min="1" value="3"></label>
        <label>未回访冷却窗口（天）<input id="recallCooldown" type="number" min="1" max="30" value="5" title="N 天内已回访过的协议不进今日名单；昨天才回访未联系上的，需再过 N 天后才再次回访"></label>
        <label>计划回访日期<input id="planDate" type="date"></label>
      </div>
      <div class="cfg-tip" style="font-size:12px;color:#888;margin:-4px 0 6px">生成名单将归属到「计划回访日期」（可提前排未来日期的班，如周末）；对方用「查看日期」切换到对应日即可看到。</div>
    </div>

    <!-- 操作按钮 -->
    <div class="cfg-actions" style="border-top:1px dashed var(--line);padding-top:12px;margin-top:14px">
      <button id="saveStaffBtn" class="btn">保存配置</button>
      <button id="btnAppend" class="btn btn-ghost" title="保留原名单不变，仅按当前选人+配额+产品补充分配未回访协议（= 上方「生成回访名单」）">➕ 追加排班</button>
      <button id="btnClearRegen" class="btn" style="background:#cf6a00" title="清空当日所有已生成名单后，按当前配置重新生成（覆盖，数据不对时用）">🔄 清空重生成</button>
      <button id="btnSyncTasks" class="btn-ghost" title="仅对当日【待回访】任务按当前配置重新平衡归属/配额，已回访/已作废记录保留">🔄 同步刷新任务</button>
      <button id="manageStaffBtn" class="btn-ghost">人员管理</button>
      <button id="permBtn" class="btn-ghost" title="按具体人员设置可见模块与同步数据库权限，生成专属链接">人员权限</button>
      <button id="genLinkBtn" class="btn-ghost" style="margin-left:auto;color:#1F4E78;border-color:#9cc3e6" title="生成同网络可访问的回访链接">生成回访链接</button>
    </div>
    <div class="cfg-tip" style="font-size:12px;color:#888;margin-top:6px">
      <b>➕ 追加排班</b>：保留原名单，只补新选人员/配额/产品对应的未回访协议（用于中途加人）。
      <b>🔄 清空重生成</b>：清空当日全部名单后按当前配置重来（数据不对时重抽）。
    </div>
    <div id="dispatchTip" class="dispatch-tip"></div>
  </div>

  <div class="dispatch-grid" id="dispatchTodayWrap">
    <div class="dispatch-card" style="grid-column:1 / -1">
      <h3>② 今日待分配</h3>
      <div id="activeStaffTip" class="meta-line" style="margin-bottom:8px"></div>
      <!-- v10.28.55：按 priority_score 排期（P0=1000 ≥60 天 → P1=500 30-60 天 → P2=100 <30 天 → -1=电池不在手中排除） -->
      <div style="background:#eef6ff;border:1px solid #b8d4f0;border-radius:6px;padding:8px 12px;margin-bottom:10px;font-size:12px;color:#1F4E78">
        💡 <b>排序规则（v10.28.55 升级）</b>：
        <b>① priority_score DESC</b>（P0=1000：≥60 天未流通 ≥2 个月；P1=500：30-60 天未流通；P2=100：<30 天未流通；-1=电池不在手中，已从回访名单排除） →
        ② 电量&lt;25% 优先 → ③ 未回访过的优先 → ④ 最近回访时间远的优先。
        排期口径：<b>前两个月及更早未流通的协议（≥60 天）最优先</b>，前一个月未流通的（30-60 天）次之，最近仍活跃的（<30 天）最后处理；因断充已归还柜中/被员工回收的电池不进入回访名单。
      </div>
      <div style="display:flex;gap:10px;align-items:center;margin-bottom:8px;flex-wrap:wrap">
        <label style="font-size:13px;color:#555">接待人筛选<select id="todaySolverFilter" style="margin-left:6px;padding:4px 8px;border:1px solid var(--line);border-radius:8px"><option value="">全部接待人</option></select></label>
        <label style="font-size:13px;color:#555">查看日期<input id="viewDate" type="date" style="margin-left:6px;padding:4px 8px;border:1px solid var(--line);border-radius:8px"></label>
        <div id="todayMeta" class="meta-line" style="margin:0"></div>
      </div>
      <div class="tbl-scroll"><table id="todayTbl"><thead><tr>
        <th class="batch-sel"><input type="checkbox" class="sel-all" data-target="today"></th>
        <th>协议ID</th><th>消费者ID</th><th>手机号</th><th>当前手机号</th>
        <th>手机号归属地</th><th>距今未换电天数</th><th>月均换电频次</th><th>换电周期</th><th>下次预计换电</th>
        <th>自动分配接待人</th><th>计划回访</th>
        <th>最后租赁套餐</th><th>电池SN</th><th>车辆最后定位地址</th><th>最后有效定位时间</th>
        <th>电池电量</th><th>电池状态</th><th>电池最后流通记录</th><th>异常原因</th>
        <th>上次接待人</th><th>上次接待时间</th><th>上次回访内容</th><th>协议类型</th><th>协议状态</th><th>押金划扣状态</th><th>回访分类</th><th>操作</th>
      </tr></thead><tbody id="todayBody"></tbody></table></div>
    </div>
  </div>

  <div class="dispatch-grid" id="dispatchScheduleWrap" style="display:none">
    <div class="dispatch-card" style="grid-column:1 / -1">
      <h3>② 回访调度（含未接通 +N 天再次回访）</h3>
      <div style="display:flex;gap:10px;align-items:center;margin-bottom:8px;flex-wrap:wrap">
        <label style="font-size:13px;color:#555">接待人筛选<select id="schedSolverFilter" style="margin-left:6px;padding:4px 8px;border:1px solid var(--line);border-radius:8px"><option value="">全部接待人</option></select></label>
        <div id="schedMeta" class="meta-line" style="margin:0"></div>
      </div>
      <div class="tbl-scroll"><table id="schedTbl"><thead><tr>
        <th class="batch-sel"><input type="checkbox" class="sel-all" data-target="sched"></th>
        <th>协议ID</th><th>消费者ID</th><th>手机号</th><th>当前手机号</th>
        <th>手机号归属地</th><th>距今未换电天数</th><th>月均换电频次</th><th>换电周期</th><th>下次预计换电</th>
        <th>接待人</th><th>计划回访</th>
        <th>最后租赁套餐</th><th>电池SN</th><th>车辆最后定位地址</th><th>最后有效定位时间</th>
        <th>电池电量</th><th>电池状态</th><th>电池最后流通记录</th><th>异常原因</th>
        <th>来源</th><th>上次接待人</th><th>上次接待时间</th><th>上次回访内容</th><th>协议类型</th><th>协议状态</th><th>押金划扣状态</th><th>回访分类</th><th>回访结果</th><th>操作</th>
      </tr></thead><tbody id="schedBody"></tbody></table></div>
    </div>
  </div>
  <!-- 批量改派工具条 -->
  <div id="batchBar" style="display:none;position:sticky;bottom:0;z-index:50;background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin-top:12px;box-shadow:0 4px 16px rgba(31,78,120,.12);gap:12px;align-items:center;flex-wrap:wrap">
    <span style="font-size:13px">已选 <b id="batchCount">0</b> 条</span>
    <label style="font-size:13px">改派给<select id="batchSolver" style="margin-left:6px;padding:4px 8px;border:1px solid var(--line);border-radius:8px"><option value="">选择接待人</option></select></label>
    <button id="batchReassignBtn" class="btn" style="background:#1a7f37">批量改派</button>
    <button id="batchClear" class="btn-ghost">取消选择</button>
    <span id="batchTip" style="font-size:12px;color:#888"></span>
  </div>
</div>

<!-- ============ 排班总览 Tab ============ -->
<div class="tablewrap" id="dispatch_overview" style="display:none">
  <div class="dispatch-card">
    <h3>排班总览（全部回访任务）</h3>
    <!-- v10.23：回访结果标签数量统计（按 visit_result × outcome 聚合，点击下钻） -->
    <div class="cat-stat" id="ovOutcomeStat" style="margin:6px 0 14px"></div>
    <div class="filters-inline" id="dFilters" style="align-items:flex-start">
      <label>接待人<select id="dSolver"><option value="">全部</option></select></label>
      <label>状态<select id="dStatus"><option value="">全部</option><option>待回访</option><option>已回访</option><option>已关闭</option></select></label>
      <label>省份<select id="dProvince"><option value="">全部</option></select></label>
      <label>城市<select id="dCity"><option value="">全部</option></select></label>
      <label>区域<select id="dArea"><option value="">全部</option></select></label>
      <label>街道<select id="dStreet"><option value="">全部</option></select></label>
      <label>电池产品<select id="dProduct"><option value="">全部</option></select></label>
      <label>协议状态<select id="dAgrStatus"><option value="">全部</option><option value="working">生效中</option><option value="owe_rent">欠租</option><option value="unsubscribing">退订中</option></select></label>
      <label>低频档位<select id="dLevel"><option value="">全部</option><option value="1">L1</option><option value="2">L2</option><option value="3">L3</option><option value="4">L4</option><option value="5">L5</option></select></label>
      <label>回访结果<select id="dVisitResult"><option value="">全部</option><option value="visited">已回访</option><option value="pending">未回访</option></select></label>
      <label>接待时间从<input id="dVisitFrom" type="date"></label>
      <label>接待时间到<input id="dVisitTo" type="date"></label>
      <label>使用天数（多选）
        <div class="ms-wrap" id="dDaysWrap">
          <button type="button" class="ms-trigger" id="dDaysTrigger">全部</button>
          <div class="ms-panel" id="dDaysPanel" style="display:none">
            <div style="display:flex;gap:6px;margin-bottom:6px">
              <button type="button" class="btn-mini" id="dDaysAll">全选</button>
              <button type="button" class="btn-mini" id="dDaysInv">反选</button>
              <button type="button" class="btn-mini" id="dDaysClear">清空</button>
            </div>
            <div class="ms-options" id="dDays"></div>
          </div>
        </div>
      </label>
      <label>关键词<input id="dKw" placeholder="手机号/协议ID/昵称"></label>
      <button id="dReset" class="btn-ghost" style="margin-top:16px">重置</button>
      <button id="clearTodayBtn" class="btn-ghost" style="margin-top:16px;color:#c0392b;border-color:#e7b5b5">清空今日排班</button>
      <button id="clearAssignmentsBtn" class="btn-ghost" style="margin-top:16px;color:#c0392b;border-color:#e7b5b5">清空全部排班数据</button>
      <div style="display:flex;gap:6px;margin-top:16px;align-items:center">
        <select id="cancelSolver" class="inp" style="max-width:130px"></select>
        <button id="cancelSolverBtn" class="btn-ghost" style="color:#c0392b;border-color:#e7b5b5" title="作废该接待人名下所有待回访任务，相关协议释放回待分配池，下次追加排班可重新分配">作废该人分配</button>
      </div>
      <button id="aiClassifyBtn" class="btn" style="margin-top:16px;background:#1a7f37">AI 自动分类</button>
      <span id="aiClassifyTip" class="dispatch-tip"></span>
    </div>
    <div id="catStat" class="cat-stat"></div>
    <table id="allTbl"><thead><tr>
      <th>协议ID</th><th>消费者ID</th><th>手机号</th><th>当前手机号</th><th>接待人</th><th>计划回访</th><th>状态</th><th>回访结果</th><th>接待时间</th><th>来源</th><th>城市</th><th>区域</th><th>档位</th><th>回访分类</th><th>标签摘要</th><th>操作</th>
    </tr></thead><tbody id="allBody"></tbody></table>
    <div class="pager" id="allPager"></div>
  </div>
</div>

<!-- ============ 历史排班 Tab ============ -->
<div class="tablewrap" id="dispatch_history" style="display:none">
  <div class="dispatch-card">
    <h3>历史排班查询</h3>
    <div class="history-bar">
      <label>选择日期<input id="historyDate" type="date"></label>
      <span id="historyMeta" style="font-size:12px;color:#888"></span>
      <button id="clearHistoryBtn" class="btn-ghost" style="margin-left:auto">清空历史排班</button>
    </div>
    <div id="historyStaff" class="history-badges"></div>
    <div id="histCatStat" class="cat-stat"></div>
    <table id="historyTbl"><thead><tr>
      <th>序号</th><th>协议ID</th><th>消费者ID</th><th>手机号</th><th>接待人</th><th>计划回访</th>
    </tr></thead><tbody id="historyBody"></tbody></table>
    <div class="pager" id="historyPager"></div>
  </div>
</div>

<!-- ============ 无需回访 Tab ============ -->
<div class="tablewrap" id="no_followup" style="display:none">
  <div class="dispatch-card">
    <h3>无需回访名单（替换/剔除用户归档）</h3>
    <div class="filters-inline" style="margin-bottom:10px">
      <label>原因<select id="nfReasonFilter"><option value="">全部</option><option value="系统数据错误·4814电池">系统数据错误·4814电池</option><option value="空号联系不上">空号联系不上</option><option value="非低频用户">非低频用户</option><option value="欠租用户">欠租用户</option><option value="其他">其他</option></select></label>
      <label>关键词<input id="nfKw" placeholder="手机号/协议ID"></label>
      <button id="nfReset" class="btn-ghost">重置</button>
    </div>
    <div id="nfStat" class="meta-line" style="margin-bottom:10px"></div>
    <table id="nfTbl"><thead><tr>
      <th>协议ID</th><th>手机号</th><th>协议类型</th><th>协议状态</th><th>押金划扣状态</th><th>原因</th><th>备注</th><th>标记人</th><th>标记时间</th><th>操作</th>
    </tr></thead><tbody id="nfBody"></tbody></table>
    <div class="pager" id="nfPager"></div>
  </div>
</div>

<!-- 人员管理弹窗 -->
<div class="tag-modal" id="staffModal">
  <div class="tag-box" style="width:min(420px,94vw)">
    <h3>人员管理</h3>
    <div style="display:flex;gap:8px;margin-bottom:12px">
      <input id="newStaffName" type="text" placeholder="输入姓名" style="flex:1;padding:7px 9px;border:1px solid var(--line);border-radius:8px">
      <button id="addStaffBtn" class="btn">添加</button>
    </div>
    <div id="staffListWrap" style="max-height:300px;overflow:auto;border:1px solid var(--line);border-radius:8px;padding:8px">
      <table style="width:100%;font-size:13px"><tbody id="staffListBody"></tbody></table>
    </div>
    <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:14px">
      <button id="staffModalSave" class="btn">保存名单</button>
      <button id="staffModalCancel" class="btn-ghost">关闭</button>
    </div>
    <div id="staffModalMsg" class="dispatch-tip"></div>
  </div>
</div>

<!-- 回访链接弹窗 -->
<div class="tag-modal" id="linkModal">
  <div class="tag-box" style="width:min(580px,94vw)">
    <h3>回访链接（同网络可访问）</h3>
    <p style="font-size:13px;color:#666;margin:6px 0 12px">将下方链接发给同局域网内的同事或手机，打开即可查看并操作回访看板（已直接定位到「回访排班」）。需本机服务窗口保持运行、且防火墙放行该端口。</p>
    <div style="display:flex;gap:8px;margin-bottom:10px">
      <input id="linkInput" type="text" readonly style="flex:1;padding:8px 10px;border:1px solid var(--line);border-radius:8px;font-size:13px">
      <button id="copyLinkBtn" class="btn">复制</button>
      <button id="testLinkBtn" class="btn-ghost" title="在新窗口打开预览，验证链接在手机/电脑端是否可访问">🧪 测试链接</button>
    </div>
    <div style="font-size:12px;color:#888">本机内网地址：<span id="lanIpHint">—</span></div>
    <div style="margin:12px 0 4px;font-size:13px;color:#333">对外可见模块（勾选后对方只能看到这些，无法切换到未勾选项）：</div>
    <div id="linkMods" class="filter-mini" style="flex-wrap:wrap;gap:8px;margin-bottom:4px">
      <label class="staff-card" style="cursor:pointer"><input type="checkbox" value="dispatch" checked><span class="name">回访排班</span></label>
      <label class="staff-card" style="cursor:pointer"><input type="checkbox" value="dispatch_schedule" checked><span class="name">回访调度</span></label>
      <label class="staff-card" style="cursor:pointer"><input type="checkbox" value="dispatch_overview"><span class="name">排班总览</span></label>
      <label class="staff-card" style="cursor:pointer"><input type="checkbox" value="dispatch_history"><span class="name">历史排班</span></label>
      <label class="staff-card" style="cursor:pointer"><input type="checkbox" value="all"><span class="name">全部活跃协议</span></label>
      <label class="staff-card" style="cursor:pointer"><input type="checkbox" value="owe"><span class="name">欠租催收</span></label>
      <label class="staff-card" style="cursor:pointer"><input type="checkbox" value="lf"><span class="name">低频用户</span></label>
      <label class="staff-card" style="cursor:pointer"><input type="checkbox" value="reception"><span class="name">回访看板</span></label>
    </div>
    <div style="font-size:12px;color:#888;margin-bottom:6px">默认仅开放「回访排班」与「回访调度」，可按需加勾「排班总览」「历史排班」等。</div>
    <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:8px">
      <button id="linkModalClose" class="btn-ghost">关闭</button>
    </div>
  </div>
</div>

<!-- 人员权限弹窗（v10.28.55：账号密码登录 + 角色 + 手机白名单 + 模块） -->
<div class="tag-modal" id="permModal">
  <div class="tag-box" style="width:min(680px,94vw)">
    <h3>人员权限设置（账号体系）</h3>
    <p style="font-size:13px;color:#666;margin:6px 0 12px">
      为每位同事创建<b>登录账号</b>并配置可见模块 / 数据范围 / 手机白名单 / 是否可同步。
      同事用「账号+密码」登录（旧 <code>?user=boss</code> 明文链接已停用）。
      <b>数据范围</b>填城市关键词（逗号分隔，如 <code>上海,杭州</code>）；<b>手机白名单</b>填手机号前缀（逗号分隔，如 <code>138,1390010</code>），二者留空/填「全部」表示不限。
    </p>
    <div style="display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap">
      <input id="permUsername" type="text" placeholder="登录账号（如 wang）" style="flex:1;min-width:130px;padding:8px 10px;border:1px solid var(--line);border-radius:8px;font-size:13px">
      <input id="permName" type="text" placeholder="显示名（如 客服小王）" style="flex:1;min-width:130px;padding:8px 10px;border:1px solid var(--line);border-radius:8px;font-size:13px">
      <input id="permPw" type="text" placeholder="登录密码" style="flex:1;min-width:120px;padding:8px 10px;border:1px solid var(--line);border-radius:8px;font-size:13px">
      <button id="permAddBtn" class="btn">添加账号</button>
    </div>
    <div id="permList" style="max-height:320px;overflow:auto;border:1px solid var(--line);border-radius:8px;padding:8px"></div>
    <div id="permMsg" class="dispatch-tip"></div>
    <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:10px">
      <button id="permSaveBtn" class="btn">保存配置</button>
      <button id="permModalClose" class="btn-ghost">关闭</button>
    </div>
  </div>
</div>

<!-- 贴标签弹窗 -->
<div class="tag-modal" id="tagModal">
  <div class="tag-box">
    <h3>回访标签 - <span id="tagUser"></span></h3>
    <div class="tag-tabs">
      <button data-l="L1" class="active">一级</button>
      <button data-l="L2">二级</button>
      <button data-l="L3">三级</button>
      <button data-l="OUT">回访结果</button>
    </div>
    <div id="tagOptions" class="tag-options"></div>
    <div class="tag-actions">
      接待人<select id="tagSolver"></select>
      计划回访<input type="date" id="tagDate">
      状态<select id="tagStatus"><option>待回访</option><option>已回访</option><option>已关闭</option></select>
      <label>回访分类<select id="tagCat"></select></label>
      <button id="tagSave" class="btn">保存</button>
      <button id="tagCancel" class="btn-ghost">取消</button>
    </div>
    <div id="tagMsg" class="dispatch-tip"></div>
  </div>
</div>

<div class="tag-modal" id="replaceModal">
  <div class="tag-box" style="width:min(580px,94vw)">
    <h3>替换回访用户 - <span id="repCurrent"></span></h3>
    <div class="rep-search"><input id="repKw" type="text" placeholder="搜索 手机号 / 协议ID，留空显示全部候选"></div>
    <div class="rep-tip" id="repTip">加载中…</div>
    <div id="repList" class="rep-list"></div>
    <div class="tag-actions">
      <button id="repCancel" class="btn-ghost">取消</button>
    </div>
  </div>
</div>

<!-- 标记无需回访弹窗 -->
<div class="tag-modal" id="noFollowupModal">
  <div class="tag-box" style="width:min(480px,94vw)">
    <h3>标记为无需回访 - <span id="nfCurrent"></span></h3>
    <div style="font-size:13px;color:#666;margin:6px 0 12px">选择原因后确认，原任务将关闭，该用户不再进入后续自动分配。</div>
    <label style="display:flex;flex-direction:column;gap:6px;font-size:13px;color:#555">原因
      <select id="nfReason" style="padding:7px 9px;border:1px solid var(--line);border-radius:8px;font-size:13px">
        <option value="系统数据错误·4814电池">系统数据错误·4814电池</option>
        <option value="空号联系不上">空号联系不上</option>
        <option value="非低频用户">非低频用户</option>
        <option value="欠租用户">欠租用户</option>
        <option value="其他">其他</option>
      </select>
    </label>
    <label style="display:flex;flex-direction:column;gap:6px;font-size:13px;color:#555;margin-top:10px">备注
      <textarea id="nfNote" rows="3" style="padding:7px 9px;border:1px solid var(--line);border-radius:8px;font-size:13px;resize:vertical"></textarea>
    </label>
    <div class="tag-actions" style="margin-top:16px">
      <button id="nfConfirm" class="btn" style="background:#c0392b">确认标记</button>
      <button id="nfCancel" class="btn-ghost">取消</button>
    </div>
    <div id="nfMsg" class="dispatch-tip"></div>
  </div>
</div>

<!-- v10.20：追加排班 Modal（只为本次勾选的人员+数量分配，原名单完全保留） -->
<div class="tag-modal" id="appendModal">
  <div class="tag-box" style="width:min(560px,94vw)">
    <h3>追加排班 — 选择要新增的接待人</h3>
    <div style="font-size:13px;color:#666;margin:6px 0 12px">
      勾选<b>本次新增</b>的人员，为每人填写接待数量。仅对这几个人按各自配额生成新任务；<b>原名单完全不动</b>，避免单人回访数量翻倍。
    </div>
    <div style="font-size:13px;color:#555;margin:4px 0 8px">已配置的接待人员：</div>
    <div id="appendStaffList" class="staff-row" style="display:flex;flex-wrap:wrap;gap:8px;max-height:340px;overflow:auto;padding:6px;border:1px dashed var(--line);border-radius:8px"></div>
    <div class="tag-actions" style="margin-top:16px">
      <button id="appendConfirm" class="btn" style="background:#1a7f37">生成追加名单</button>
      <button id="appendModalClose" class="btn-ghost">取消</button>
    </div>
    <div id="appendModalMsg" class="dispatch-tip"></div>
  </div>
</div>

<div class="foot">说明：低频判定按"归还电池"次数（cb_exchange_order 中 back_battery_time&gt;0，仅算归还）→ L1 15~30天&lt;3 / L2 30~45天&lt;4 / L3 45~60天&lt;5 / L4 &gt;60天&lt;9（v10.11 默认放宽版；阈值从 db_conf.json→lowfreq_thresholds 读取，可改；≤15 天新用户不参与判定）。手机号保留原始 11 位，用于电话回访。跟进记录仅保存在本浏览器(localStorage)，换设备/清缓存会丢失，重要跟进请同步到 Excel 工作簿。</div>

<script>
// v10.28.55：全局错误兜底——渲染异常时显示红条而非白屏卡死，便于定位（而不是一直"加载中"）
window.addEventListener('error', function(e){
  try{
    var box=document.getElementById('fatalErr');
    if(!box){ box=document.createElement('div'); box.id='fatalErr';
      box.style.cssText='position:fixed;left:0;right:0;top:0;z-index:99999;background:#c0392b;color:#fff;font-size:13px;padding:10px 14px;white-space:pre-wrap;max-height:60vh;overflow:auto';
      (document.body||document.documentElement).appendChild(box); }
    box.textContent='⚠️ 页面渲染出错（可尝试刷新或重新同步一次）：'+((e&&e.message)?e.message:e);
  }catch(_){}
});
// v10.28.57 性能核心：明细 rows 采用「列式 + 字典编码 + base64 位打包」
//   行式 JSON：123k 行 × 78 字段，每行重复 78 个 key ≈ 700B 纯 key 开销 → 25MB+
//   列式编码：常量列存单值、低基数列存字典+位打包索引、高基数列原样 → 约 2MB
const _COLS_RAW = __COLS__;
function decodeCols(C){
  var n=(C&&C.n)||0, cols=(C&&C.c)||{}, rows=new Array(n), i, q, jj;
  for(i=0;i<n;i++) rows[i]={};
  var M=null, B64='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
  for(var k in cols){
    var c=cols[k];
    if(c.k!==undefined){
      var kv=c.k;
      if(c.j){ var kj=JSON.stringify(kv); for(i=0;i<n;i++) rows[i][k]=JSON.parse(kj); }
      else { for(i=0;i<n;i++) rows[i][k]=kv; }
      continue;
    }
    if(c.s!==undefined){
      if(!M){ M={}; for(i=0;i<64;i++) M[B64.charAt(i)]=i; }
      var s=c.s, w=c.w||1, d=c.d;
      if(c.j){ for(jj=0;jj<d.length;jj++) d[jj]=JSON.parse(d[jj]); }
      if(w===1){ for(i=0;i<n;i++){ var t=d[M[s.charAt(i)]]; rows[i][k]=(t===undefined?null:t); } }
      else { for(i=0;i<n;i++){ var b=i*w, v=0; for(q=0;q<w;q++) v=(v<<6)|(M[s.charAt(b+q)]||0); var t2=d[v]; rows[i][k]=(t2===undefined?null:t2); } }
      continue;
    }
    if(c.i!==undefined){
      var ix=c.i, dd=c.d;
      if(c.j){ for(jj=0;jj<dd.length;jj++) dd[jj]=JSON.parse(dd[jj]); }
      for(i=0;i<n;i++){ var t3=dd[ix[i]]; rows[i][k]=(t3===undefined?null:t3); }
      continue;
    }
    if(c.v!==undefined){ var vv=c.v; for(i=0;i<n;i++) rows[i][k]=vv[i]; continue; }
  }
  return rows;
}
const DATA = __DATA__;
const DATA_SUMMARY = __DATA_SUMMARY__;
try{
  var _decT0=(window.performance&&performance.now)?performance.now():Date.now();
  DATA.rows = decodeCols(_COLS_RAW);
  var _decT1=(window.performance&&performance.now)?performance.now():Date.now();
  window.__DECODE_MS__ = Math.round(_decT1-_decT0);
  if(window.console) console.log('[v10.28.57] 列式解码 '+DATA.rows.length+' 行 / '+window.__DECODE_MS__+'ms');
}catch(e){
  if(window.console) console.error('[v10.28.57] 列式解码失败，回退空明细', e);
  DATA.rows = [];
}
const rows = DATA.rows;
const LAZY_ENABLED = false;   // v10.28.57：明细已全量在本地，无需懒加载
window.__LAZY_ENABLED__ = LAZY_ENABLED;
// 优选产品：默认排序时排在最前面（深圳4824/杭州4824/阳朔4824/深圳4814/杭州4814/阳朔4814）
const PREF_PRODUCTS = ['深圳4824','杭州4824','阳朔4824','深圳4814','杭州4814','阳朔4814'];
function prodPriority(p){ if(!p) return 99; for(let i=0;i<PREF_PRODUCTS.length;i++){ if(p.indexOf(PREF_PRODUCTS[i])>=0) return i; } return 99; }
rows.forEach(r=>{ r.pp = prodPriority(r.pd); });
const aidToPhone = {};
(rows || []).forEach(r => { if(r.id != null) aidToPhone[r.id] = r.ph || ''; });
const PS = 100;
// v10.28.55：接待明细「用户状态」颜色映射 + 前端兜底计算（DB 同步时已写入 r.user_status；空字段时再算）
const USER_STATUS_COLOR = {'已换电':'#16a34a','已退订':'#c0392b','未换电':'#d97706','—':'#888'};
function _userStatusOf(r){
  if(!r) return '—';
  if(r.user_status) return r.user_status;
  const bct = String(r.battery_circ_time||'').trim();
  const rt  = String(r.time||'').trim();
  const raw = String(r._agreement_status_raw || r.agreement_status || '').trim();
  const terminatedRaw = new Set(['unsubscribing','terminated','closed','退订中','已终止']);
  if(terminatedRaw.has(raw)) return '已退订';
  if(bct && rt){
    return bct >= rt ? '已换电' : '未换电';
  }
  if(bct) return '已换电';
  return '未换电';
}
let state = {view:'all', province:'', city:'', area:'', street:'', product:'', status:'', agreementType:'', islf:'', level:'', bco:'', bcv:'', circOpType:'', smsr:'', days:[], agr:'', kw:'', tags:[], sortKey:'id', sortDir:1, page:1, phone:'', analysisPage:1};

document.getElementById('now').textContent = DATA.now;

// 级联选项构建
function opts(arr,empty){ return `<option value="">${empty}</option>` + [...new Set(arr)].filter(Boolean).sort().map(v=>`<option>${esc(v)}</option>`).join(''); }
function fillSelect(id, html){ document.getElementById(id).innerHTML = html; }
const provinces = [...new Set(rows.map(r=>r.pr))].filter(Boolean).sort();
fillSelect('fProvince', opts(provinces,'全部省份'));

function cascade(){
  const base = rows.filter(r=>{
    return (!state.province || r.pr===state.province) &&
           (!state.city || r.ci===state.city) &&
           (!state.area || r.ar===state.area);
  });
  const cities = [...new Set(base.map(r=>r.ci))].filter(Boolean).sort();
  fillSelect('fCity', opts(cities,'全部城市'));
  if(state.city && !cities.includes(state.city)){ state.city=''; state.area=''; state.street=''; }
  const base2 = base.filter(r=>!state.city || r.ci===state.city);
  const areas = [...new Set(base2.map(r=>r.ar))].filter(Boolean).sort();
  fillSelect('fArea', opts(areas,'全部区域'));
  if(state.area && !areas.includes(state.area)){ state.area=''; state.street=''; }
  const base3 = base2.filter(r=>!state.area || r.ar===state.area);
  const streets = [...new Set(base3.map(r=>r.st))].filter(Boolean).sort();
  fillSelect('fStreet', opts(streets,'全部街道'));
  if(state.street && !streets.includes(state.street)){ state.street=''; }
  // restore selections
  document.getElementById('fProvince').value=state.province;
  document.getElementById('fCity').value=state.city;
  document.getElementById('fArea').value=state.area;
  document.getElementById('fStreet').value=state.street;
}

const prods = [...new Set(rows.map(r=>r.pd))].filter(Boolean).sort();
fillSelect('fProduct', opts(prods,'全部产品'));
// v10.28.55：低频用户数据分析 7 维度筛选（独立 a 前缀控件，避免与主表冲突）
fillSelect('aProduct', opts(prods,'全部电池产品'));
const bcos = [...new Set(rows.map(r=>r.bco))].filter(Boolean).sort();
fillSelect('fBco', `<option value="">全部</option><option value="_empty">未记录</option>`+bcos.map(v=>`<option>${esc(v)}</option>`).join(''));
fillSelect('fBcv', `<option value="">全部</option><option value="1">在流通</option><option value="0">暂无电池</option>`);
const smsrs=[...new Set(rows.map(r=>r.smsr))].filter(Boolean).sort();
fillSelect('fSmsr', `<option value="">全部</option>`+smsrs.map(v=>`<option>${esc(v)}</option>`).join('')+`<option value="_none">未记录</option>`);

// 初始化使用天数多选组件（支持全选/反选/清空）
const DAY_RANGES = [
  {v:'0-30',t:'0 ~ 30天'},
  {v:'31-60',t:'31 ~ 60天'},
  {v:'61-90',t:'61 ~ 90天'},
  {v:'91-180',t:'91 ~ 180天'},
  {v:'181-365',t:'181 ~ 365天'},
  {v:'365+',t:'365天以上'}
];
(function initDaysFilter(){
  const box=document.getElementById('fDays');
  const trig=document.getElementById('fDaysTrigger');
  const panel=document.getElementById('fDaysPanel');
  const wrap=document.getElementById('fDaysWrap');
  box.innerHTML = DAY_RANGES.map(r=>`<label class="tg" data-range="${r.v}"><input type="checkbox" value="${r.v}"><span>${r.t}</span></label>`).join('');
  const getChecked=()=>[...box.querySelectorAll('input:checked')].map(i=>i.value);
  const updateTrigger=()=>{
    const sels=getChecked();
    trig.textContent = sels.length===0 ? '全部' : `已选 ${sels.length} 项`;
  };
  const sync=()=>{ state.days=getChecked(); updateTrigger(); };
  const apply=()=>{ sync(); state.page=1; render(); };
  box.querySelectorAll('input').forEach(cb=>{ cb.onchange=apply; });
  document.getElementById('fDaysAll').onclick=()=>{ box.querySelectorAll('input').forEach(cb=>cb.checked=true); apply(); };
  document.getElementById('fDaysInv').onclick=()=>{ box.querySelectorAll('input').forEach(cb=>cb.checked=!cb.checked); apply(); };
  document.getElementById('fDaysClear').onclick=()=>{ box.querySelectorAll('input').forEach(cb=>cb.checked=false); apply(); };
  trig.onclick=(e)=>{ e.stopPropagation(); panel.style.display = panel.style.display==='none'?'block':'none'; };
  document.addEventListener('click',(e)=>{ if(wrap && !wrap.contains(e.target)){ panel.style.display='none'; } });
  sync();
})();

// 初始化标签筛选(主表) — 多标签 OR 语义
const ALL_TAGS=[...new Set(rows.flatMap(r=>r.tags||[]))].sort();
(function(){
  const tf=document.getElementById('tagFilter');
  ALL_TAGS.forEach(tg=>{
    const l=document.createElement('label'); l.className='tg';
    l.innerHTML=`<input type="checkbox" value="${esc(tg)}"><span>${esc(tg)}</span>`;
    l.querySelector('input').onchange=()=>{ state.tags=[...tf.querySelectorAll('input:checked')].map(i=>i.value); l.classList.toggle('active', l.querySelector('input').checked); state.page=1; if(state.view==='reception'){detailState.page=1;renderReception();} else render(); };
    tf.appendChild(l);
  });
})();

const fuKey=(id,f)=>`lfowe_${id}_${f}`;
const fuGet=(id,f)=>localStorage.getItem(fuKey(id,f))||'';
const fuSet=(id,f,v)=>{ if(v) localStorage.setItem(fuKey(id,f),v); else localStorage.removeItem(fuKey(id,f)); };

function esc(s){return (s==null?'':String(s)).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}

// v10.28.55：「导出全部数据 CSV」开关。
//   true 时 pass() 只保留 Tab 本身的口径（全部活跃协议/欠租催收/低频用户），
//   跳过后面所有用户手动设置的筛选条件（省市区街道/产品/状态/类型/档位/协议ID/关键词…）。
//   导出完成后立即复位为 false，不影响页面正常渲染。
let __EXPORT_ALL__ = false;
function pass(r){
  if(state.view==='owe' && !r.owe) return false;
  if(state.view==='lf' && !r.lf) return false;
  if(__EXPORT_ALL__) return true;   // ← 导出全部：Tab 口径已满足，跳过后续筛选
  if(state.province && r.pr!==state.province) return false;
  if(state.city && r.ci!==state.city) return false;
  if(state.area && r.ar!==state.area) return false;
  if(state.street && r.st!==state.street) return false;
  if(state.product && r.pd!==state.product) return false;
  if(state.status && r.status!==state.status) return false;
  if(state.agreementType){
    const raw = r.atr || r.at || '';
    if(state.agreementType==='single' && raw!=='single' && raw!=='个人') return false;
    if(state.agreementType==='company' && raw!=='company' && raw!=='企业') return false;
  }
  if(state.islf !== '' && String(r.lf)!==state.islf) return false;
  if(state.level && String(r.lv)!==state.level) return false;
  if(state.bco === '_empty'){ if((r.bco||'')!=='') return false; }
  else if(state.bco && r.bco!==state.bco) return false;
  // v10.21：最后流通类型筛选（柜内借出/换电-还电池/调拨-回收/柜内归还/其他/未记录）
  if(state.circOpType === '未知'){ if((r.cot||'')!=='' && r.cot!=='未知') return false; }
  else if(state.circOpType && r.cot!==state.circOpType) return false;
  if(state.bcv !== '' && String(r.bcv)!==state.bcv) return false;
  if(state.smsr === '_none'){ if((r.smsr||'')!=='') return false; }
  else if(state.smsr && r.smsr!==state.smsr) return false;
  if(state.days && state.days.length){
    const d = r.days==null?null:Number(r.days);
    if(d==null || isNaN(d)) return false;
    const ok = state.days.some(v=>{
      if(v==='0-30') return d>=0 && d<=30;
      if(v==='31-60') return d>=31 && d<=60;
      if(v==='61-90') return d>=61 && d<=90;
      if(v==='91-180') return d>=91 && d<=180;
      if(v==='181-365') return d>=181 && d<=365;
      if(v==='365+') return d>365;
      return false;
    });
    if(!ok) return false;
  }
  if(state.agr && !String(r.id).includes(state.agr.trim())) return false;
  if(state.kw){const k=state.kw.trim().toLowerCase(); if(!((r.ph||'').includes(k)||(r.nm||'').toLowerCase().includes(k))) return false;}
  if(state.tags.length && !(r.tags||[]).some(x=>state.tags.includes(x))) return false;
  return true;
}
function apply(){let f=rows.filter(pass); const k=state.sortKey,d=state.sortDir;
  f.sort((a,b)=>{
    const pa=a.pp??99, pb=b.pp??99;            // 优选产品始终排最前
    if(pa!==pb) return pa-pb;
    let x=a[k],y=b[k]; if(typeof x==='string'){x=x.toLowerCase();y=y.toLowerCase();} x=x===''?null:x;y=y===null?null:y; return (x<y?-1:x>y?1:0)*d;
  }); return f;}

function svg(p){return `<svg viewBox="0 0 24 24"><path d="${p}"/></svg>`;}
const ICON={
  doc:'M4 4h16v16H4zM7 8h10M7 12h10M7 16h6',
  warn:'M12 3l9 16H3zM12 10v4M12 17v.5',
  pulse:'M3 12h4l3-8 4 16 3-8h4',
  alert:'M12 3l9 16H3zM12 9v5M12 16h.01'
};
function card(n,t,variant,src,icon){return `<div class="kpi ${variant||'blue'}"><div class="ic">${icon||''}</div><div class="n">${n}</div><div class="t">${t}</div><div class="src">${src||''}</div></div>`;}
function renderKPIs(f){const owe=f.filter(r=>r.owe).length, lf=f.filter(r=>r.lf).length, l1=f.filter(r=>r.lv===1).length;
  document.getElementById('kpis').innerHTML=
    card(f.length,'当前协议数','blue','来源：cb_exchange_agreement 中 status∈working/owe_rent/unsubscribing 且 is_del=0，再叠加当前所有筛选',svg(ICON.doc))+
    card(owe,'欠租催收','red','来源：当前协议中 status = "owe_rent"',svg(ICON.warn))+
    card(lf,'低频用户','org','来源：当前协议中满足 15~30/30~45/45~60/>60天任一低频档位(L1~L4) 或 电池电量<25%(L5)',svg(ICON.pulse))+
    card(l1,'L1最严重','vio','来源：当前协议中 15~30天内换电 &lt; 1',svg(ICON.alert));}
function renderNote(){
  document.getElementById('statsNote').innerHTML = `
  <h4>统计口径与计算依据</h4>
  <div>数据截止：<b>${DATA.now}</b>，数据库：<code>sharing-citybike-pro</code>。所有 KPI 均为“当前筛选条件下”的统计结果。</div>
  <ul>
    <li><b>当前协议数</b>：<code>cb_exchange_agreement</code> 中 <code>status IN ('working','owe_rent','unsubscribing') AND is_del=0</code>，再叠加顶部省市区街道/产品/协议类型/协议状态/是否低频/档位/协议ID/关键词筛选。<br>本次同步后活跃协议 <b>${DATA.total}</b> 条；活跃状态分布：<b>${DATA.diagnostic?Object.entries(DATA.diagnostic.active_status_count||{}).map(([k,v])=>`${k}:${v}`).join(' / '):'—'}</b>。</li>
    <li><b>协议类型</b>：来自 <code>cb_exchange_agreement.type</code>，<code>single</code>=个人，<code>company</code>=企业。当前活跃协议中按类型分布：<b>${DATA.diagnostic?Object.entries(DATA.diagnostic.active_type_count||{}).map(([k,v])=>`${k}:${v}`).join(' / '):'—'}</b>。</li>
    <li><b>全表状态分布（含非活跃）</b>：<b>${DATA.diagnostic?Object.entries(DATA.diagnostic.all_status_count||{}).map(([k,v])=>`${k}:${v}`).join(' / '):'—'}</b>。若发现大量有效协议被排除，可联系技术支持扩展活跃协议定义。</li>
    <li><b>押金划扣状态</b>：来自 <code>cb_exchange_agreement.deposit_status</code>，<code>on</code>=押金在押（未退、未划扣），<code>off</code>=押金已释放（已退款或已划扣抵扣费用）。</li>
    <li><b>欠租催收</b>：当前协议中 <code>status = 'owe_rent'</code> 的数量。</li>
    <li><b>低频用户</b>：当前协议中，近 60/45/30/15 天内“归还电池”次数满足任一低频档位（L1~L4，取最严重档），或电池电量 &lt; 25%（L5）的协议数。</li>
    <li><b>L1最严重</b>：当前协议中，近 15 天内（生效 &gt;15 天前提下）归还次数 &lt; 1 次的协议数。</li>
    <li><b>归还次数判定</b>：<code>cb_exchange_order</code> 中 <code>back_battery_time &gt; 0</code> 即计为 1 次归还；<b>只算归还，不统计取电池</b>。因原字段 <code>back_status</code> 只覆盖到 2023 年，改用此口径确保覆盖到最新 2026 年数据。</li>
    <li><b>低频档位规则（8 月 12 号口径）</b>：生效 &gt;15 天且 ≤30 天内换电&lt;1次=L1 / &gt;30 且 ≤45 天内&lt;2次=L2 / &gt;45 且 ≤60 天内&lt;3次=L3 / &gt;60 天 60 天内&lt;4次=L4（≤15 天新用户不参与 L1~L4 判定；窗口换电次数，非全历史 total）。另 L5：生效 ≤15 天且电池电量&lt;25% 即提醒换电，或生效 &gt;15 天且 15 天内 0 次换电 且 电量&lt;25%。满足任一即低频。<b>流通异常</b>用户（电池已被柜上报/不在用户手里）自动从回访名单剔除（v10.18.4 起）。</li>
    <li><b>月均换电频次</b>：60天归还次数 ÷ 2（60天≈2个月），保留两位小数；反映近两个月平均活跃度。</li>
    <li><b>地理字段</b>：<code>cb_exchange_agreement.site_id</code> JOIN <code>cb_site</code> 取 province / city / area / street / community。</li>
  </ul>`;
}
function bars(arr,maxv,color){return arr.map(d=>`<div class="bar"><span class="bl" style="width:${maxv?d.value/maxv*100:0}%;background:${color}"></span><b title="${esc(d.label)}">${esc(d.label)}</b><i>${d.value}</i></div>`).join('');}
// v10.28.55：电量校准显示 —— 主显校准值，悬浮显示原始+陈旧天数；陈旧加红边
function _socCell(r){
  try{
    var hasCal = (r && (r.socc!==undefined && r.socc!==null && r.socc!==''));
    if(!hasCal){
      // 校准数据尚未生成（首次同步未完）—— 显示原始 BMS 值
      return esc(r && r.soc || '—');
    }
    var raw  = (r.socr!=null && r.socr!=='') ? Number(r.socr) : null;
    var cal  = Number(r.socc);
    var age  = (r.soage!=null && r.soage!=='') ? Number(r.soage) : null;
    var stale= !!r.sost;
    var tip  = '原始BMS: ' + (raw!=null?raw+'%':'未知') + ' → 自放电 ' + (age!=null?(age.toFixed?age.toFixed(1):age):'?') + '天 = ' + cal + '%';
    if(stale) tip = '⚠ BMS已陈旧 ' + (age!=null?age.toFixed(1):'?') + '天未上报，仅供参考 ｜ ' + tip;
    var color = stale ? '#c0392b' : (cal < 25 ? '#c0392b' : (cal < 50 ? '#d97706' : '#16a34a'));
    var sub   = (raw!=null) ? ('<span style="color:#888;font-size:11px">(实测 ' + raw + '%)</span>') : '';
    var ago   = (age!=null) ? ('<span style="color:#888;font-size:11px">' + (stale?'陈旧':'·'+(age.toFixed?age.toFixed(1):age)) + '天前</span>') : '';
    return '<span title="' + esc(tip) + '" style="color:' + color + ';font-weight:600;cursor:help">' + cal + '%</span> ' + sub + (age!=null ? ' ' + ago : '');
  }catch(_e){ return esc(r && r.soc || '—'); }
}
function renderCharts(f){
  const lv=[1,2,3,4,5].map(l=>({label:'L'+l,value:f.filter(r=>r.lv===l).length}));
  document.getElementById('chartLevel').innerHTML=bars(lv,Math.max(1,...lv.map(x=>x.value)),'#C0392B');
  const pc={}; f.forEach(r=>{if(r.pd)pc[r.pd]=(pc[r.pd]||0)+1;});
  const topP=Object.entries(pc).sort((a,b)=>b[1]-a[1]).slice(0,10).map(([k,v])=>({label:k,value:v}));
  document.getElementById('chartProduct').innerHTML=bars(topP,topP.length?topP[0].value:1,'#1F4E78');
  const cc={}; f.forEach(r=>{if(r.ci)cc[r.ci]=(cc[r.ci]||0)+1;});
  const topC=Object.entries(cc).sort((a,b)=>b[1]-a[1]).slice(0,10).map(([k,v])=>({label:k,value:v}));
  document.getElementById('chartCity').innerHTML=bars(topC,topC.length?topC[0].value:1,'#16a34a');
}

function renderTable(f){
  const total=f.length, pages=Math.max(1,Math.ceil(total/PS));
  if(state.page>pages)state.page=pages;
  const start=(state.page-1)*PS, pr=f.slice(start,start+PS), tb=document.getElementById('tbody');
  tb.innerHTML=pr.map(r=>{
    const mf = r.mf!=null ? Number(r.mf).toFixed(2) : (r.c60!=null ? (r.c60/2).toFixed(2) : '—');
    const statusBadge = r.status==='owe_rent'?'<span class="badge owe">欠租</span>':(r.status==='unsubscribing'?'<span class="badge unsub">退订中</span>':'生效中');
    return `<tr class="${r.lv?'lv'+r.lv:''}">
    <td>${r.id}</td><td>${esc(r.uid||'—')}</td><td class="ph">${r.ph||'—'}</td><td class="cph" style="color:#C00000;font-weight:600">${r.cph||r.ph||'—'}</td><td>${esc(r.smst||'—')}</td><td style="${r.smsr==='失败'?'color:#c0392b;font-weight:600':(r.smsr==='成功'?'color:#1e8449;font-weight:600':'')}">${esc(r.smsr||'—')}</td><td>${esc(r.smsf||'—')}</td><td>${r.days!=null?r.days:'—'}</td>
    <td>${esc(r.pd)}</td><td>${esc(r.bsn||'—')}</td><td>${esc(r.bcl||'—')}</td><td>${esc(r.bco||'—')}</td><td>${r.bcv?'在流通':'暂无电池'}</td><td>${esc(r.vol||'—')}</td><td>${esc(r.cur||'—')}</td><td>${_socCell(r)}</td><td>${r.onl==='online'?'在线':(r.onl==='offline'?'离线':'—')}</td><td>${r.dep!=null?Number(r.dep).toFixed(2):'—'}</td><td>${ {'on':'在押','off':'已退/已划扣'}[r.dst]||r.dst||'—' }</td><td>${esc(r.pkg||'—')}</td>
    <td>${esc(r.pr)}</td><td>${esc(r.ci)}</td><td>${esc(r.ar)}</td><td>${esc(r.st)}</td><td>${esc(r.co)}</td>
    <td>${esc(r.at||'—')}</td>
    <td>${statusBadge}</td>
    <td>${r.ac||'—'}</td><td>${r.re||'—'}</td><td>${r.c15}</td><td>${r.c30}</td><td>${r.c45}</td><td>${r.c60}</td>
    <td>${mf}</td>
    <td>${r.lf?'<span class="badge lf">低频</span>':'—'}</td><td>${esc(r.ln)}</td><td>${esc(r.rt||'—')}</td><td>${esc(fmtSolver(r.rs)||'—')}</td><td>${esc(r.rty||'—')}</td><td>${esc((r.rd||'').slice(0,30))}</td>
    <td><input class="fu" data-id="${r.id}" data-f="fu1" value="${esc(fuGet(r.id,'fu1'))}"></td>
    <td><input class="fu" data-id="${r.id}" data-f="fu2" value="${esc(fuGet(r.id,'fu2'))}"></td>
    <td><input class="fu" data-id="${r.id}" data-f="fu3" value="${esc(fuGet(r.id,'fu3'))}"></td><td class="tagcol">${(r.tags||[]).map(t=>`<span class="tg-chip">${esc(t)}</span>`).join('')||'—'}</td><td>${esc(fmtPcity(r))}</td><td>${r.dnr!=null&&r.dnr!==''?r.dnr:'—'}</td><td>${r.swf!=null?r.swf:'—'}</td><td>${r.scy!=null&&r.scy!==''?r.scy:'—'}</td><td>${r.dns!=null&&r.dns!==''?r.dns:'—'}</td><td>${plocBadge(r.ploc)}</td><td class="lst" title="${esc(r.lla||r.cloc||r.bloc||'')}">${esc(r.lla||r.cloc||r.bloc||'—')}</td><td>${esc(r.cq||'—')}</td></tr>`}).join('');
  document.getElementById('tblmeta').textContent=`共 ${total} 条 ｜ 第 ${state.page}/${pages} 页 ｜ 每页 ${PS}`;
  document.getElementById('pager').innerHTML=
    `<button id="pFirst" ${state.page<=1?'disabled':''}>« 首页</button>
     <button id="pPrev" ${state.page<=1?'disabled':''}>‹ 上一页</button>
     <span>第 ${state.page} / ${pages} 页</span>
     <button id="pNext" ${state.page>=pages?'disabled':''}>下一页 ›</button>
     <button id="pLast" ${state.page>=pages?'disabled':''}>末页 »</button>`;
  tb.querySelectorAll('input.fu').forEach(inp=>inp.addEventListener('change',()=>fuSet(inp.dataset.id,inp.dataset.f,inp.value)));
  const g=id=>document.getElementById(id);
  if(g('pFirst'))g('pFirst').onclick=()=>{state.page=1;render();};
  if(g('pPrev'))g('pPrev').onclick=()=>{state.page--;render();};
  if(g('pNext'))g('pNext').onclick=()=>{state.page++;render();};
  if(g('pLast'))g('pLast').onclick=()=>{state.page=pages;render();};
}
function render(){
  cascade();
  const view = state.view;
  const isDsp = (view==='dispatch'||view==='dispatch_schedule'||view==='dispatch_overview'||view==='dispatch_history');
  const showRec = view==='reception';
  const showDsp = view==='dispatch';
  const showSchedule = view==='dispatch_schedule';
  const showOverview = view==='dispatch_overview';
  const showHistory = view==='dispatch_history';
  const showNoFollowup = view==='no_followup';
  const showAnalysis = view==='analysis';
  // v10.28.55：回访效果 Tab
  const showEffect = view==='effect';
  document.getElementById('reception').style.display = showRec?'block':'none';
  document.getElementById('dispatch').style.display = (showDsp||showSchedule)?'block':'none';
  document.getElementById('dispatchTodayWrap').style.display = showDsp?'grid':'none';
  document.getElementById('dispatchScheduleWrap').style.display = showSchedule?'grid':'none';
  document.getElementById('dispatch_overview').style.display = showOverview?'block':'none';
  document.getElementById('dispatch_history').style.display = showHistory?'block':'none';
  document.getElementById('no_followup').style.display = showNoFollowup?'block':'none';
  document.getElementById('analysis').style.display = showAnalysis?'block':'none';
  document.getElementById('effect').style.display = showEffect?'block':'none';
  const hideMain = (showRec||isDsp||showNoFollowup||showAnalysis||showEffect);
  document.getElementById('tblWrap').style.display = hideMain?'none':'block';
  document.querySelector('.charts').style.display = hideMain?'none':'';
  document.getElementById('kpis').style.display = hideMain?'none':'';
  document.getElementById('statsPanel').style.display = (showRec||showNoFollowup||showAnalysis||showEffect)?'none':'block';
  document.querySelector('.filters').style.display = hideMain?'none':'block';
  if(showRec){ renderReception(); return; }
  if(showDsp||showSchedule){ loadDispatch(); return; }
  if(showOverview){ renderDispatchOverview(); return; }
  if(showHistory){ loadHistoryDates(); return; }
  if(showNoFollowup){ loadNoFollowup(); return; }
  if(showAnalysis){ renderAnalysis(); return; }
  // v10.28.55：回访效果 Tab 渲染
  if(showEffect){ if(typeof window.renderEffect==='function') window.renderEffect(); return; }
  const f=apply(); renderKPIs(f); renderNote(); renderCharts(f); renderTable(f);
}

// ===== 低频用户数据分析（独立菜单模块 v10.28.55）=====
// 7 个筛选维度：协议ID / 电池产品 / 协议状态 / 协议类型 / 是否低频 / 低频档位 / 消费者手机号
function applyAnalysis(){
  return DATA.rows.filter(r=>{
    if(state.product && r.pd!==state.product) return false;
    if(state.status && r.status!==state.status) return false;
    if(state.agreementType && r.at!==state.agreementType) return false;
    if(state.islf==='1' && !r.lf) return false;
    if(state.islf==='0' && r.lf) return false;
    if(state.level && String(r.lv)!==String(state.level)) return false;
    if(state.agreement && !String(r.id).includes(state.agreement)) return false;
    if(state.phone){
      const p=state.phone, ph=String(r.ph||''), cph=String(r.cph||'');
      if(ph.indexOf(p)<0 && cph.indexOf(p)<0) return false;
    }
    return true;
  });
}
function renderAnalysis(){
  const f=applyAnalysis();
  const total=f.length, pages=Math.max(1,Math.ceil(total/PS));
  if(state.analysisPage>pages) state.analysisPage=pages;
  if(state.analysisPage<1) state.analysisPage=1;
  const start=(state.analysisPage-1)*PS, pr=f.slice(start,start+PS), tb=document.getElementById('analysisBody');
  tb.innerHTML=pr.map(r=>{
    const statusLabel = r.status==='owe_rent'?'欠租':(r.status==='unsubscribing'?'退订中':'生效中');
    const dstLabel = {'on':'在押','off':'已退/已划扣'}[r.dst]||r.dst||'';
    const onl = r.onl==='online'?'在线':(r.onl==='offline'?'离线':'—');
    const bcv = r.bcv?'在流通':'暂无电池';
    const ploc = r.ploc? (r.ploc==='本地'?'本地':(r.ploc==='外地'?'外地':r.ploc)) : '—';
    const mf = r.mf!=null ? Number(r.mf).toFixed(2) : '—';
    const dep = r.dep!=null ? Number(r.dep).toFixed(2) : '—';
    const lfBadge = r.lf?'<span class="badge lf">低频</span>':'—';
    return `<tr>
      <td>${r.id}</td>
      <td>${esc(r.uid||'—')}</td>
      <td class="ph">${r.ph||'—'}</td>
      <td class="cph" style="color:#C0392B;font-weight:600">${r.cph||r.ph||'—'}</td>
      <td>${esc(r.pkg||'—')}</td>
      <td>${esc(r.bsn||'—')}</td>
      <td>${esc(r.bcl||'—')}</td>
      <td>${esc(fmtPcity(r))}</td>
      <td>${r.dnr!=null&&r.dnr!==''?r.dnr:'—'}</td>
      <td>${r.swf!=null?r.swf:'—'}</td>
      <td>${r.scy!=null&&r.scy!==''?r.scy:'—'}</td>
      <td>${esc(r.at||'—')}</td>
      <td>${statusLabel}</td>
      <td>${r.ac||'—'}</td>
      <td>${r.re||'—'}</td>
      <td>${ploc}</td>
      <td class="lst" title="${esc(r.lla||r.cloc||r.bloc||'')}">${esc(r.lla||r.cloc||r.bloc||'—')}</td>
      <td>${esc(r.cq||'—')}</td>
      <td>${esc(r.bco||'—')}</td>
      <td>${bcv}</td>
      <td>${r.days!=null?r.days:'—'}</td>
      <td>${esc(r.pd)}</td>
      <td>${esc(r.vol||'—')}</td>
      <td>${esc(r.cur||'—')}</td>
      <td>${_socCell(r)}</td>
      <td>${onl}</td>
      <td>${dep}</td>
      <td>${dstLabel}</td>
      <td>${esc(r.pr)}</td>
      <td>${esc(r.ci)}</td>
      <td>${esc(r.ar)}</td>
      <td>${esc(r.st)}</td>
      <td>${esc(r.co)}</td>
      <td>${r.c15}</td>
      <td>${r.c30}</td>
      <td>${r.c45}</td>
      <td>${r.c60}</td>
      <td>${mf}</td>
      <td>${lfBadge}</td>
      <td>${esc(r.ln)}</td>
      <td>${esc(r.rt||'—')}</td>
      <td>${esc(fmtSolver(r.rs)||'—')}</td>
      <td>${esc(r.rty||'—')}</td>
      <td>${esc((r.rd||'').slice(0,30))}</td>
    </tr>`;
  }).join('');
  document.getElementById('analysisMeta').textContent=`共 ${total} 条 ｜ 第 ${state.analysisPage}/${pages} 页 ｜ 每页 ${PS}`;
  document.getElementById('analysisPager').innerHTML=
    `<button id="aFirst" ${state.analysisPage<=1?'disabled':''}>« 首页</button>
     <button id="aPrev" ${state.analysisPage<=1?'disabled':''}>‹ 上一页</button>
     <span>第 ${state.analysisPage} / ${pages} 页</span>
     <button id="aNext" ${state.analysisPage>=pages?'disabled':''}>下一页 ›</button>
     <button id="aLast" ${state.analysisPage>=pages?'disabled':''}>末页 »</button>`;
  const g=id=>document.getElementById(id);
  if(g('aFirst'))g('aFirst').onclick=()=>{state.analysisPage=1;renderAnalysis();};
  if(g('aPrev'))g('aPrev').onclick=()=>{state.analysisPage--;renderAnalysis();};
  if(g('aNext'))g('aNext').onclick=()=>{state.analysisPage++;renderAnalysis();};
  if(g('aLast'))g('aLast').onclick=()=>{state.analysisPage=pages;renderAnalysis();};
}
// v10.28.55：all=true 忽略 7 个筛选维度导出全量 43 列；all=false 仅导出筛选结果
// v10.28.55：抽出 buildAnalysisRows 复用给 CSV / Excel 两种导出；NUMERIC_HEADERS 标记应转数值的列
const ANALYSIS_HEAD = ['协议ID','用户ID','手机号','当前手机号','租赁套餐','电池SN','电池最后流通时间','手机号归属地','距今未换电天数','月均换电频次','换电周期(天)','协议类型','协议状态','激活时间','租金到期时间','本地/外地','电池最后定位','流通季度','操作类型','是否流通','使用天数','电池产品','电压(V)','电流(A)','电量','电池状态','押金(元)','押金划扣状态','省份','城市','区域','街道','社区','15天','30天','45天','60天','月均','是否低频','档位','最近接待','接待人','接待类型','接待内容'];
const NUMERIC_HEADERS = new Set(['距今未换电天数','月均换电频次','换电周期(天)','电压(V)','电流(A)','电量','押金(元)','15天','30天','45天','60天','月均','使用天数']);
function analysisValueMap(r){
  const statusLabel = r.status==='owe_rent'?'欠租':(r.status==='unsubscribing'?'退订中':'生效中');
  const dstLabel = {'on':'在押','off':'已退/已划扣'}[r.dst]||r.dst||'';
  const onl = r.onl==='online'?'在线':(r.onl==='offline'?'离线':'');
  const bcv = r.bcv?'在流通':'暂无电池';
  const ploc = r.ploc? (r.ploc==='本地'?'本地':(r.ploc==='外地'?'外地':r.ploc)) : '';
  const mf = r.mf!=null ? Number(r.mf).toFixed(2) : '';
  const dep = r.dep!=null ? Number(r.dep).toFixed(2) : '';
  return [r.id,r.uid||'',r.ph,r.cph||r.ph||'',r.pkg||'',r.bsn||'',r.bcl||'',r.pcity||fmtPcity(r)||'',(r.dnr!=null&&r.dnr!==''?r.dnr:''),(r.swf!=null?r.swf:''),(r.scy!=null&&r.scy!==''?r.scy:''),r.at||'',statusLabel,r.ac||'',r.re||'',ploc,(r.lla||r.cloc||r.bloc||''),r.cq||'',r.bco||'',bcv,(r.days!=null?r.days:''),r.pd,r.vol||'',r.cur||'',r.soc||'',onl,dep,dstLabel,r.pr,r.ci,r.ar,r.st,r.co,r.c15,r.c30,r.c45,r.c60,mf,(r.lf?'低频':''),r.ln||'',r.rt||'',fmtSolver(r.rs)||'',r.rty||'',(r.rd||'').slice(0,40)];
}
function buildAnalysisRows(all){
  const f = all ? (DATA.rows||[]).slice() : applyAnalysis().slice();
  const numericCols = ANALYSIS_HEAD.map((h,i)=>NUMERIC_HEADERS.has(h)?i:-1).filter(i=>i>=0);
  return { f, head: ANALYSIS_HEAD, numericCols };
}
function exportAnalysisCsv(all){
  const {f} = buildAnalysisRows(all);
  if(!f.length){ alert(all?'没有可导出的记录。':'当前筛选下没有可导出的记录，请先放宽条件，或改用「导出全部数据 CSV（43列）」。'); return; }
  const head = ANALYSIS_HEAD;
  const lines=[head.join(',')].concat(f.map(r=>analysisValueMap(r).map(v=>{v=(v==null?'':v).toString();return /[",\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v;}).join(',')));
  const blob=new Blob(['\ufeff'+lines.join('\n')],{type:'text/csv;charset=utf-8'});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob);
  a.download=`低频用户数据分析_${all?'全部':'筛选'}_${f.length}条_${Date.now()}.csv`; a.click();
}
function exportAnalysisXlsx(all){
  const {f, head, numericCols} = buildAnalysisRows(all);
  if(!f.length){ alert(all?'没有可导出的记录。':'当前筛选下没有可导出的记录，请先放宽条件，或改用「导出全部 Excel（43列）」。'); return; }
  const rows = f.map(r=>analysisValueMap(r));
  const payload = { name:`低频用户数据分析_${all?'全部':'筛选'}_${f.length}条`, head, rows, numericCols };
  fetch('/api/export_analysis_xlsx',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
    .then(async resp=>{
      if(!resp.ok){ let m='导出失败'; try{ m=(await resp.json()).msg||m; }catch(e){} throw new Error(m); }
      const blob = await resp.blob();
      const a=document.createElement('a'); a.href=URL.createObjectURL(blob);
      a.download=`低频用户数据分析_${all?'全部':'筛选'}_${f.length}条_${Date.now()}.xlsx`; a.click();
    })
    .catch(e=>alert('导出 Excel 失败：'+e.message));
}
document.getElementById('btnAnalysisCsv').onclick=()=>{exportAnalysisCsv(false);};
document.getElementById('btnAnalysisCsvAll').onclick=()=>{
  if(!confirm('将忽略 7 个筛选维度，导出全部低频用户数据（43 列全字段）。\n确定继续吗？')) return;
  exportAnalysisCsv(true);
};
document.getElementById('btnAnalysisXlsx').onclick=()=>{exportAnalysisXlsx(false);};
document.getElementById('btnAnalysisXlsxAll').onclick=()=>{
  if(!confirm('将忽略 7 个筛选维度，导出全部低频用户数据（43 列全字段）到 Excel。\n确定继续吗？')) return;
  exportAnalysisXlsx(true);
};
let detailState = {solver:'', page:1};
let recTagSel = [];
const RD_PS = 100;
const TYPE_LABEL = {book_user_visit:'回访预约', owe_rent_user:'欠租跟进', silent_user:'沉默唤醒'};
function initRcvSolver(){
  const sl=document.getElementById('rSolver');
  const trig=document.getElementById('rSolverTrigger');
  const panel=document.getElementById('rSolverPanel');
  const search=document.getElementById('rSolverSearch');
  const wrap=document.getElementById('rSolverWrap');
  // 从 localStorage 读取用户自定义的额外接待人（不在 cb_reception_log 数据里的也可用）
  const EXT_KEY = 'lf_reception_extra_solvers';
  let extras = [];
  try{ const raw = localStorage.getItem(EXT_KEY); extras = raw ? (JSON.parse(raw) || []) : []; }catch(_){ extras = []; }
  if(!Array.isArray(extras)) extras = [];
  extras = [...new Set(extras.map(x=>String(x||'').trim()).filter(Boolean))];
  if(!sl.dataset.init){
    // v10.28.55：候选列表从 r.solvers（多值数组）展开，而不是只取 r.solver 首项
    const solvers=[...new Set(
      DATA.reception_detail.flatMap(r => (r.solvers && r.solvers.length) ? r.solvers : [r.solver])
    )].filter(Boolean).sort();
    // 合并用户自定义接待人（不在数据里的也展示，可正常筛）
    const merged = [...new Set([...solvers, ...extras])].sort();
    sl.innerHTML=`<label class="tg"><input type="checkbox" value="__ALL__" checked><span>全部</span></label>`+
      merged.map(s=>{
        const isExtra = extras.indexOf(s) !== -1 && solvers.indexOf(s) === -1;
        return `<label class="tg" data-name="${esc(s)}"${isExtra?' data-extra="1" title="自定义接待人"':''}><input type="checkbox" value="${esc(s)}"><span>${esc(s)}${isExtra?' <i style="color:#9bb;font-size:10px">★</i>':''}</span></label>`;
      }).join('');
    const updateTrigger=()=>{
      const sels=[...sl.querySelectorAll('input:checked')].map(i=>i.value);
      trig.textContent = (sels.includes('__ALL__')||sels.length===0) ? '全部接待人' : `已选 ${sels.length} 人`;
    };
    sl.querySelectorAll('input').forEach(cb=>{
      cb.onchange=()=>{
        if(cb.value==='__ALL__'){
          sl.querySelectorAll('input').forEach(o=>{ if(o!==cb) o.checked=cb.checked; });
        } else {
          const all=sl.querySelector('input[value="__ALL__"]');
          const specifics=[...sl.querySelectorAll('input')].filter(o=>o.value!=='__ALL__');
          all.checked = specifics.length>0 && specifics.every(o=>o.checked);
        }
        updateTrigger();
        detailState.page=1; renderReception();
      };
    });
    trig.onclick=(e)=>{ e.stopPropagation(); panel.style.display = panel.style.display==='none'?'block':'none'; };
    search.oninput=()=>{ const q=search.value.trim().toLowerCase();
      sl.querySelectorAll('label.tg').forEach(lb=>{ const n=(lb.dataset.name||'').toLowerCase(); lb.style.display = (!q || n.includes(q) || lb.querySelector('input').value==='__ALL__')?'':'none'; }); };
    document.addEventListener('click',(e)=>{ if(wrap && !wrap.contains(e.target)){ panel.style.display='none'; } });
    // +新增接待人 按钮 + 输入框回车
    const addBtn=document.getElementById('rSolverAddBtn');
    const addInput=document.getElementById('rSolverAddInput');
    const addMsg=document.getElementById('rSolverAddMsg');
    const addSolver=()=>{
      const name=(addInput.value||'').trim();
      if(!name){ addMsg.style.color='#c33'; addMsg.textContent='请输入姓名'; return; }
      // 去重：已经在候选里就只勾选上
      const exists = sl.querySelector(`input[value="${CSS.escape(name)}"]`);
      if(exists){
        exists.checked = true;
        // 取消勾选 __ALL__
        const allCb = sl.querySelector('input[value="__ALL__"]');
        if(allCb) allCb.checked = false;
        addMsg.style.color='#589'; addMsg.textContent='已存在「'+name+'」，已勾选';
        updateTrigger();
        detailState.page=1; renderReception();
        return;
      }
      // 持久化
      if(!extras.includes(name)) extras.push(name);
      try{ localStorage.setItem(EXT_KEY, JSON.stringify(extras)); }catch(_){ }
      // 插入到候选（按字母序插入）
      const allLabels=[...sl.querySelectorAll('label.tg')].filter(l=>l.querySelector('input').value!=='__ALL__');
      const lb=document.createElement('label');
      lb.className='tg'; lb.dataset.name=name; lb.dataset.extra='1'; lb.title='自定义接待人';
      lb.innerHTML=`<input type="checkbox" value="${esc(name)}" checked><span>${esc(name)} <i style="color:#9bb;font-size:10px">★</i></span>`;
      // 找字母序插入位置
      let inserted = false;
      for(const a of allLabels){
        const an = a.dataset.name||'';
        if(name.localeCompare(an, 'zh') < 0){ a.parentNode.insertBefore(lb, a); inserted=true; break; }
      }
      if(!inserted) sl.appendChild(lb);
      // 绑定 change
      lb.querySelector('input').onchange=()=>{
        const all=sl.querySelector('input[value="__ALL__"]');
        const specifics=[...sl.querySelectorAll('input')].filter(o=>o.value!=='__ALL__');
        all.checked = specifics.length>0 && specifics.every(o=>o.checked);
        updateTrigger();
        detailState.page=1; renderReception();
      };
      // 取消勾选 __ALL__
      const allCb = sl.querySelector('input[value="__ALL__"]');
      if(allCb) allCb.checked = false;
      updateTrigger();
      addMsg.style.color='#285'; addMsg.textContent='已新增「'+name+'」并默认勾选';
      addInput.value='';
      detailState.page=1; renderReception();
    };
    if(addBtn) addBtn.onclick=addSolver;
    if(addInput) addInput.onkeydown=(e)=>{ if(e.key==='Enter'){ e.preventDefault(); addSolver(); } };
    sl.dataset.init='1';
    updateTrigger();
  }
  const rt=document.getElementById('recTagFilter');
  if(!rt.dataset.init){
    ALL_TAGS.forEach(tg=>{
      const l=document.createElement('label'); l.className='tg';
      l.innerHTML=`<input type="checkbox" value="${esc(tg)}"><span>${esc(tg)}</span>`;
      l.querySelector('input').onchange=()=>{ recTagSel=[...rt.querySelectorAll('input:checked')].map(i=>i.value); l.classList.toggle('active', l.querySelector('input').checked); detailState.page=1; renderReception(); };
      rt.appendChild(l);
    });
    rt.dataset.init='1';
  }
}
function recFiltered(){
  const s=document.getElementById('rStart').value, e=document.getElementById('rEnd').value;
  const sels=[...document.querySelectorAll('#rSolver input:checked')].map(i=>i.value);
  const allOn = sels.includes('__ALL__') || sels.length===0;
  return DATA.reception_detail.filter(r=>{
    const d=r.time.slice(0,10);
    if(s && d<s) return false;
    if(e && d>e) return false;
    // v10.28.55：多选支持 —— 只要该记录的任何一位接待人（r.solvers）被勾选即显示
    const _rs = (r.solvers && r.solvers.length) ? r.solvers : [r.solver];
    if(!allOn && !_rs.some(x=>sels.includes(x))) return false;
    if(recTagSel.length && !(r.tags||[]).some(x=>recTagSel.includes(x))) return false;
    return true;
  });
}
function renderReception(){
  initRcvSolver();
  const f=recFiltered();
  const map={};
  // v10.28.55：多选支持 —— 一条记录的多位接待人（r.solvers）分别累计
  f.forEach(r=>{
    const _rs = (r.solvers && r.solvers.length) ? r.solvers : [r.solver];
    _rs.forEach(s=>{
      if(!s) return;
      const m=map[s]||(map[s]={solver:s,count:0,users:new Set(),types:{},tags:{}});
      m.count++; if(r.uid) m.users.add(r.uid); m.types[r.type]=(m.types[r.type]||0)+1;
      // v10.23：标签按 TS_TAG_MAP 合并成大类 + 计数；明细列每个 chip 后加 (N)
      (r.tags||[]).forEach(t=>{
        const key = TS_TAG_MAP[t] || t;
        m.tags[key] = (m.tags[key]||0) + 1;
      });
    });
  });
  const rows=Object.values(map).map(m=>({
    solver:m.solver,count:m.count,users:m.users.size,types:m.types,
    tags:Object.entries(m.tags).sort((a,b)=>b[1]-a[1]).map(([k,v])=>({k,v}))
  })).sort((a,b)=>b.count-a.count);
  document.getElementById('rectblmeta').textContent=`筛选后共 ${rows.length} 位接待人，接待明细 ${f.length} 条（来源 cb_reception_log）`;
  document.getElementById('rectbody').innerHTML=rows.map(m=>{const t=m.types||{};
    const chips=m.tags.length
      ? m.tags.map(x=>`<span class="tg-chip" data-tag="${esc(x.k)}" title="点击查看该标签明细"><span class="tg-name">${esc(x.k)}</span><b class="tg-count">${x.v}</b></span>`).join('')
      : '—';
    return `<tr data-solver="${esc(m.solver)}">
      <td>${esc(m.solver)}</td><td>${m.count}</td><td>${m.users}</td>
      <td>${t.book_user_visit||0}</td><td>${t.owe_rent_user||0}</td><td>${t.silent_user||0}</td>
      <td><span class="other-drill ${t.other?'':'zero'}" data-solver="${esc(m.solver)}">${t.other||0}</span></td>
      <td class="tagcol">${chips}</td>
      <td style="color:var(--blue);font-weight:700">查看 ›</td></tr>`;}).join('');
  document.getElementById('rectbody').querySelectorAll('tr').forEach(tr=>tr.onclick=()=>{detailState={solver:tr.dataset.solver,page:1};showRecDetail();});
  // v10.23：点击 chip 直接下钻该接待人的该标签明细
  document.getElementById('rectbody').querySelectorAll('.tg-chip[data-tag]').forEach(sp=>sp.onclick=(e)=>{
    e.stopPropagation();
    const tr=sp.closest('tr'); const solver=tr.dataset.solver; const tag=sp.dataset.tag;
    detailState={solver,page:1}; tsDetailState={tag,page:1}; recTagSel=[tag];
    showTsDetail();
  });
  document.getElementById('rectbody').querySelectorAll('.other-drill').forEach(sp=>sp.onclick=(e)=>{e.stopPropagation(); otherState={solver:sp.dataset.solver,page:1}; showRecOtherBreakdown();});
  document.getElementById('recDetailWrap').style.display='none';
  document.getElementById('recOtherWrap').style.display='none';
}
// 标签数量统计：按 recFiltered() 的时间/接待人范围，统计每条接待记录上的标签出现次数
// 业务口径：未接听/电话沟通/外呼未接通 统一归入「联系不上」大类统计
const TS_TAG_MAP = {'未接听':'联系不上','电话沟通':'联系不上','外呼未接通':'联系不上'};
const TS_CONTACT_TAGS = ['联系不上','未接听','电话沟通','外呼未接通'];
let tsTagSel = [];
function renderTagStat(){
  const sels=[...document.querySelectorAll('#rSolver input:checked')].map(i=>i.value);
  const f=recFiltered();
  const cnt={}; f.forEach(r=>{
    (r.tags||[]).forEach(t=>{
      const key = TS_TAG_MAP[t] || t;
      cnt[key] = (cnt[key]||0) + 1;
    });
  });
  const arr=Object.entries(cnt).map(([k,v])=>({label:k,value:v})).sort((a,b)=>b.value-a.value);
  const s=document.getElementById('rStart').value, e=document.getElementById('rEnd').value;
  const range = (s||e)?`${s||'最早'} ~ ${e||'最新'}` : '全部时间';
  const solverTxt = (sels.includes('__ALL__')||sels.length===0) ? '全部接待人' : sels.join('、');
  document.getElementById('tsSum').innerHTML = `统计范围：<b>${range}</b> ｜ 接待人：<b>${esc(solverTxt)}</b> ｜ 命中接待记录 <b>${f.length}</b> 条 ｜ 展示口径：未接听/电话沟通/外呼未接通 已合并为「联系不上」（同一记录多个标签各计 1 次）`;
  const maxv = arr.length?arr[0].value:1;
  const palette={'空号':'#C0392B','停机':'#E67E22','联系不上':'#7c3aed','协助换电':'#1F4E78','已告知换电':'#16a34a','欠租催收':'#c0392b'};
  document.getElementById('tsChart').innerHTML = arr.length
    ? arr.map(d=>`<div class="bar"><span class="bl" style="width:${d.value/maxv*100}%;background:${palette[d.label]||'#5b8def'}"></span><b style="cursor:pointer" data-tag="${esc(d.label)}">${esc(d.label)} ▸</b><i>${d.value}</i></div>`).join('')
    : '<div style="color:#999;font-size:12px;padding:8px 0">该范围内无接待记录。</div>';
  document.getElementById('tsChart').querySelectorAll('b[data-tag]').forEach(b=>b.onclick=()=>{
    const tag=b.dataset.tag;
    tsTagSel=[tag];
    document.getElementById('recDetailWrap').style.display='block';
    tsDetailState={tag:tag,page:1};
    showTsDetail();
  });
}
let tsDetailState={tag:'',page:1};
const TS_PS=100;
function showTsDetail(){
  const f=recFiltered().filter(r=>
    tsDetailState.tag==='联系不上'
      ? (r.tags||[]).some(t=>TS_CONTACT_TAGS.includes(t))
      : (r.tags||[]).includes(tsDetailState.tag)
  ).slice().sort((a,b)=>b.time<a.time?-1:b.time>a.time?1:0);
  const pages=Math.max(1,Math.ceil(f.length/TS_PS)), pg=Math.min(tsDetailState.page,pages);
  const slice=f.slice((pg-1)*TS_PS, pg*TS_PS);
  document.getElementById('recDetailMeta').textContent=`标签「${tsDetailState.tag}」的接待明细（共 ${f.length} 条，第 ${pg}/${pages} 页）`;
  document.getElementById('recDetailBody').innerHTML=slice.map(r=>{
    const tl=TYPE_LABEL[r.type]||r.type;
    const ph = aidToPhone[r.aid] || '—';
    return `<tr><td>${r.time}</td><td>${r.aid}</td><td>${esc(r.uid||'—')}</td><td class="ph">${ph}</td><td>${esc(r.battery_circ_time||'—')}</td><td>${esc(r.agreement_status||'—')}</td><td style="color:${USER_STATUS_COLOR[r.user_status]||'#888'};font-weight:600">${esc(r.user_status||'—')}</td><td style="color:${r.need_followup===false?'#c0392b':'#16a34a'};font-weight:600">${r.need_followup===false?'无需回访':'需要回访'}</td><td>${esc(tl)}</td><td class="tagcol">${(r.tags||[]).map(x=>`<span class="tg-chip">${esc(x)}</span>`).join('')||'—'}</td><td class="detail">${esc(r.detail)}</td></tr>`;}).join('');
  document.getElementById('recDetailWrap').style.display='block';
  document.getElementById('recDetailPager').innerHTML=`<button ${pg<=1?'disabled':''} onclick="tsDetailState.page=1;showTsDetail()">« 首页</button>
    <button ${pg<=1?'disabled':''} onclick="tsDetailState.page--;showTsDetail()">‹ 上页</button>
    <span>第 ${pg}/${pages} 页</span>
    <button ${pg>=pages?'disabled':''} onclick="tsDetailState.page++;showTsDetail()">下页 ›</button>
    <button ${pg>=pages?'disabled':''} onclick="tsDetailState.page=${pages};showTsDetail()">末页 »</button>`;
}
function showRecDetail(){
  const f=recFiltered().filter(r=>r.solver===detailState.solver);
  f.sort((a,b)=> b.time<a.time?-1:b.time>a.time?1:0);
  const pages=Math.max(1,Math.ceil(f.length/RD_PS)), pg=Math.min(detailState.page,pages);
  const slice=f.slice((pg-1)*RD_PS, pg*RD_PS);
  document.getElementById('recDetailMeta').textContent=`${esc(detailState.solver)} 的接待明细（共 ${f.length} 条，第 ${pg}/${pages} 页）`;
  document.getElementById('recDetailBody').innerHTML=slice.map(r=>{
    const tl=TYPE_LABEL[r.type]||r.type;
    const ph = aidToPhone[r.aid] || '—';
    return `<tr><td>${r.time}</td><td>${r.aid}</td><td>${esc(r.uid||'—')}</td><td class="ph">${ph}</td><td>${esc(r.battery_circ_time||'—')}</td><td>${esc(r.agreement_status||'—')}</td><td style="color:${USER_STATUS_COLOR[r.user_status]||'#888'};font-weight:600">${esc(r.user_status||'—')}</td><td style="color:${r.need_followup===false?'#c0392b':'#16a34a'};font-weight:600">${r.need_followup===false?'无需回访':'需要回访'}</td><td>${esc(tl)}</td><td class="tagcol">${(r.tags||[]).map(x=>`<span class="tg-chip">${esc(x)}</span>`).join('')||'—'}</td><td class="detail">${esc(r.detail)}</td></tr>`;}).join('');
  document.getElementById('recDetailWrap').style.display='block';
  document.getElementById('recDetailPager').innerHTML=`<button ${pg<=1?'disabled':''} onclick="detailState.page=1;showRecDetail()">« 首页</button>
    <button ${pg<=1?'disabled':''} onclick="detailState.page--;showRecDetail()">‹ 上页</button>
    <span>第 ${pg}/${pages} 页</span>
    <button ${pg>=pages?'disabled':''} onclick="detailState.page++;showRecDetail()">下页 ›</button>
    <button ${pg>=pages?'disabled':''} onclick="detailState.page=${pages};showRecDetail()">末页 »</button>`;
}

let otherState={solver:'',page:1};
const OTHER_PS=100;
function showRecOtherBreakdown(){
  const solver=otherState.solver;
  const base=recFiltered().filter(r=>r.solver===solver && r.type==='other').sort((a,b)=> b.time<a.time?-1:b.time>a.time?1:0);
  const cnt={};
  base.forEach(r=>{
    const tags=(r.tags||[]).filter(x=>x!=='其他杂项');
    if(tags.length){ tags.forEach(t=>{ cnt[t]=(cnt[t]||0)+1; }); }
    else { cnt['其他未识别']=(cnt['其他未识别']||0)+1; }
  });
  document.getElementById('recOtherMeta').textContent=`${esc(solver)} 的「其他」接待记录拆分（共 ${base.length} 条）`;
  const arr=Object.entries(cnt).sort((a,b)=>b[1]-a[1]);
  document.getElementById('recOtherStat').innerHTML=arr.length
    ? arr.map(([k,v])=>`<span class="tg-chip" style="background:#e8f4ff;border-color:#9cc3e6;color:#1F4E78">${esc(k)} <b>${v}</b></span>`).join('')
    : '<span style="color:#999;font-size:12px">暂无能进一步拆分的标签</span>';
  const pages=Math.max(1,Math.ceil(base.length/OTHER_PS)), pg=Math.min(otherState.page,pages);
  const slice=base.slice((pg-1)*OTHER_PS, pg*OTHER_PS);
  document.getElementById('recOtherBody').innerHTML=slice.map(r=>{
    const ph=aidToPhone[r.aid]||'—';
    return `<tr><td>${r.time}</td><td>${r.aid}</td><td>${esc(r.uid||'—')}</td><td class="ph">${ph}</td><td>${esc(r.battery_circ_time||'—')}</td><td>${esc(r.agreement_status||'—')}</td><td style="color:${USER_STATUS_COLOR[r.user_status]||'#888'};font-weight:600">${esc(r.user_status||'—')}</td><td class="tagcol">${(r.tags||[]).map(x=>`<span class="tg-chip">${esc(x)}</span>`).join('')||'—'}</td><td class="detail">${esc(r.detail)}</td></tr>`;
  }).join('');
  document.getElementById('recDetailWrap').style.display='none';
  document.getElementById('recOtherWrap').style.display='block';
  document.getElementById('recOtherPager').innerHTML=`<button ${pg<=1?'disabled':''} onclick="otherState.page=1;showRecOtherBreakdown()">« 首页</button>
    <button ${pg<=1?'disabled':''} onclick="otherState.page--;showRecOtherBreakdown()">‹ 上页</button>
    <span>第 ${pg}/${pages} 页</span>
    <button ${pg>=pages?'disabled':''} onclick="otherState.page++;showRecOtherBreakdown()">下页 ›</button>
    <button ${pg>=pages?'disabled':''} onclick="otherState.page=${pages};showRecOtherBreakdown()">末页 »</button>`;
}

document.getElementById('tabs').addEventListener('click',e=>{if(e.target.dataset.v){state.view=e.target.dataset.v; state.page=1;
  document.querySelectorAll('#tabs button').forEach(b=>b.classList.remove('active')); e.target.classList.add('active'); render();
  // v10.28.55：切到「回访效果」时首次拉取并按当前筛选渲染
  if(state.view==='effect'){ renderEffect(); }
}});
document.getElementById('fProvince').onchange=e=>{state.province=e.target.value; state.city=''; state.area=''; state.street=''; state.page=1; render();};
document.getElementById('fCity').onchange=e=>{state.city=e.target.value; state.area=''; state.street=''; state.page=1; render();};
document.getElementById('fArea').onchange=e=>{state.area=e.target.value; state.street=''; state.page=1; render();};
document.getElementById('fStreet').onchange=e=>{state.street=e.target.value; state.page=1; render();};
document.getElementById('fProduct').onchange=e=>{state.product=e.target.value;state.page=1;render();};
document.getElementById('fStatus').onchange=e=>{state.status=e.target.value;state.page=1;render();};
document.getElementById('fAgreementType').onchange=e=>{state.agreementType=e.target.value;state.page=1;render();};
document.getElementById('fIsLf').onchange=e=>{state.islf=e.target.value;state.page=1;render();};
document.getElementById('fLevel').onchange=e=>{state.level=e.target.value;state.page=1;render();};
document.getElementById('fBco').onchange=e=>{state.bco=e.target.value;state.page=1;render();};
document.getElementById('fBcv').onchange=e=>{state.bcv=e.target.value;state.page=1;render();};
document.getElementById('fCircOpType').onchange=e=>{state.circOpType=e.target.value;state.page=1;render();};
document.getElementById('fSmsr').onchange=e=>{state.smsr=e.target.value;state.page=1;render();};
['rStart','rEnd'].forEach(id=>document.getElementById(id).onchange=()=>{detailState.page=1;renderReception();});
document.getElementById('btnTagStat').onclick=()=>{renderTagStat();};
document.getElementById('rReset').onclick=()=>{document.getElementById('rStart').value='';document.getElementById('rEnd').value='';const sl=document.getElementById('rSolver'); if(sl.dataset.init){ sl.querySelectorAll('input').forEach(o=>{o.checked=(o.value==='__ALL__');}); document.getElementById('rSolverTrigger').textContent='全部接待人'; } detailState={solver:'',page:1};recTagSel=[];document.querySelectorAll('#recTagFilter input:checked').forEach(i=>{i.checked=false; i.closest('.tg').classList.remove('active');});renderReception();};
document.getElementById('btnTagStat').onclick=()=>{renderTagStat();};

// v10.23：导出当前接待看板筛选结果为 CSV（含 接待时间/接待人/协议ID/用户ID/手机号/电池流通时间/协议状态/用户状态/类型/标签/接待内容）
const REC_EXPORT_HEAD = ['接待时间','接待人','协议ID','用户ID','手机号','电池最后流通时间','协议状态','用户状态','类型','标签','接待内容'];
function csvEsc(v){
  v = (v==null?'':v).toString();
  return /[",\n\r]/.test(v) ? '"'+v.replace(/"/g,'""')+'"' : v;
}
document.getElementById('btnRecExport').onclick=()=>{
  const f = recFiltered().slice().sort((a,b)=> b.time<a.time?-1:b.time>a.time?1:0);
  if(!f.length){ alert('当前筛选下没有可导出的接待记录，请先放宽条件。'); return; }
  const TYPE_LABEL = window._TYPE_LABEL || {};
  const rows = [REC_EXPORT_HEAD.join(',')];
  for(const r of f){
    const tl = TYPE_LABEL[r.type] || r.type || '';
    const tags = (r.tags||[]).join('/');
    const ph = (typeof aidToPhone!=='undefined' && aidToPhone[r.aid]) || '';
    rows.push([r.time, fmtSolver(r.solver)||'—', r.aid||'', r.uid||'', ph, r.battery_circ_time||'', r.agreement_status||'', r.user_status||'—', r.need_followup===false?'无需回访':'需要回访', tl, tags, r.detail||''].map(csvEsc).join(','));
  }
  const s=document.getElementById('rStart').value, e=document.getElementById('rEnd').value;
  const tag=recTagSel.length?`__${recTagSel.join('-')}`.replace(/[\\\/:*?"<>|]/g,'_'):'';
  const fname=`接待名单_${s||'earliest'}_${e||'latest'}${tag}_${f.length}条_${Date.now()}.csv`;
  const blob = new Blob(['\ufeff'+rows.join('\n')], {type:'text/csv;charset=utf-8'});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=fname; a.click();
};
document.getElementById('recOtherClose').onclick=()=>{document.getElementById('recOtherWrap').style.display='none';};
let tA; document.getElementById('fAgreement').oninput=e=>{clearTimeout(tA);tA=setTimeout(()=>{state.agr=e.target.value;state.page=1;render();},200);};
let tP; document.getElementById('fPhone').oninput=e=>{clearTimeout(tP);tP=setTimeout(()=>{state.phone=e.target.value.trim();state.analysisPage=1;if(state.view==='analysis')renderAnalysis();},200);};
// v10.28.55：低频用户数据分析 Tab 7 维度筛选绑定
document.getElementById('aProduct').onchange=e=>{state.product=e.target.value;state.analysisPage=1;renderAnalysis();};
document.getElementById('aStatus').onchange=e=>{state.status=e.target.value;state.analysisPage=1;renderAnalysis();};
document.getElementById('aAgreementType').onchange=e=>{state.agreementType=e.target.value;state.analysisPage=1;renderAnalysis();};
document.getElementById('aIsLf').onchange=e=>{state.islf=e.target.value;state.analysisPage=1;renderAnalysis();};
document.getElementById('aLevel').onchange=e=>{state.level=e.target.value;state.analysisPage=1;renderAnalysis();};
let tAgr; document.getElementById('aAgreement').oninput=e=>{clearTimeout(tAgr);tAgr=setTimeout(()=>{state.agreement=e.target.value.trim();state.analysisPage=1;renderAnalysis();},200);};
let tAph; document.getElementById('aPhone').oninput=e=>{clearTimeout(tAph);tAph=setTimeout(()=>{state.phone=e.target.value.trim();state.analysisPage=1;renderAnalysis();},200);};
document.getElementById('aReset').onclick=()=>{
  ['aProduct','aStatus','aAgreementType','aIsLf','aLevel'].forEach(id=>{const el=document.getElementById(id); if(el) el.value='';});
  document.getElementById('aAgreement').value='';
  document.getElementById('aPhone').value='';
  state.product=''; state.status=''; state.agreementType=''; state.islf=''; state.level=''; state.agreement=''; state.phone='';
  state.analysisPage=1;
  renderAnalysis();
};
let tK; document.getElementById('fKw').oninput=e=>{clearTimeout(tK);tK=setTimeout(()=>{state.kw=e.target.value;state.page=1;render();},200);};
document.getElementById('btnReset').onclick=()=>{state={view:state.view,province:'',city:'',area:'',street:'',product:'',status:'',agreementType:'',islf:'',level:'',bco:'',bcv:'',circOpType:'',smsr:'',days:[],agr:'',agreement:'',kw:'',tags:[],sortKey:'id',sortDir:1,page:1,phone:'',analysisPage:1};
  document.querySelectorAll('#fDays input').forEach(cb=>cb.checked=false);
  document.getElementById('fDaysTrigger').textContent='全部';
  ['fProvince','fCity','fArea','fStreet','fProduct','fStatus','fAgreementType','fIsLf','fLevel','fBco','fBcv','fCircOpType','fSmsr','fAgreement','fKw','fPhone','aProduct','aStatus','aAgreementType','aIsLf','aLevel','aAgreement','aPhone'].forEach(id=>{const el=document.getElementById(id); if(el)el.value='';});
  document.querySelectorAll('#tagFilter input:checked').forEach(i=>{i.checked=false; i.closest('.tg').classList.remove('active');});
  render();};
document.querySelectorAll('th').forEach(th=>th.onclick=()=>{const k=th.dataset.k; if(state.sortKey===k)state.sortDir*=-1;else{state.sortKey=k;state.sortDir=1;} state.page=1;render();});
// v10.28.55：导出主表 —— all=true 忽略所有筛选导出全量；all=false 仅导出当前筛选
function exportMainCsv(all){
  __EXPORT_ALL__ = !!all;
  let f;
  try{ f = apply(); } finally { __EXPORT_ALL__ = false; }
  if(!f.length){ alert(all?'没有可导出的记录。':'当前筛选下没有可导出的记录，请先放宽条件，或改用「导出全部数据 CSV」。'); return; }
  const head=['协议ID','用户ID','手机号','当前手机号','接收时间','发送结果','失败原因','使用天数','电池产品','电池SN','电池最后流通时间','操作类型','是否流通','电压(V)','电流(A)','电量','在线状态','押金(元)','押金划扣状态','租赁套餐','省份','城市','区域','街道','社区','协议类型','协议状态','激活时间','租金到期','15天','30天','45天','60天','月均换电频次','是否低频','档位','最近接待','接待人','接待类型','接待内容','跟进人','跟进状态','跟进备注','标签'];
  const lines=[head.join(',')].concat(f.map(r=>{
    const mf = r.mf!=null ? Number(r.mf).toFixed(2) : (r.c60!=null ? (r.c60/2).toFixed(2) : '');
    const dep = r.dep!=null ? Number(r.dep).toFixed(2) : '';
    const statusLabel = r.status==='owe_rent'?'欠租':(r.status==='unsubscribing'?'退订中':'生效中');
    const dstLabel = {'on':'在押','off':'已退/已划扣'}[r.dst]||r.dst||'';
    return [r.id,r.uid||'',r.ph,r.cph||r.ph||'',r.smst||'',r.smsr||'',r.smsf||'',r.days!=null?r.days:'',r.pd,r.bsn||'',r.bcl||'',r.bco||'',(r.bcv?'在流通':'暂无电池'),r.vol||'',r.cur||'',r.soc||'',r.onl||'',dep,dstLabel,r.pkg||'',r.pr,r.ci,r.ar,r.st,r.co,r.at||'',statusLabel,r.ac,r.re,r.c15,r.c30,r.c45,r.c60,mf,r.lf?'低频':'',r.ln,r.rt||'',fmtSolver(r.rs)||'',r.rty||'',(r.rd||'').slice(0,40),fuGet(r.id,'fu1'),fuGet(r.id,'fu2'),fuGet(r.id,'fu3'),(r.tags||[]).join('/')].map(v=>{v=(v==null?'':v).toString();return /[",\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v;}).join(',');
  }));
  const blob=new Blob(['\ufeff'+lines.join('\n')],{type:'text/csv;charset=utf-8'});
  const _vn={all:'全部活跃协议',owe:'欠租催收',lf:'低频用户'}[state.view]||state.view;
  const _tag=all?'全部':'筛选';
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob);
  a.download=`${_vn}_${_tag}_${f.length}条_${Date.now()}.csv`; a.click();
}
document.getElementById('btnCsv').onclick=()=>exportMainCsv(false);
document.getElementById('btnCsvAll').onclick=()=>{
  if(!confirm('将忽略当前所有筛选条件，导出本 Tab 口径下的全部记录。\n\n当前 Tab：'+({all:'全部活跃协议',owe:'欠租催收',lf:'低频用户'}[state.view]||state.view)+'\n确定继续吗？')) return;
  exportMainCsv(true);
};
const sp=document.getElementById('statsPanel'), st=document.getElementById('statsToggle');
st.addEventListener('click',()=>{const o=sp.classList.toggle('open');st.setAttribute('aria-expanded',o);});

// ===== 看板内一键同步数据库（需通过 start.bat / run_serve.bat 启动的本地服务） =====
(function(){
  const btn=document.getElementById('btnSync'); if(!btn) return;
  const modal=document.getElementById('syncModal'), logEl=document.getElementById('syncLog'), barEl=document.getElementById('syncBar');
  if(!window.__SERVE__){
    const banner=document.getElementById('noServeBanner'); if(banner) banner.style.display='block';
    btn.disabled=true; btn.title='请双击 start.bat 启动本地服务后再使用同步功能';
    btn.textContent='[SYNC] 同步(需本地服务)';
    btn.onclick=()=>alert('同步功能需要本地服务。\n请关闭本页，双击 start.bat（推荐，会自动打开浏览器）或 run_serve.bat（前台运行）启动本地服务，\n再用浏览器打开 http://127.0.0.1:8173 即可在看板内一键同步。\n\n提示：run_sync.bat 只是「在线更新」脚本，并不会启动服务。');
    return;
  }
  let timer=null;
  let lastRawErr='';
  const titleEl=document.getElementById('syncTitle');
  const errWrap=document.getElementById('syncErrWrap');
  const errEl=document.getElementById('syncErr');
  const errActions=document.getElementById('syncErrActions');
  function setLog(text,pct){ logEl.textContent=text; if(pct!=null) barEl.style.width=Math.min(100,pct)+'%'; }
  async function poll(){
    try{
      const st2=await fetch('/sync_status').then(r=>r.json());
      const lines=(st2.log||[]).join('\n');
      const pct=st2.total?Math.round(st2.step/st2.total*100):(st2.running?10:100);
      setLog(lines||'同步中…',pct);
      if(!st2.running && st2.finished_at){
        clearInterval(timer); timer=null;
        if(st2.error){
          titleEl.textContent='[FAIL] 同步失败';
          lastRawErr=(st2.log||[]).join('\n')+'\n\n===== 详细错误 =====\n'+(st2.raw_stderr||'');
          setLog(lines+'\n\n[FAIL] 同步失败：'+st2.error,100);
          errEl.textContent=lastRawErr;
          errWrap.style.display='block';
          errActions.style.display='block';
          document.getElementById('syncHint').textContent='错误日志已保存到 out/sync_error.log，可查看或复制';
          btn.disabled=false; btn.classList.remove('busy'); btn.textContent='[SYNC] 同步数据库';
        }
        else { setLog(lines+'\n\n[OK] 同步完成，正在刷新看板…',100); setTimeout(()=>location.reload(),600); }
      }
    }catch(e){ setLog('读取进度失败：'+e,null); }
  }
  document.getElementById('btnCopyErr').onclick=async()=>{
    try{ await navigator.clipboard.writeText(lastRawErr); alert('已复制错误日志，请粘贴给技术支持'); }
    catch(e){ alert('复制失败，请手动选中红色错误框内容复制'); }
  };
  document.getElementById('btnCloseModal').onclick=()=>{ modal.classList.remove('show'); };
  btn.onclick=async()=>{
    if(!confirm('将重新连接数据库并刷新看板数据，约需 1~3 分钟，是否继续？')) return;
    btn.disabled=true; btn.classList.add('busy'); btn.textContent='[WAIT] 同步中…';
    modal.classList.add('show'); setLog('正在启动同步…',3);
    // v10.28.55：先做一次轻量诊断，再正式触发同步，避免「点了同步但页面毫无反应」
    try{
      const diag = await fetch('/api/diag',{method:'GET',cache:'no-store'});
      const dj = await diag.json().catch(()=>({}));
      if(!dj.ok){
        setLog('【诊断】本地服务未正常响应：'+(dj.msg||dj.error||'未知')+'\n\n可能原因：\n1) 旧版本 serve.py 仍在运行（未重启服务）\n2) 端口 8173 被其他程序占用\n3) 升级后未双击 start.bat 重启\n\n正在尝试用备用通道（GET）触发同步…',null);
      } else {
        setLog('【诊断】服务在线 ｜ 版本 '+(dj.version||'?')+' ｜ 端口 '+(dj.port||'?')+' ｜ IP '+(dj.lan_ip||'?')+'\n正在启动同步…',8);
      }
    }catch(_e){ /* 诊断失败不阻断，继续走主流程 */ }
    // v10.28.55：先尝试 POST，失败则降级到 GET（兼容极少数被代理/防火墙拦截 POST 的网络环境）
    let triggered = false;
    try{
      const res=await fetch('/sync',{method:'POST'});
      const j=await res.json().catch(()=>({}));
      if(j && j.ok){ triggered = true; }
      else if(j && j.msg && j.msg.indexOf('进行中')>=0){ triggered = true; }
      else if(j && j.msg){ setLog('同步启动返回：'+j.msg+'\n（仍继续轮询进度…）',8); triggered = true; }
    }catch(e1){
      try{
        const r2=await fetch('/sync',{method:'GET',cache:'no-store'});
        const j2=await r2.json().catch(()=>({}));
        if(j2 && j2.ok){ triggered = true; setLog('（POST 失败，已用 GET 兜底触发同步）',8); }
      }catch(e2){ /* 留到下面统一报错 */ }
    }
    if(triggered){
      if(!timer) timer=setInterval(poll,3000);
      return;
    }
    // v10.28.55：失败时给出可执行的指引（不再用「run_sync.bat」这种误导性字眼）
    const tip = [
      '【同步失败】服务未响应同步请求。',
      '',
      '📌 最常见原因：升级到新版本后，没有重启本地服务（旧的 serve.py 仍在运行）。',
      '',
      '🔧 解决办法（任选其一）：',
      '  1) 关掉当前页面，回到 lowfreq_local 文件夹',
      '  2) 双击 start.bat（推荐，会在后台拉起服务并自动打开浏览器）',
      '  3) 或双击 run_serve.bat（前台运行，可直接看到日志）',
      '  4) 注意：run_sync.bat 是「在线更新」脚本，并不会启动服务',
      '',
      '💡 进一步诊断：可在本机浏览器打开 http://127.0.0.1:8173/api/diag 查看服务版本/端口/IP。',
      '   若 /api/diag 返回 404，说明服务版本过旧，请务必重启服务。'
    ].join('\n');
    alert(tip);
    btn.disabled=false; btn.classList.remove('busy'); btn.textContent='[SYNC] 同步数据库';
    modal.classList.remove('show');
  };
})();

// ===== 回访排班 Tab =====
let dData = {items:[], tags:null, staff:null, cats:[]};
let curItem = null;
let curLevel = 'L1';
let dPage = 1;
const D_PAGE = 50;
let dState = {solver:'', status:'', province:'', city:'', area:'', street:'', product:'', agrStatus:'', level:'', visitResult:'', visitFrom:'', visitTo:'', days:[], kw:'', recCategory:''};

function esc2(s){ s = s==null?'':String(s); return s.replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function todayStr(){ const d=new Date(); const p=n=>String(n).padStart(2,'0'); return d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate()); }
const dTip = ()=>document.getElementById('dispatchTip');

// 标签弹窗的级别切换
document.querySelectorAll('.tag-tabs button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('.tag-tabs button').forEach(x=>x.classList.remove('active'));
  b.classList.add('active'); curLevel=b.dataset.l; renderTagOptions();
});

function renderTodayStaff(staffList, todayList, quotas, defaultQuota){
  const wrap=document.getElementById('todayStaffWrap');
  const set=new Set(todayList);
  if(!staffList.length){ wrap.innerHTML='<span style="color:#999;font-size:12px">请先在「人员管理」中添加接待人员</span>'; return; }
  wrap.innerHTML=staffList.map(name=>{
    const checked=set.has(name)?'checked':'';
    const val=(quotas[name]==null)?'':quotas[name];
    const disabledCls=set.has(name)?'':'disabled';
    return `<label class="staff-card ${disabledCls}"><input type="checkbox" value="${esc2(name)}" ${checked}><span class="name">${esc2(name)}</span><input type="number" min="1" class="qinput" data-name="${esc2(name)}" value="${val}" placeholder="默认${defaultQuota}"></label>`;
  }).join('');
  // 勾选变化时启用/禁用数量输入
  wrap.querySelectorAll('input[type=checkbox]').forEach(cb=>{
    cb.onchange=()=>{
      const card=cb.closest('.staff-card');
      const qinput=card.querySelector('.qinput');
      if(cb.checked){ card.classList.remove('disabled'); qinput.style.display=''; }
      else { card.classList.add('disabled'); qinput.style.display='none'; }
    };
  });
}

// 生成名单筛选器：电池产品/代理商/地理级联
function collectGenFilter(){
  const ut=[];
  if(document.getElementById('filterTypeLf').checked) ut.push('lf');
  if(document.getElementById('filterTypeOwe').checked) ut.push('owe');
  return {
    product: document.getElementById('filterProduct').value,
    agent: document.getElementById('filterAgent').value,
    city: document.getElementById('filterCity').value,
    area: document.getElementById('filterArea').value,
    street: document.getElementById('filterStreet').value,
    community: document.getElementById('filterCommunity').value,
    user_types: ut
  };
}

function renderGenFilterOptions(genFilter){
  const rows = (typeof DATA!=='undefined' && DATA.rows) || [];
  const uniq = (arr)=>[...new Set(arr.filter(Boolean))].sort();
  fillSelect('filterProduct', opts(uniq(rows.map(r=>r.pd)),'全部电池产品'));
  fillSelect('filterAgent', opts(uniq(rows.map(r=>r.ag)),'全部代理商'));
  const gf = genFilter||{};
  const cities = uniq(rows.map(r=>r.ci));
  fillSelect('filterCity', opts(cities,'全部城市'));
  const areaBase = gf.city ? rows.filter(r=>r.ci===gf.city) : rows;
  fillSelect('filterArea', opts(uniq(areaBase.map(r=>r.ar)),'全部区域'));
  const streetBase = gf.area ? areaBase.filter(r=>r.ar===gf.area) : areaBase;
  fillSelect('filterStreet', opts(uniq(streetBase.map(r=>r.st)),'全部街道'));
  const commBase = gf.area ? rows.filter(r=>r.ci===gf.city&&r.ar===gf.area) : (gf.city?rows.filter(r=>r.ci===gf.city):rows);
  fillSelect('filterCommunity', opts(uniq(commBase.map(r=>r.co)),'全部社区'));
  fillSelect('filterCircQuarter', opts(uniq(rows.map(r=>r.cq).filter(Boolean)),'全部流通季度'));
  if(gf.product) document.getElementById('filterProduct').value=gf.product;
  if(gf.agent) document.getElementById('filterAgent').value=gf.agent;
  if(gf.city) document.getElementById('filterCity').value=gf.city;
  if(gf.area) document.getElementById('filterArea').value=gf.area;
  if(gf.street) document.getElementById('filterStreet').value=gf.street;
  if(gf.community) document.getElementById('filterCommunity').value=gf.community;
  document.getElementById('filterAgreementType').value = gf.agreement_type || 'all';
  const ut=gf.user_types||['lf'];
  document.getElementById('filterTypeLf').checked=ut.includes('lf');
  document.getElementById('filterTypeOwe').checked=ut.includes('owe');
  const syncTypeOptionClass=(id)=>{
    const cb=document.getElementById(id);
    const opt=cb.closest('.type-option');
    if(opt) opt.classList.toggle('checked', cb.checked);
  };
  ['filterTypeLf','filterTypeOwe'].forEach(id=>syncTypeOptionClass(id));
  const rebuild = ()=>{ renderGenFilterOptions(collectGenFilter()); renderDispatch(); };
  document.getElementById('filterCity').onchange=rebuild;
  document.getElementById('filterArea').onchange=rebuild;
  document.getElementById('filterStreet').onchange=rebuild;
  document.getElementById('filterProduct').onchange=()=>renderDispatch();
  document.getElementById('filterAgent').onchange=()=>renderDispatch();
  document.getElementById('filterCommunity').onchange=()=>renderDispatch();
  document.getElementById('filterCircQuarter').onchange=()=>renderDispatch();
  document.getElementById('filterAgreementType').onchange=()=>renderDispatch();
  document.getElementById('filterTypeLf').onchange=()=>{ syncTypeOptionClass('filterTypeLf'); renderDispatch(); };
  document.getElementById('filterTypeOwe').onchange=()=>{ syncTypeOptionClass('filterTypeOwe'); renderDispatch(); };
}

function loadDispatch(){
  if(!window.__SERVE__){ const b=document.getElementById('noServeBanner'); if(b) b.style.display='block'; dTip().textContent='「回访排班」需通过 start.bat 启动本地服务后使用（内网同事访问 http://<本机内网IP>:8173）。'; return; }
  // v10.28.55 hotfix：把原本的 Promise.all(...) 改成 Promise.allSettled(...)，逐端点独立处理；
  //              任一 fetch 抛 TypeError: Failed to fetch 也不再让整批崩，能精准定位到挂掉的端点。
  const _endpoints = [
    {key:'assignments', url:'/api/assignments'},
    {key:'tags',        url:'/api/tags'},
    {key:'staff',       url:'/api/staff'},
    {key:'rec_cats',    url:'/api/rec_categories'}
  ];
  const _results = {};
  const _errs = [];
  Promise.allSettled(_endpoints.map(e =>
    fetch(e.url + '?_=' + Date.now(), {cache:'no-store', signal: AbortSignal.timeout ? AbortSignal.timeout(8000) : undefined})
      .then(r => {
        if(!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(j => ({ key:e.key, json:j }))
      .catch(err => { _errs.push(e.key + '(' + (err && err.message||err) + ')'); return { key:e.key, json:null }; })
  )).then(settled => {
    let a={items:[]}, t={}, s={staff:[], today_staff:[], quotas:{}, daily_quota:30, recall_days:3, recall_cooldown_days:5, gen_filter:{}}, c={categories:[]};
    settled.forEach(r => {
      if(r.status !== 'fulfilled' || !r.value || !r.value.json) return;
      const {key, json: j} = r.value;
      if(!j || j.ok === false) { _errs.push(key + '(服务器返回 ok:false)'); return; }
      if(key==='assignments') a=j;
      else if(key==='tags') t=j;
      else if(key==='staff') s=j;
      else if(key==='rec_cats') c=j;
    });
    if(_errs.length){ console.warn('[v10.28.55] loadDispatch 部分端点失败:', _errs); }
    dData.items = a.items || [];
    dData.tags  = t;
    dData.staff = s;
    dData.cats  = c.categories || [];
    // v10.28.55：若已按 token 限定数据范围 / 手机白名单，每次加载数据后重新过滤
    if(typeof window.__SCOPE__!=='undefined' || typeof window.__PHONE_ALLOW__!=='undefined'){
      applyScope(window.__SCOPE__, window.__PHONE_ALLOW__);
    }
    // 注入 c15（近15天换电次数）到回访任务，供优先级排序使用
    if(typeof DATA!=='undefined' && DATA.rows){
      const recById={};
      DATA.rows.forEach(r=>{ if(r.id!=null) recById[r.id]=r; });
      dData.items.forEach(it=>{ const rec=recById[it.agreement_id]; if(rec){ it.c15=rec.c15; if(!it.last_rec_time) it.last_rec_time=rec.rt||''; } });
    }
    const staffList = s.staff || [];
    const todayISO = new Date().toISOString().slice(0,10);
    if(!document.getElementById('planDate').value) document.getElementById('planDate').value=todayISO;
    if(!document.getElementById('viewDate').value) document.getElementById('viewDate').value=todayISO;
    document.getElementById('viewDate').onchange=()=>renderDispatch();
    // v10.26：planDate 变化时重新渲染表格，刷新 dnr 单元格
    const _planEl = document.getElementById('planDate');
    if(_planEl){
      const _refreshByPlan = () => { try{ if(typeof renderDispatch==='function') renderDispatch(); }catch(_){} };
      _planEl.onchange = _refreshByPlan;
      // 兼容某些浏览器只触发 input 不触发 change
      _planEl.addEventListener && _planEl.addEventListener('input', _refreshByPlan);
    }
    document.getElementById('quotaDefault').value = s.daily_quota || 30;
    document.getElementById('recallInput').value = s.recall_days || 3;
    document.getElementById('recallCooldown').value = s.recall_cooldown_days || 5;
    renderTodayStaff(staffList, s.today_staff || [], s.quotas || {}, s.daily_quota || 30);
    const sel = document.getElementById('dSolver');
    sel.innerHTML = '<option value="">全部</option>' + staffList.map(x=>`<option>${esc2(x)}</option>`).join('');
    renderGenFilterOptions(s.gen_filter || {});
    const csel = document.getElementById('cancelSolver');
    if(csel) csel.innerHTML = staffList.map(x=>`<option value="${esc2(x)}">${esc2(x)}</option>`).join('');
    initDispatchFilters();
    renderDispatch();
    loadHistoryDates();
    startVersionPolling();
    // v10.28.55：把端点加载情况上报到 dTip。若全部成功给绿色对勾；部分失败给红字+具体哪个端点挂掉。
    const tipEl = dTip();
    if(_errs.length){
      tipEl.innerHTML = '<span style="color:#c0392b">⚠ 部分数据加载失败：</span>'
        + _errs.map(e=>`<code style="background:#fff5f5;padding:1px 5px;border-radius:3px;color:#a93226">${esc2(e)}</code>`).join(' ')
        + ' <a href="javascript:void(0)" onclick="loadDispatch()" style="margin-left:8px;color:#1a7f37;font-weight:600">↻ 重试</a>';
    } else {
      tipEl.innerHTML = '<span style="color:#1a7f37">✓ 数据加载成功（'+ dData.items.length +' 条回访任务）</span>';
    }
    // v10.28.55：同步更新顶部服务状态徽章
    if(typeof updateServeBadge==='function') updateServeBadge(true, _errs.length ? '部分端点异常' : '');
  }).catch(e=>{
    // Promise.allSettled 理论不会触发这里，留给极端兜底
    dTip().textContent='加载失败：'+e;
    if(typeof updateServeBadge==='function') updateServeBadge(false, String(e));
  });
}

// v10.21.6：数据版本轮询——后端任何写操作（同步数据库/追加排班/分配/清空调度）后 bump 版本号，
// 主服务器与各客户端前端每 5s 查一次 /api/version，变化即自动刷新。
// v10.28.55：因 DATA 是生成期嵌入 HTML 的，版本变化时若当前在「依赖内嵌 DATA 的视图」
// （effect / reception / lf / analysis / all / owe），整页 reload 才能拿到最新 DATA。
// 仍在 dispatch 类视图的保留 loadDispatch() 路径（这部分数据走 assignments.json）。
let _dvTimer=null, _dvStarted=false;
async function checkDataVersion(){
  try{
    const j = await fetch('/api/version').then(r=>r.json());
    if(typeof window.__DATA_VERSION__ === 'undefined'){ window.__DATA_VERSION__ = j.version; return; }
    if(j.version !== window.__DATA_VERSION__){
      const oldV = window.__DATA_VERSION__;
      window.__DATA_VERSION__ = j.version;
      const v = state.view || '';
      // 依赖内嵌 DATA 的视图 → 整页 reload；force_run 后端已重新生成 HTML，DATA 是最新的
      if(['effect','reception','lf','analysis','all','owe','dispatch_overview'].includes(v)){
        console.log('[v10.28.55] DATA_VERSION', oldV, '→', j.version, ' 视图', v, '需 reload');
        try{ location.reload(); }catch(_){}
        return;
      }
      // dispatch / schedule / history → 走 loadDispatch 路径
      if(['dispatch','dispatch_schedule','dispatch_history'].includes(v)){
        loadDispatch();
      }
    }
  }catch(_){}
}
function startVersionPolling(){
  if(_dvStarted) return;
  _dvStarted = true;
  fetch('/api/version').then(r=>r.json()).then(j=>{ window.__DATA_VERSION__ = j.version; }).catch(()=>{});
  _dvTimer = setInterval(checkDataVersion, 5000);
}

// v10.28.55 hotfix：实时探活服务（每 8 秒一次 /api/health），如失联立即显示顶部黄条并给「立即重试」按钮。
// 正常时右上角显示绿色小点；连续 2 次失败 → 顶部条 + 列出最后 4 次失败原因。
let _hbTimer = null, _hbFail = 0, _hbLast4 = [];
async function _probeOnce(){
  const t0 = Date.now();
  try{
    const ctrl = (typeof AbortController!=='undefined') ? new AbortController() : null;
    const to = ctrl ? setTimeout(()=>ctrl.abort(), 4000) : null;
    const r = await fetch('/api/health' + '?_=' + Date.now(), {cache:'no-store', signal: ctrl ? ctrl.signal : undefined});
    if(to) clearTimeout(to);
    if(!r.ok) throw new Error('HTTP ' + r.status);
    const j = await r.json();
    if(!j.ok) throw new Error('ok:false');
    _hbFail = 0;
    _hbLast4 = [];
    updateServeBadge(true, '', Date.now() - t0);
  }catch(e){
    _hbFail += 1;
    _hbLast4.push(Date.now().toTimeString().slice(0,8) + ' ' + (e.message || e));
    if(_hbLast4.length > 4) _hbLast4.shift();
    updateServeBadge(false, _hbLast4[_hbLast4.length-1]);
  }
}
function startHeartbeat(){
  if(_hbTimer) return;
  _hbTimer = setInterval(_probeOnce, 8000);
  // 延迟首次探，避免和初次 loadDispatch 抢资源
  setTimeout(_probeOnce, 1500);
}
function updateServeBadge(ok, detail, latencyMs){
  const bar = document.getElementById('serveStatusBar');
  const icn = document.getElementById('serveStatusIcon');
  const txt = document.getElementById('serveStatusText');
  const det = document.getElementById('serveStatusDetail');
  // 全局角标：右上角 [SYNC] 旁添一个 dot（小圆点），不破坏现有布局
  let dot = document.getElementById('serveStatusDot');
  if(!dot){
    dot = document.createElement('span');
    dot.id = 'serveStatusDot';
    dot.style.cssText = 'display:inline-block;width:8px;height:8px;border-radius:50%;margin:0 6px 0 2px;vertical-align:middle';
    const ref = document.getElementById('syncBtn');
    if(ref && ref.parentNode) ref.parentNode.insertBefore(dot, ref.nextSibling);
  }
  if(ok){
    bar.style.display = 'none';
    dot.style.background = '#22c55e';
    dot.title = '服务正常（' + (latencyMs||'?') + 'ms）';
  } else {
    bar.style.display = 'block';
    icn.textContent = '⚠';
    txt.textContent = _hbFail >= 2 ? ('本地服务连接已失联 × ' + _hbFail + ' 次') : '本地服务单次失败';
    det.textContent = detail ? ('| 最后错误：' + detail) : '';
    dot.style.background = '#dc2626';
    dot.title = '服务失联：' + (detail||'未知');
  }
}
// 打开/关闭"如何修复"折叠区
if(document.getElementById('serveStatusHowto')){
  document.getElementById('serveStatusHowto').onclick = () => {
    const x = document.getElementById('serveStatusHowtoBody');
    x.style.display = x.style.display === 'none' ? 'block' : 'none';
  };
}
if(document.getElementById('serveStatusRetry')){
  document.getElementById('serveStatusRetry').onclick = async () => {
    document.getElementById('serveStatusRetry').textContent = '重试中…';
    await _probeOnce();
    document.getElementById('serveStatusRetry').textContent = '↻ 立即重试';
    // 顺便也强制重载一次 loadDispatch
    if(typeof loadDispatch === 'function'){
      try{ loadDispatch(); }catch(_){}
    }
  };
}
// 启动探活
if(window.__SERVE__){ startHeartbeat(); }

function initDispatchFilters(){
  const items=dData.items;
  const provinces=[...new Set(items.map(x=>x.province))].filter(Boolean).sort();
  fillSelect('dProvince', opts(provinces,'全部省份'));
  dCascade();
  const prods=[...new Set(items.map(x=>x.product))].filter(Boolean).sort();
  fillSelect('dProduct', opts(prods,'全部产品'));
  // 使用天数多选
  const box=document.getElementById('dDays');
  const trig=document.getElementById('dDaysTrigger');
  const panel=document.getElementById('dDaysPanel');
  const wrap=document.getElementById('dDaysWrap');
  box.innerHTML = DAY_RANGES.map(r=>`<label class="tg" data-range="${r.v}"><input type="checkbox" value="${r.v}"><span>${r.t}</span></label>`).join('');
  const getChecked=()=>[...box.querySelectorAll('input:checked')].map(i=>i.value);
  const updateTrigger=()=>{ trig.textContent = getChecked().length===0 ? '全部' : `已选 ${getChecked().length} 项`; };
  const sync=()=>{ dState.days=getChecked(); updateTrigger(); };
  const apply=()=>{ sync(); dPage=1; renderAll(); };
  box.querySelectorAll('input').forEach(cb=>{ cb.onchange=apply; });
  document.getElementById('dDaysAll').onclick=()=>{ box.querySelectorAll('input').forEach(cb=>cb.checked=true); apply(); };
  document.getElementById('dDaysInv').onclick=()=>{ box.querySelectorAll('input').forEach(cb=>cb.checked=!cb.checked); apply(); };
  document.getElementById('dDaysClear').onclick=()=>{ box.querySelectorAll('input').forEach(cb=>cb.checked=false); apply(); };
  trig.onclick=(e)=>{ e.stopPropagation(); panel.style.display = panel.style.display==='none'?'block':'none'; };
  document.addEventListener('click',(e)=>{ if(wrap && !wrap.contains(e.target)){ panel.style.display='none'; } });
  sync();
}

function dCascade(){
  const items=dData.items;
  const base=items.filter(x=>{
    return (!dState.province || x.province===dState.province) &&
           (!dState.city || x.city===dState.city) &&
           (!dState.area || x.area===dState.area);
  });
  const cities=[...new Set(base.map(x=>x.city))].filter(Boolean).sort();
  fillSelect('dCity', opts(cities,'全部城市'));
  if(dState.city && !cities.includes(dState.city)){ dState.city=''; dState.area=''; dState.street=''; }
  const base2=base.filter(x=>!dState.city || x.city===dState.city);
  const areas=[...new Set(base2.map(x=>x.area))].filter(Boolean).sort();
  fillSelect('dArea', opts(areas,'全部区域'));
  if(dState.area && !areas.includes(dState.area)){ dState.area=''; dState.street=''; }
  const base3=base2.filter(x=>!dState.area || x.area===dState.area);
  const streets=[...new Set(base3.map(x=>x.street))].filter(Boolean).sort();
  fillSelect('dStreet', opts(streets,'全部街道'));
  if(dState.street && !streets.includes(dState.street)){ dState.street=''; }
  document.getElementById('dProvince').value=dState.province;
  document.getElementById('dCity').value=dState.city;
  document.getElementById('dArea').value=dState.area;
  document.getElementById('dStreet').value=dState.street;
}

function daysSince(dateStr){
  if(!dateStr) return null;
  const d=new Date(dateStr.slice(0,10));
  if(isNaN(d.getTime())) return null;
  return (Date.now()-d.getTime())/86400000;
}
function isPriority(it){
  const lastRec = it.last_rec_time || it.last_rec_detail || '';
  const days = daysSince(lastRec);
  if(days===null || days < 15) return false;             // 无回访记录或回访不足15天
  if(Number(it.c15||0) > 0) return false;               // 近15天有换电(归还)记录
  const detail = (it.last_rec_detail||'') + ' ' + (it.last_rec_solver||'');
  if(/暂无电池|手里没电池|手头没电池|没有电池|无电池|没拿到电池/.test(detail)) return false;
  if(/暂存|寄存|寄放|暂放|暂代存放/.test(detail)) return false;
  if(it.status==='unsubscribing' || /退订|终止协议|解约|退订中/.test(detail)) return false;
  return true;
}

function renderDispatch(){
  const items=dData.items.filter(genFilterMatch);
  const today=new Date().toISOString().slice(0,10);
  const view = state.view;
  const viewDate=document.getElementById('viewDate').value||today;
  // 接待人筛选下拉（每张表独立，从当前名单去重填充，保留已选值）
  const fillSolver=(selId)=>{
    const sel=document.getElementById(selId);
    const solvers=[...new Set(items.map(x=>x.assigned_solver).filter(Boolean))].sort();
    const cur=sel.value;
    sel.innerHTML='<option value="">全部接待人</option>'+solvers.map(s=>`<option ${s===cur?'selected':''}>${esc2(s)}</option>`).join('');
    if(!solvers.includes(cur)) sel.value='';
    sel.onchange=()=>renderDispatch();
    return sel.value;
  };
    const todaySolver=fillSolver('todaySolverFilter');
    const schedSolver=fillSolver('schedSolverFilter');
    // 当前排班提示：明确显示今日会按哪些接待人分配
    const activeStaff=(dData.staff&&dData.staff.today_staff&&dData.staff.today_staff.length)?dData.staff.today_staff:(dData.staff&&dData.staff.staff||[]);
    const tipEl=document.getElementById('activeStaffTip');
    if(tipEl) tipEl.innerHTML=`<span style="color:#1F4E78;font-weight:600">当前排班人员：</span>${activeStaff.map(s=>`<span style="margin-right:8px;background:#eef4fb;padding:2px 8px;border-radius:4px">${esc2(s)}</span>`).join('')}（修改排班后请点「🔄 同步刷新任务」更新已生成任务）`;
    if(view==='dispatch' || view==='dispatch_schedule'){
    if(view==='dispatch'){
      const todayList=items.filter(x=>x.source==='auto'&&x.created_date===viewDate && (!todaySolver||x.assigned_solver===todaySolver));
      document.getElementById('todayMeta').textContent=`共 ${todayList.length} 个（计划日期 ${viewDate}${todaySolver?' · '+todaySolver:''}）`;
      document.getElementById('todayBody').innerHTML=todayList.map(it=>rowHtml(it,false)).join('');
      document.querySelectorAll('#todayBody .mini').forEach(b=>b.onclick=()=>openTag(b.dataset.id));
      document.querySelectorAll('#todayBody .rep-btn').forEach(b=>b.onclick=()=>openReplace(b.dataset.id));
      document.querySelectorAll('#todayBody .nf-btn').forEach(b=>b.onclick=()=>openNoFollowup(b.dataset.id));
      document.querySelectorAll('#todayBody .mark-visit-btn').forEach(b=>b.onclick=()=>toggleVisit(b.dataset.id));
    } else {
      let schedList=items.filter(x=>x.status==='待回访'&&(x.source==='recall'||x.planned_time<=today) && (!schedSolver||x.assigned_solver===schedSolver));
      schedList.forEach(it=>{ it._prio=isPriority(it); });
      const prio=schedList.filter(x=>x._prio).sort((a,b)=>(a.last_rec_time||'').localeCompare(b.last_rec_time||''));
      const rest=schedList.filter(x=>!x._prio).sort((a,b)=>(a.planned_time||'').localeCompare(b.planned_time||''));
      schedList=prio.concat(rest);
      const prioN=prio.length;
      document.getElementById('schedMeta').textContent=`共 ${schedList.length} 个（含未接通 +N 天再次回访${schedSolver?' · '+schedSolver:''}）｜ [优先] ${prioN} 个`;
      document.getElementById('schedBody').innerHTML=schedList.map(it=>rowHtml(it,true)).join('');
      document.querySelectorAll('#schedBody .mini').forEach(b=>b.onclick=()=>openTag(b.dataset.id));
      document.querySelectorAll('#schedBody .rep-btn').forEach(b=>b.onclick=()=>openReplace(b.dataset.id));
      document.querySelectorAll('#schedBody .nf-btn').forEach(b=>b.onclick=()=>openNoFollowup(b.dataset.id));
      document.querySelectorAll('#schedBody .mark-visit-btn').forEach(b=>b.onclick=()=>toggleVisit(b.dataset.id));
    }
  }
  wireBatchBar();
  renderAll();
}

// 批量改派：勾选行 + 选择目标接待人，一次性改派
function wireBatchBar(){
  if(document.body.classList.contains('shared')) return; // 共享查看模式不显示改派工具条
  const bar=document.getElementById('batchBar');
  if(!bar) return;
  const refresh=()=>{
    const checked=[...document.querySelectorAll('.row-sel:checked')];
    document.getElementById('batchCount').textContent=checked.length;
    bar.style.display=checked.length?'flex':'none';
  };
  document.querySelectorAll('.sel-all').forEach(cb=>{
    cb.onchange=()=>{
      const t=cb.dataset.target;
      document.querySelectorAll('#'+ (t==='today'?'todayBody':'schedBody') +' .row-sel').forEach(x=>x.checked=cb.checked);
      refresh();
    };
  });
  document.querySelectorAll('.row-sel').forEach(cb=>cb.onchange=refresh);
  // 目标接待人下拉（来自今日排班人员）
  const solvers=[...new Set(dData.items.map(x=>x.assigned_solver).filter(Boolean))].sort();
  const bs=document.getElementById('batchSolver');
  const cur=bs.value;
  bs.innerHTML='<option value="">选择接待人</option>'+solvers.map(s=>`<option ${s===cur?'selected':''}>${esc2(s)}</option>`).join('');
  document.getElementById('batchClear').onclick=()=>{
    document.querySelectorAll('.row-sel').forEach(x=>x.checked=false);
    document.querySelectorAll('.sel-all').forEach(x=>x.checked=false);
    refresh();
  };
  refresh();
}

function renderDispatchOverview(){
  if(!window.__SERVE__){ const b=document.getElementById('noServeBanner'); if(b) b.style.display='block'; dTip().textContent='「排班总览」需通过 start.bat 启动本地服务后使用（内网同事访问 http://<本机内网IP>:8173）。'; return; }
  if(dData.items && dData.items.length){ initDispatchFilters(); renderAll(); }
  else { loadDispatch(); }
}

function formatCirc(it){
  const t=it.bcl||'—', op=it.bco||'—', cv=it.bcv?'在流通':'暂无电池';
  return `${esc2(t)} ${esc2(op)} ${cv}`;
}
function batStatus(it){
  const o=(it.online||'').toLowerCase();
  if(o==='online' || o==='on' || o==='在线') return '<span style="color:#1e8449;font-weight:600">在线</span>';
  if(o==='offline' || o==='off' || o==='离线') return '<span style="color:#c0392b;font-weight:600">离线</span>';
  return `<span style="color:#888">${esc2(it.online)||'未知'}</span>`;
}
// v10.28：cb_battery.last_location_time（毫秒戳）→ yyyy-MM-dd HH:mm:ss；0/无效/缺数据返回 '—'
function formatLlt(ms){
  if(!ms || Number(ms)<=0) return '—';
  const d = new Date(Number(ms));
  if(isNaN(d.getTime())) return '—';
  const p=n=>String(n).padStart(2,'0');
  return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}
function plocBadge(v){
  if(v==='本地') return '<span style="color:#1e8449;font-weight:600">本地</span>';
  if(v==='外地') return '<span style="color:#c0392b;font-weight:600">外地</span>';
  return `<span style="color:#888">${esc2(v)||'—'}</span>`;
}
// v10.26：按当前 planDate 实时算「距今未换电天数」= (planDate - 电池最后记录日) / 1day
function calcDnr(it){
  const planEl = document.getElementById('planDate');
  const planStr = (planEl && planEl.value) ? planEl.value : (function(){const d=new Date();return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');})();
  const lcts = Number(it.lcts)||0;
  if(!lcts) return '';
  const planMs = Date.parse(planStr + 'T00:00:00');
  if(!planMs || isNaN(planMs)) return '';
  const diff = Math.floor((planMs - lcts) / 86400000);
  return diff >= 0 ? diff : 0;
}
// v10.26：月均换电频次统一格式化为 "X.X次/月"
function fmtSwf(v){
  if(v===''||v===null||v===undefined) return '—';
  const n = Number(v);
  if(!isFinite(n) || n<=0) return n===0?'0次/月':'—';
  // 整数不带 .0
  const s = Number.isInteger(n) ? String(n) : n.toFixed(1);
  return s + '次/月';
}
function visitBadge(it){
  if(it.visit_result==='visited') return `<span class="badge" style="background:#e6f4ea;color:#137333;border-color:#b7e1c6">已回访</span>`+(it.visited_at?`<span style="font-size:11px;color:#888">${esc2(it.visited_at)}</span>`:'');
  return `<span class="badge" style="background:#fde0e0;color:#c0392b;border-color:#f5b5b5">未回访</span>`;
}
function rowHtml(it,sched){
  const src = it.source==='recall'?'再次回访':(it.source==='auto'?'自动分配':it.source);
  const markBtn = `<button class="btn-mini mark-visit-btn" data-id="${it.id}" style="${it.visit_result==='visited'?'color:#c0392b':''}">${it.visit_result==='visited'?'标记未回访':'标记已回访'}</button>`;
  const sel = `<td class="batch-sel"><input type="checkbox" class="row-sel" data-id="${it.id}"></td>`;
  if(sched){
    const dstLabel2 = {'on':'在押','off':'已退/已划扣'}[it.deposit_status]||it.deposit_status||'—';
    const statusLabel2 = it.agreement_status==='owe_rent'?'欠租':(it.agreement_status==='unsubscribing'?'退订中':'生效中');
    return `<tr>
      ${sel}
      <td>${it._prio?'<span class="prio-tag">[优先]</span> ':''}${it.agreement_id}</td>
      <td>${esc2(it.consumer_id||it.user_id||'-')}</td>
      <td>${esc2(it.phone)}</td>
      <td style="color:#C00000;font-weight:600">${esc2(it.cur_phone||it.phone||'')}</td>
      <td><span class="city-badge" title="${it.psrc==='ip138'?'ip138.com Web 查':'号段库自动归属'}">${esc2(fmtPcity(it))}${it.psrc==='ip138'?'<sup style="color:#888;font-size:9px">Web</sup>':''}</span></td>
      <td>${calcDnr(it)!==''?calcDnr(it):'—'}</td>
      <td>${fmtSwf(it.swf)}</td>
      <td>${it.scy!=null&&it.scy!==''?it.scy:'—'}</td>
      <td>${esc2(it.nse)||'—'}</td>
      <td>${esc2(it.assigned_solver)}</td>
      <td>${esc2(it.planned_time)}</td>
      <td>${esc2(it.pkg||'—')}</td>
      <td>${esc2(it.bsn||'—')}</td>
      <td class="lst" title="${esc2(it.lla||it.cloc)}">${esc2(it.lla||it.cloc)||'—'}</td>
      <td>${formatLlt(it.llt)}</td>
      <td>${_socCell(it)}</td>
      <td>${batStatus(it)}</td>
      <td class="lst" title="${esc2(formatCirc(it))}">${formatCirc(it)}</td>
      <td class="lst" title="${esc2(it.cabn)}">${esc2(it.cabn)||''}</td>
      <td>${esc2(src)}</td>
      <td>${esc2(it.last_rec_solver)||'-'}</td>
      <td>${esc2(it.last_rec_time)||'-'}</td>
      <td class="lst" title="${esc2(it.last_rec_detail)}">${esc2(it.last_rec_detail)||'-'}</td>
      <td>${esc2(it.agreement_type||'—')}</td>
      <td>${statusLabel2}</td>
      <td>${dstLabel2}</td>
      <td>${catBadge(it)}</td>
      <td>${visitBadge(it)}</td>
      <td><button class="mini" data-id="${it.id}">贴标签</button> <button class="rep-btn" data-id="${it.id}">替换</button> <button class="btn-ghost nf-btn" data-id="${it.id}" style="padding:3px 9px;font-size:12px">无需回访</button> ${markBtn}</td>
    </tr>`;
  }
  const dstLabel = {'on':'在押','off':'已退/已划扣'}[it.deposit_status]||it.deposit_status||'—';
  const statusLabel = it.agreement_status==='owe_rent'?'欠租':(it.agreement_status==='unsubscribing'?'退订中':'生效中');
  return `<tr>
    ${sel}
    <td>${it.agreement_id}</td>
    <td>${esc2(it.consumer_id||it.user_id||'-')}</td>
    <td>${esc2(it.phone)}</td>
    <td style="color:#C00000;font-weight:600">${esc2(it.cur_phone||it.phone||'')}</td>
    <td><span class="city-badge" title="${it.psrc==='ip138'?'ip138.com Web 查':'号段库自动归属'}">${esc2(fmtPcity(it))}${it.psrc==='ip138'?'<sup style="color:#888;font-size:9px">Web</sup>':''}</span></td>
    <td>${calcDnr(it)!==''?calcDnr(it):'—'}</td>
    <td>${fmtSwf(it.swf)}</td>
    <td>${it.scy!=null&&it.scy!==''?it.scy:'—'}</td>
    <td>${esc2(it.nse)||'—'}</td>
    <td>${esc2(it.assigned_solver)}</td>
    <td>${esc2(it.planned_time)}</td>
    <td>${esc2(it.pkg||'—')}</td>
      <td>${esc2(it.bsn||'—')}</td>
      <td class="lst" title="${esc2(it.lla||it.cloc)}">${esc2(it.lla||it.cloc)||'—'}</td>
      <td>${formatLlt(it.llt)}</td>
      <td>${_socCell(it)}</td>
      <td>${batStatus(it)}</td>
      <td class="lst" title="${esc2(formatCirc(it))}">${formatCirc(it)}</td>
      <td class="lst" title="${esc2(it.cabn)}">${esc2(it.cabn)||''}</td>
    <td>${esc2(it.last_rec_solver)||'-'}</td>
    <td>${esc2(it.last_rec_time)||'-'}</td>
    <td class="lst" title="${esc2(it.last_rec_detail)}">${esc2(it.last_rec_detail)||'-'}</td>
    <td>${esc2(it.agreement_type||'—')}</td>
    <td>${statusLabel}</td>
    <td>${dstLabel}</td>
    <td>${catBadge(it)}</td>
    <td><button class="mini" data-id="${it.id}">贴标签</button> <button class="rep-btn" data-id="${it.id}">替换</button> <button class="btn-ghost nf-btn" data-id="${it.id}" style="padding:3px 9px;font-size:12px">无需回访</button> ${markBtn}</td>
  </tr>`;
}

async function toggleVisit(id){
  const it=dData.items.find(x=>x.id===id); if(!it)return;
  const next = it.visit_result==='visited'?'pending':'visited';
  try{
    const res=await fetch('/api/mark_visit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id,result:next})});
    const j=await res.json();
    if(j.ok){ it.visit_result=j.visit_result; it.visited_at=j.visited_at; renderDispatch(); }
    else { alert('标记失败：'+(j.msg||'未知错误')); }
  }catch(e){ alert('标记失败：'+e); }
}

function genFilterMatch(it){
  const fp=document.getElementById('filterProduct').value;
  const fa=document.getElementById('filterAgent').value;
  const fc=document.getElementById('filterCity').value;
  const fz=document.getElementById('filterArea').value;
  const fs=document.getElementById('filterStreet').value;
  const fm=document.getElementById('filterCommunity').value;
  const fat=document.getElementById('filterAgreementType').value;
  const lf=document.getElementById('filterTypeLf').checked;
  const owe=document.getElementById('filterTypeOwe').checked;
  if(fp && it.product!==fp) return false;
  if(fa){
    const itemAgent = it.agent || (it.city ? it.city + '总代理' : '');
    if(itemAgent!==fa) return false;
  }
  if(fc && it.city!==fc) return false;
  if(fz && it.area!==fz) return false;
  if(fs && it.street!==fs) return false;
  if(fm && it.community!==fm) return false;
  // 电池流通季度筛选（按最后流通时间归属的季度，如 2026Q2）
  const fq=document.getElementById('filterCircQuarter').value;
  if(fq && it.cq!==fq) return false;
  if(fat && fat !== 'all'){
    const raw = it.agreement_type_raw || it.agreement_type || '';
    if(fat==='single' && raw!=='single' && raw!=='个人') return false;
    if(fat==='company' && raw!=='company' && raw!=='企业') return false;
  }
  // 用户类型筛选：按当前勾选过滤显示（并集）
  const types=[]; if(lf) types.push('lf'); if(owe) types.push('owe');
  if(types.length){
    const matchLf = lf && it.is_lf;
    const matchOwe = owe && it.is_owe;
    if(!matchLf && !matchOwe) return false;
  }
  return true;
}

function dPass(x){
  if(dState.solver && x.assigned_solver!==dState.solver) return false;
  if(dState.status && x.status!==dState.status) return false;
  if(dState.province && x.province!==dState.province) return false;
  if(dState.city && x.city!==dState.city) return false;
  if(dState.area && x.area!==dState.area) return false;
  if(dState.street && x.street!==dState.street) return false;
  if(dState.product && x.product!==dState.product) return false;
  if(dState.agrStatus && x.agreement_status!==dState.agrStatus) return false;
  if(dState.level && String(x.level)!==dState.level) return false;
  // v10.23：回访结果标签数量统计下钻筛选（按 outcome 关键字匹配 tags.outcomes）
  if(dState.outcomeFilter){
    const vr = (x.visit_result==='visited') ? 'visited' : 'pending';
    if(dState.outcomeFilter.isVis !== (vr==='visited')) return false;
    const outs = (x.tags && x.tags.outcomes) || [];
    if(!outs.some(o => (o||'').includes(dState.outcomeFilter.k))) return false;
  }
  if(dState.visitResult){
    const vr = x.visit_result || 'pending';
    if(vr!==dState.visitResult) return false;
  }
  if(dState.visitFrom || dState.visitTo){
    const va = x.visited_at;
    if(!va) return false;
    const vd = va.slice(0,10);
    if(dState.visitFrom && vd < dState.visitFrom) return false;
    if(dState.visitTo && vd > dState.visitTo) return false;
  }
  if(dState.days && dState.days.length){
    const d = x.use_days==null?null:Number(x.use_days);
    if(d==null || isNaN(d)) return false;
    const ok = dState.days.some(v=>{
      if(v==='0-30') return d>=0 && d<=30;
      if(v==='31-60') return d>=31 && d<=60;
      if(v==='61-90') return d>=61 && d<=90;
      if(v==='91-180') return d>=91 && d<=180;
      if(v==='181-365') return d>=181 && d<=365;
      if(v==='365+') return d>365;
      return false;
    });
    if(!ok) return false;
  }
  if(dState.recCategory){ const k=x.rec_category||'00'; if(k!==dState.recCategory) return false; }
  if(dState.kw){const k=dState.kw.toLowerCase(); if(!((x.phone||'').includes(k)||String(x.agreement_id).includes(k)||(x.lname||'').toLowerCase().includes(k))) return false;}
  return true;
}

const CAT_COLORS = {"01":"#e67e22","02":"#f39c12","03":"#c0392b","04":"#8e44ad","05":"#27ae60","06":"#d35400","07":"#2980b9","08":"#16a085","09":"#2c82c9","10":"#7f8c8d","00":"#95a5a6"};
function catName(k){ const c=(dData.cats||[]).find(x=>x.key===k); return c?c.name:k; }
function catBadge(it){ const k=it.rec_category||'00'; const nm=catName(k); const col=CAT_COLORS[k]||'#95a5a6'; return `<span class="cat-badge" style="background:${col}1a;color:${col};border:1px solid ${col}55">${esc2((nm||'').slice(0,14))}</span>`; }

function renderCatStat(){
  const wrap=document.getElementById('catStat'); if(!wrap) return;
  const list=dData.items; // 分类统计基于全集，点击某类才下钻表格
  const cnt={};
  list.forEach(it=>{ const k=it.rec_category||'00'; cnt[k]=(cnt[k]||0)+1; });
  const cats=[['00','其他/未匹配']].concat((dData.cats||[]).map(c=>[c.key,c.name]));
  const total=list.length;
  wrap.innerHTML='<div class="cat-stat-title">回访分类统计（点击数字下钻筛选，共 '+total+' 条）</div><div class="cat-stat-row">'
    + cats.map(([k,n])=>{
        const col=CAT_COLORS[k]||'#95a5a6'; const num=cnt[k]||0;
        const active = dState.recCategory===k ? 'active':'';
        const nameShown = (n||'').length>10 ? (n.slice(0,10)+'…') : n;
        return `<button class="cat-pill ${active}" style="--c:${col}" onclick="filterByCat('${k}')"><b>${num}</b><span>${esc2(k)} ${esc2(nameShown)}</span></button>`;
      }).join('')
    + `<button class="cat-pill ${dState.recCategory===''?'active':''}" onclick="filterByCat('')"><b>${total}</b><span>全部</span></button>`
    + '</div>';
}

// v10.23：排班总览 顶部「回访结果标签数量统计」—— 按 visit_result(已/未回访) × outcome(回访结果标签) 聚合
function renderOutcomeStat(){
  const wrap=document.getElementById('ovOutcomeStat'); if(!wrap) return;
  const list = dData.items || [];
  const visCnt = {visited:0, pending:0, other:0};
  const outCntVisited = {};   // 已回访 各 outcome 计数
  const outCntPending = {};   // 待回访 各 outcome 计数
  list.forEach(it=>{
    const vr = it.visit_result || 'pending';
    if(vr==='visited') visCnt.visited++;
    else if(vr==='pending') visCnt.pending++;
    else visCnt.other++;
    const bucket = vr==='visited' ? outCntVisited : outCntPending;
    (it.tags && it.tags.outcomes || []).forEach(o=>{ bucket[o] = (bucket[o]||0)+1; });
  });
  const visitedTotal = visCnt.visited, pendingTotal = visCnt.pending;
  const totalAll = list.length;
  const sortDesc = (o)=>Object.entries(o).sort((a,b)=>b[1]-a[1]);
  const topV = sortDesc(outCntVisited).slice(0, 12);
  const topP = sortDesc(outCntPending).slice(0, 12);
  const outcomeTotal = topV.length + topP.length;
  if(!outcomeTotal){
    wrap.innerHTML = '<div class="cat-stat-title">回访结果标签数量统计（暂无 outcome 标签数据）</div>';
    return;
  }
  const pill = (k,n,extra)=>`<button class="cat-pill ${extra||''}" style="--c:#5b8def"><b>${n}</b><span>${esc2(k)}</span></button>`;
  const head = `<div class="cat-stat-title">回访结果标签数量统计（点击下钻筛选｜已回访 <b style="color:#1a7f37">${visitedTotal}</b> · 待回访 <b style="color:#c0392b">${pendingTotal}</b> · 共 ${totalAll} 条任务）</div><div class="cat-stat-row">`;
  const groupV = topV.length ? `<div style="margin:6px 0 4px;font-size:12px;color:#1a7f37;font-weight:600">已回访 outcome</div><div class="cat-stat-row">` + topV.map(([k,n])=>pill(k,n,"vis-row")).join('') + `</div>` : '';
  const groupP = topP.length ? `<div style="margin:6px 0 4px;font-size:12px;color:#c0392b;font-weight:600">待回访 outcome</div><div class="cat-stat-row">` + topP.map(([k,n])=>pill(k,n,"pen-row")).join('') + `</div>` : '';
  wrap.innerHTML = head + groupV + groupP + '</div>';
  // 点击 outcome chip：切换 dState.outcomeFilter + renderAll()；再次点同名chip清空
  wrap.querySelectorAll('.cat-pill').forEach(b=>{
    b.onclick=()=>{
      const k = b.querySelector('span').textContent.trim();
      const isVis = b.classList.contains('vis-row');
      if(dState.outcomeFilter && dState.outcomeFilter.k===k && dState.outcomeFilter.isVis===isVis){
        dState.outcomeFilter=null;
      } else { dState.outcomeFilter={k, isVis}; }
      renderAll();
    };
  });
}
function filterByCat(k){ dState.recCategory=k; dPage=1; renderAll(); }

function renderAll(){
  dCascade();
  renderCatStat();
  if(typeof renderOutcomeStat==='function') renderOutcomeStat();
  let list=dData.items.filter(dPass);
  const pages=Math.max(1,Math.ceil(list.length/D_PAGE));
  if(dPage>pages)dPage=pages;
  const slice=list.slice((dPage-1)*D_PAGE,dPage*D_PAGE);
  document.getElementById('allBody').innerHTML=slice.map(it=>{
    const tg=[...(it.tags&&it.tags.L1||[]),...(it.tags&&it.tags.L2||[]),...(it.tags&&it.tags.L3||[]),...(it.tags&&it.tags.outcomes||[])];
    const src=it.source==='recall'?'再次回访':(it.source==='auto'?'自动分配':'手动');
    const markBtn = `<button class="btn-mini mark-visit-btn" data-id="${it.id}" style="${it.visit_result==='visited'?'color:#c0392b':''}">${it.visit_result==='visited'?'标记未回访':'标记已回访'}</button>`;
    return `<tr>
      <td>${it.agreement_id}</td><td>${esc2(it.consumer_id||it.user_id||'-')}</td><td>${esc2(it.phone)}</td>
      <td style="color:#C00000;font-weight:600">${esc2(it.cur_phone||it.phone||'')}</td>
      <td>${esc2(it.assigned_solver)}</td><td>${esc2(it.planned_time)}</td><td>${esc2(it.status)}</td>
      <td>${visitBadge(it)}</td><td>${esc2(it.visited_at||'—')}</td><td>${esc2(src)}</td>
      <td>${esc2(it.city||'-')}</td><td>${esc2(it.area||'-')}</td>      <td>${esc2(it.lname||'-')}</td>
      <td>${catBadge(it)}</td>
      <td class="lst" title="${esc2(tg.join('/'))}">${esc2(tg.join('/')||'-')}</td>
      <td><button class="mini" data-id="${it.id}">编辑</button> ${markBtn}</td>
    </tr>`;
  }).join('');
  document.getElementById('allPager').innerHTML=`共 ${list.length} 条 · 第 ${dPage}/${pages} 页 `
    +`<button ${dPage<=1?'disabled':''} onclick="dPage--;renderAll()">上页</button>`
    +`<button ${dPage>=pages?'disabled':''} onclick="dPage++;renderAll()">下页</button>`;
  document.querySelectorAll('#allBody .mini').forEach(b=>b.onclick=()=>openTag(b.dataset.id));
  document.querySelectorAll('#allBody .mark-visit-btn').forEach(b=>b.onclick=()=>toggleVisit(b.dataset.id));
}

function openTag(id){
  const it=dData.items.find(x=>x.id===id); if(!it)return;
  curItem=it;
  document.getElementById('tagUser').textContent=it.phone+' / 协议'+it.agreement_id;
  document.getElementById('tagSolver').innerHTML='<option value="">未分配</option>'+(dData.staff.staff||[]).map(x=>`<option ${x===it.assigned_solver?'selected':''}>${esc2(x)}</option>`).join('');
  document.getElementById('tagDate').value=it.planned_time||'';
  document.getElementById('tagStatus').value=it.status||'待回访';
  const tc=document.getElementById('tagCat');
  tc.innerHTML='<option value="">未分类</option>'+[['00','其他/未匹配']].concat((dData.cats||[]).map(c=>[c.key,c.name])).map(([k,n])=>`<option value="${k}">${k} · ${esc2(n)}</option>`).join('');
  tc.value=it.rec_category||'00';
  curLevel='L1';
  document.querySelectorAll('.tag-tabs button').forEach(x=>x.classList.toggle('active',x.dataset.l==='L1'));
  renderTagOptions();
  document.getElementById('tagMsg').textContent='';
  document.getElementById('tagModal').classList.add('show');
}

function renderTagOptions(){
  const tags=dData.tags||{levels:[],outcomes:[]};
  const box=document.getElementById('tagOptions');
  let opts=[], cur=[];
  if(curLevel==='OUT'){ opts=tags.outcomes||[]; cur=(curItem.tags&&curItem.tags.outcomes)||[]; }
  else { const lv=(tags.levels||[]).find(l=>l.id===curLevel); opts=lv?lv.options:[]; cur=(curItem.tags&&curItem.tags[curLevel])||[]; }
  box.innerHTML=opts.map(o=>`<label><input type="checkbox" value="${esc2(o)}" data-l="${curLevel}" ${cur.includes(o)?'checked':''}>${esc2(o)}</label>`).join('');
  box.querySelectorAll('input').forEach(i=>i.onchange=()=>{
    const L=i.dataset.l; const arr=curItem.tags[L]||(curItem.tags[L]=[]);
    if(i.checked){ if(!arr.includes(i.value))arr.push(i.value); }
    else { curItem.tags[L]=arr.filter(v=>v!==i.value); }
  });
}

document.getElementById('tagSave').onclick=async()=>{
  if(!curItem)return;
  curItem.assigned_solver=document.getElementById('tagSolver').value;
  curItem.planned_time=document.getElementById('tagDate').value;
  curItem.status=document.getElementById('tagStatus').value;
  const msg=document.getElementById('tagMsg'); msg.style.color='#888'; msg.textContent='保存中…';
  try{
    const res=await fetch('/api/assign',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:curItem.id,assigned_solver:curItem.assigned_solver,planned_time:curItem.planned_time,status:curItem.status,rec_category:document.getElementById('tagCat').value,tags:curItem.tags,tagged_by:curItem.assigned_solver})});
    const j=await res.json();
    if(j.ok){ msg.style.color='#1a7f37'; msg.textContent=j.recall_created?`已保存，并自动生成 ${j.recall_time} 再次回访任务`:'已保存'; document.getElementById('tagModal').classList.remove('show'); loadDispatch(); }
    else { msg.style.color='#c0392b'; msg.textContent='保存失败：'+(j.msg||'未知'); }
  }catch(e){ msg.style.color='#c0392b'; msg.textContent='保存失败：'+e; }
};
document.getElementById('tagCancel').onclick=()=>document.getElementById('tagModal').classList.remove('show');
document.getElementById('tagModal').onclick=(e)=>{ if(e.target.id==='tagModal')document.getElementById('tagModal').classList.remove('show'); };

// ---- 替换回访用户 ----
let repTaskId=null;
async function openReplace(taskId){
  repTaskId=taskId;
  const it=dData.items.find(x=>x.id===taskId);
  document.getElementById('repCurrent').textContent = it ? (it.agreement_id+' / '+it.phone) : (''+taskId);
  document.getElementById('repKw').value='';
  document.getElementById('replaceModal').classList.add('show');
  await loadReplaceCandidates('');
}
async function loadReplaceCandidates(kw){
  const tip=document.getElementById('repTip'); const list=document.getElementById('repList');
  list.innerHTML='<div style="padding:14px;color:#888">加载中…</div>';
  try{
    const res=await fetch('/api/replace_candidates',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task_id:repTaskId,kw})});
    const j=await res.json();
    if(!j.ok){ tip.textContent='加载失败：'+(j.msg||''); list.innerHTML=''; return; }
    tip.textContent='符合条件且未分配的候选用户（共 '+j.count+' 个）'+(j.current?('｜当前任务：'+esc2(''+j.current.phone)):'');
    if(!j.candidates.length){
      list.innerHTML='<div style="padding:14px;color:#888">没有可用的替换用户。可尝试放宽「生成名单筛选」条件，或先 [SYNC] 同步更多数据。</div>';
      return;
    }
    list.innerHTML=j.candidates.map(c=>`
      <div class="rep-item" data-aid="${c.id}">
        <div class="rep-main">
          <span class="rep-phone">${esc2(c.phone)}</span>
          <span class="rep-meta">协议 ${c.id}</span>
          ${c.is_lf?'<span class="badge lf">低频</span>':''}${c.is_owe?'<span class="badge owe">欠租</span>':''}
        </div>
        <div class="rep-sub">${esc2(c.product||'—')} ｜ ${esc2(c.city||'')}${c.area?'/'+esc2(c.area):''} ｜ 电量 ${_socCell(c)} ｜ ${c.online==='online'||c.online==='on'?'在线':'离线'}</div>
        ${c.cabn?'<div class="rep-abn">异常：'+esc2(c.cabn)+'</div>':''}
      </div>`).join('');
    list.querySelectorAll('.rep-item').forEach(el=>{ el.onclick=()=>confirmReplace(el.dataset.aid); });
  }catch(e){ tip.textContent='加载失败：'+e; }
}
async function confirmReplace(newAid){
  if(!repTaskId) return;
  if(!confirm('确认把该回访任务替换为 协议 '+newAid+' 的用户？')) return;
  try{
    const res=await fetch('/api/replace_assignment',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task_id:repTaskId,new_agreement_id:Number(newAid)})});
    const j=await res.json();
    if(j.ok){ document.getElementById('replaceModal').classList.remove('show'); loadDispatch(); }
    else { alert('替换失败：'+(j.msg||'未知错误')); }
  }catch(e){ alert('替换失败：'+e); }
}
document.getElementById('repCancel').onclick=()=>document.getElementById('replaceModal').classList.remove('show');
document.getElementById('replaceModal').onclick=(e)=>{ if(e.target.id==='replaceModal')document.getElementById('replaceModal').classList.remove('show'); };
document.getElementById('repKw').oninput=(e)=>{ loadReplaceCandidates(e.target.value); };

// ---- 标记无需回访 ----
let nfTaskId=null;
function openNoFollowup(taskId){
  nfTaskId=taskId;
  const it=dData.items.find(x=>x.id===taskId);
  document.getElementById('nfCurrent').textContent = it ? (it.agreement_id+' / '+it.phone) : (''+taskId);
  document.getElementById('nfReason').value='系统数据错误·4814电池';
  document.getElementById('nfNote').value='';
  document.getElementById('nfMsg').textContent='';
  document.getElementById('noFollowupModal').classList.add('show');
}
document.getElementById('nfCancel').onclick=()=>document.getElementById('noFollowupModal').classList.remove('show');
document.getElementById('noFollowupModal').onclick=(e)=>{ if(e.target.id==='noFollowupModal')document.getElementById('noFollowupModal').classList.remove('show'); };
document.getElementById('nfConfirm').onclick=async()=>{
  if(!nfTaskId) return;
  const reason=document.getElementById('nfReason').value;
  const note=document.getElementById('nfNote').value;
  const msg=document.getElementById('nfMsg');
  msg.style.color='#888'; msg.textContent='保存中…';
  try{
    const res=await fetch('/api/mark_no_followup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task_id:nfTaskId,reason,note})});
    const j=await res.json();
    if(j.ok){ document.getElementById('noFollowupModal').classList.remove('show'); loadDispatch(); }
    else { msg.style.color='#c0392b'; msg.textContent='标记失败：'+(j.msg||'未知错误'); }
  }catch(e){ msg.style.color='#c0392b'; msg.textContent='标记失败：'+e; }
};

// ---- 无需回访名单 Tab ----
let nfData=[];
let nfState={reason:'',kw:'',page:1};
const NF_PS=50;
async function loadNoFollowup(){
  try{
    const res=await fetch('/api/no_followup');
    const j=await res.json();
    nfData=j.items||[];
    renderNoFollowup();
  }catch(e){ document.getElementById('nfStat').textContent='加载失败：'+e; }
}
function renderNoFollowup(){
  let list=nfData;
  if(nfState.reason) list=list.filter(x=>x.reason===nfState.reason);
  if(nfState.kw){
    const k=nfState.kw.trim().toLowerCase();
    list=list.filter(x=>((x.phone||'').includes(k)||String(x.agreement_id).includes(k)));
  }
  const pages=Math.max(1,Math.ceil(list.length/NF_PS));
  if(nfState.page>pages) nfState.page=pages;
  const slice=list.slice((nfState.page-1)*NF_PS,nfState.page*NF_PS);
  document.getElementById('nfBody').innerHTML=slice.map((x,i)=>`
    <tr>
      <td>${x.agreement_id}</td><td class="ph">${esc2(x.phone||'—')}</td>
      <td>${esc2(x.agreement_type||'—')}</td>
      <td>${x.agreement_status==='owe_rent'?'欠租':(x.agreement_status==='unsubscribing'?'退订中':'生效中')}</td>
      <td>${{'on':'在押','off':'已退/已划扣'}[x.deposit_status]||x.deposit_status||'—'}</td>
      <td>${esc2(x.reason)}</td><td>${esc2(x.note||'—')}</td><td>${esc2(x.marked_by||'—')}</td><td>${esc2(x.marked_at)}</td>
      <td><button class="btn-ghost nf-del" data-idx="${i}" style="padding:3px 9px;font-size:12px;color:#c0392b;border-color:#e7b5b5">删除</button></td>
    </tr>`).join('');
  document.getElementById('nfBody').querySelectorAll('.nf-del').forEach(b=>b.onclick=async()=>{
    if(!confirm('确定从无需回访名单中删除该记录？')) return;
    try{
      const idx=(nfState.page-1)*NF_PS+parseInt(b.dataset.idx);
      const res=await fetch('/api/no_followup_remove',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({index:idx})});
      const j=await res.json();
      if(j.ok) loadNoFollowup();
      else alert('删除失败：'+(j.msg||'未知错误'));
    }catch(e){ alert('删除失败：'+e); }
  });
  const stats={}; nfData.forEach(x=>{stats[x.reason]=(stats[x.reason]||0)+1;});
  document.getElementById('nfStat').textContent=`共 ${nfData.length} 条｜按原因：${Object.entries(stats).map(([k,v])=>k+' '+v).join(' / ')}`;
  document.getElementById('nfPager').innerHTML=list.length?(`共 ${list.length} 条 · 第 ${nfState.page}/${pages}页 `
    +`<button ${nfState.page<=1?'disabled':''} onclick="nfState.page--;renderNoFollowup()">上页</button>`
    +`<button ${nfState.page>=pages?'disabled':''} onclick="nfState.page++;renderNoFollowup()">下页</button>`):'';
}
document.getElementById('nfReasonFilter').onchange=()=>{ nfState.reason=document.getElementById('nfReasonFilter').value; nfState.page=1; renderNoFollowup(); };
let nfKwT; document.getElementById('nfKw').oninput=()=>{clearTimeout(nfKwT);nfKwT=setTimeout(()=>{nfState.kw=document.getElementById('nfKw').value.trim(); nfState.page=1; renderNoFollowup();},200);};
document.getElementById('nfReset').onclick=()=>{nfState={reason:'',kw:'',page:1}; document.getElementById('nfReasonFilter').value=''; document.getElementById('nfKw').value=''; renderNoFollowup();};

['dSolver','dStatus','dProduct','dAgrStatus','dLevel','dVisitResult'].forEach(id=>{
  document.getElementById(id).onchange=()=>{
    const key=id==='dSolver'?'solver':(id==='dStatus'?'status':(id==='dProduct'?'product':(id==='dAgrStatus'?'agrStatus':(id==='dVisitResult'?'visitResult':'level'))));
    dState[key]=document.getElementById(id).value; dPage=1; renderAll();
  };
});
document.getElementById('dVisitFrom').onchange=()=>{ dState.visitFrom=document.getElementById('dVisitFrom').value; dPage=1; renderAll(); };
document.getElementById('dVisitTo').onchange=()=>{ dState.visitTo=document.getElementById('dVisitTo').value; dPage=1; renderAll(); };
['dProvince','dCity','dArea','dStreet'].forEach(id=>{
  document.getElementById(id).onchange=()=>{
    const key=id==='dProvince'?'province':(id==='dCity'?'city':(id==='dArea'?'area':'street'));
    dState[key]=document.getElementById(id).value;
    if(key==='province'){ dState.city=''; dState.area=''; dState.street=''; }
    if(key==='city'){ dState.area=''; dState.street=''; }
    if(key==='area'){ dState.street=''; }
    dPage=1; renderAll();
  };
});
let dKwT; document.getElementById('dKw').oninput=()=>{clearTimeout(dKwT);dKwT=setTimeout(()=>{dState.kw=document.getElementById('dKw').value.trim(); dPage=1; renderAll();},200);};
document.getElementById('dReset').onclick=()=>{
  dState={solver:'',status:'',province:'',city:'',area:'',street:'',product:'',agrStatus:'',level:'',visitResult:'',visitFrom:'',visitTo:'',days:[],kw:'',outcomeFilter:null};
  document.getElementById('dSolver').value=''; document.getElementById('dStatus').value='';
  document.getElementById('dProvince').value=''; document.getElementById('dCity').value=''; document.getElementById('dArea').value=''; document.getElementById('dStreet').value='';
  document.getElementById('dProduct').value=''; document.getElementById('dAgrStatus').value=''; document.getElementById('dLevel').value='';
  document.getElementById('dVisitResult').value=''; document.getElementById('dVisitFrom').value=''; document.getElementById('dVisitTo').value='';
  document.getElementById('dKw').value='';
  const box=document.getElementById('dDays'); if(box) box.querySelectorAll('input').forEach(cb=>cb.checked=false);
  const trig=document.getElementById('dDaysTrigger'); if(trig) trig.textContent='全部';
  dPage=1; renderAll();
};

document.getElementById('clearAssignmentsBtn').onclick=async()=>{
  if(!confirm('确定清空当前全部排班数据吗？此操作会删除「今日待分配」「回访调度」「排班总览」中的所有任务，且不可恢复。'))return;
  try{
    const res=await fetch('/api/clear_assignments',{method:'POST'});
    const j=await res.json();
    alert(j.ok?'当前排班数据已清空。':('清空失败：'+(j.msg||'未知错误')));
    if(j.ok) loadDispatch();
  }catch(e){ alert('清空失败：'+e); }
};

document.getElementById('aiClassifyBtn').onclick=async()=>{
  const tip=document.getElementById('aiClassifyTip'); tip.style.color='#888'; tip.textContent='AI 自动分类中…';
  try{
    const res=await fetch('/api/ai_classify',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:'auto',use_llm:true})});
    const j=await res.json();
    if(j.ok){ tip.style.color='#1a7f37'; tip.textContent='已自动分类 '+j.updated+' 条（共 '+j.total+' 条）'; renderAll(); }
    else { tip.style.color='#c0392b'; tip.textContent='分类失败：'+(j.msg||'未知'); }
  }catch(e){ tip.style.color='#c0392b'; tip.textContent='分类失败：'+e; }
};

document.getElementById('clearTodayBtn').onclick=async()=>{
  if(!confirm('确定清空今日（'+todayStr()+'）的排班总览吗？仅移除今日的自动/回访任务，保留其它日期与手动排班。'))return;
  try{
    const res=await fetch('/api/clear_assignments',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({date:todayStr()})});
    const j=await res.json();
    alert(j.ok?(j.msg||'今日排班已清空。'):('清空失败：'+(j.msg||'未知错误')));
    if(j.ok) loadDispatch();
  }catch(e){ alert('清空失败：'+e); }
};

function collectStaffConfig(){
  const staff=(dData.staff&&dData.staff.staff)||[];
  const today_staff=[...document.querySelectorAll('#todayStaffWrap input[type=checkbox]:checked')].map(i=>i.value);
  const quotas={};
  document.querySelectorAll('#todayStaffWrap .qinput').forEach(i=>{
    if(i.style.display==='none') return;
    const v=i.value.trim();
    if(v!=='') quotas[i.dataset.name]=parseInt(v,10);
  });
  const gf={};
  const fp=document.getElementById('filterProduct').value; if(fp) gf.product=fp;
  const fa=document.getElementById('filterAgent').value; if(fa) gf.agent=fa;
  const fc=document.getElementById('filterCity').value; if(fc) gf.city=fc;
  const fz=document.getElementById('filterArea').value; if(fz) gf.area=fz;
  const fs=document.getElementById('filterStreet').value; if(fs) gf.street=fs;
  const fm=document.getElementById('filterCommunity').value; if(fm) gf.community=fm;
  gf.agreement_type = document.getElementById('filterAgreementType').value || '';
  return {staff, today_staff, quotas, gen_filter:gf, daily_quota:document.getElementById('quotaDefault').value, recall_days:document.getElementById('recallInput').value, recall_cooldown_days:document.getElementById('recallCooldown').value};
}

document.getElementById('saveStaffBtn').onclick=async()=>{
  const body=collectStaffConfig();
  try{
    const res=await fetch('/api/staff',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j=await res.json();
    if(!j.ok){ dTip().textContent='保存失败。'; return; }
    dTip().textContent='配置已保存。';
    const pd=document.getElementById('planDate').value||new Date().toISOString().slice(0,10);
    const hasAuto=dData.items&&dData.items.some(x=>x.source==='auto'&&x.created_date===pd);
    if(hasAuto && confirm('当天已有自动分配任务，是否立即按新排班重新分配？')){
      // v10.19：使用「同步刷新任务」语义（仅重平衡待回访，保留已回访），不再依赖已删除的 redispatchBtn
      const r2=await fetch('/api/redispatch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({gen_date:pd, mode:'sync'})});
      const j2=await r2.json();
      if(j2.ok){ dTip().textContent='配置已保存，已按新排班同步刷新。'; }
      else { dTip().textContent='配置已保存，但同步刷新失败：'+(j2.msg||'未知错误'); }
      loadDispatch();
    } else {
      loadDispatch();
    }
  }catch(e){ dTip().textContent='保存失败：'+e; }
};

if(document.getElementById('updateBtn')){
  document.getElementById('updateBtn').onclick=async()=>{
    const url=(document.getElementById('updateUrl').value||'').trim();
    const tip=document.getElementById('updateTip');
    if(!url){ tip.textContent='请先粘贴更新链接。'; return; }
    tip.textContent='正在下载并应用更新，请稍候（约 1~3 分钟）…';
    try{
      const res=await fetch('/api/self_update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url})});
      const j=await res.json();
      if(j.ok){
        tip.textContent=(j.msg||'更新完成')+' 页面将在几秒后自动刷新…';
        // 新实例会在同一端口重启，稍等后刷新即可看到新功能
        setTimeout(()=>location.reload(), 5000);
      } else {
        tip.textContent='更新失败：'+(j.msg||'未知错误');
      }
    }catch(e){ tip.textContent='更新请求失败：'+e; }
  };
}
// v10.28.55：更新条可折叠（默认展开；点"▾ 收起"折叠成 1 行摘要）
if(document.getElementById('updateFoldBtn')){
  const _ufb=document.getElementById('updateFoldBtn');
  const _ub=document.getElementById('updateBanner');
  _ufb.onclick = ()=>{
    if(_ub.classList.contains('collapsed')){
      _ub.classList.remove('collapsed');
      _ufb.textContent='▾ 收起';
    } else {
      _ub.classList.add('collapsed');
      _ufb.textContent='▴ 展开';
    }
  };
}

// 生成回访名单（主按钮 + 追加排班）：增量模式，保留原名单，仅补未分配协议
async function genDispatchAppend(){
  const body=collectStaffConfig();
  const pd=document.getElementById('planDate').value||new Date().toISOString().slice(0,10);
  dTip().textContent=`正在保存配置并生成分配名单（计划日期 ${pd}）...`;
  try{
    const r1=await fetch('/api/staff',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j1=await r1.json();
    if(!j1.ok){ dTip().textContent='配置保存失败，未执行分配。'; return; }
    const r2=await fetch('/api/redispatch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({gen_date:pd, mode:'append'})});
    const j2=await r2.json();
    dTip().textContent=j2.ok?`分配名单已生成（计划日期 ${pd}），原名单不变。`:('生成失败：'+(j2.msg||'未知错误'));
    if(j2.ok)loadDispatch();
  }catch(e){ dTip().textContent='生成失败：'+e; }
}
document.getElementById('btnGenMain').onclick=async()=>{
  if(!confirm('确定按当前「排班人员 + 回访数量 + 电池产品」生成回访名单吗？\n（保留原有名单不变，仅补充新选人员对应的未回访协议）'))return;
  genDispatchAppend();
};
document.getElementById('btnAppend').onclick=async()=>{
  // v10.20：开 Modal 选人 + 接待数量（避免给已有人员再补一份导致数量翻倍）
  openAppendModal();
};

// v10.20：追加排班 Modal（只为本次勾选的人员分配，原名单完全不动）
let _appendModalOpen = false;
function openAppendModal(){
  if(_appendModalOpen) return;
  const staffList = (dData.staff && dData.staff.staff) || [];
  const defaultQuota = (dData.staff && dData.staff.daily_quota) || 30;
  const cfg = dData.staff||{};
  const todayStaff = cfg.today_staff || [];
  const quotas = cfg.quotas || {};
  const box = document.getElementById('appendStaffList');
  if(!box){
    alert('追加排班弹窗未挂载，请刷新页面');
    return;
  }
  box.innerHTML = staffList.map(name=>{
    const checked = todayStaff.indexOf(name)>=0 ? '' : '';  // 默认全不勾（由用户决定追加谁）
    const q = quotas[name] || defaultQuota;
    return `<label class="staff-card"><input type="checkbox" value="${esc2(name)}"><span class="name">${esc2(name)}</span><input type="number" min="1" class="qinput" data-name="${esc2(name)}" value="${q}" placeholder="默认${defaultQuota}"></label>`;
  }).join('');
  // 复选 ↔ 数量输入显示联动（数量框在勾选后才显示，原逻辑已存在）
  box.querySelectorAll('.staff-card').forEach(card=>{
    const cb=card.querySelector('input[type=checkbox]');
    const qin=card.querySelector('.qinput');
    if(qin){ qin.style.display='none'; card.classList.add('disabled'); }
    cb.onchange=()=>{
      if(cb.checked){ card.classList.remove('disabled'); qin.style.display=''; }
      else { card.classList.add('disabled'); qin.style.display='none'; }
    };
  });
  document.getElementById('appendModal').classList.add('show');
  document.getElementById('appendModalMsg').textContent='';
  _appendModalOpen = true;
}
function closeAppendModal(){
  document.getElementById('appendModal').classList.remove('show');
  _appendModalOpen = false;
}
if(document.getElementById('appendModalClose')){
  document.getElementById('appendModalClose').onclick=closeAppendModal;
}
if(document.getElementById('appendModal')){
  document.getElementById('appendModal').onclick=(e)=>{
    if(e.target.id==='appendModal') closeAppendModal();
  };
}
if(document.getElementById('appendConfirm')){
  document.getElementById('appendConfirm').onclick=submitAppend;
}
async function submitAppend(){
  const checks=[...document.querySelectorAll('#appendStaffList input[type=checkbox]:checked')];
  if(checks.length===0){
    document.getElementById('appendModalMsg').textContent='请至少勾选一位接待人';
    return;
  }
  const extra={};
  const detail=[];
  for(const cb of checks){
    const name=cb.value;
    const safeName = esc2(name).replace(/"/g,'&quot;');
    const qinput=document.querySelector(`#appendStaffList .qinput[data-name="${safeName}"]`);
    let q = parseInt(qinput && qinput.value || 0, 10);
    if(!q || q<1) q=parseInt(document.getElementById('quotaDefault').value||'30', 10) || 30;
    extra[name]=q;
    detail.push(`${name}×${q}`);
  }
  const pd=document.getElementById('planDate').value||new Date().toISOString().slice(0,10);
  document.getElementById('appendModalMsg').textContent=`正在追加（${detail.join('，')}）...`;
  try{
    const res=await fetch('/api/redispatch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({gen_date:pd, mode:'extra', extra_solvers:extra})});
    const j=await res.json();
    if(j.ok){
      document.getElementById('appendModalMsg').textContent=`追加完成：本次新增 ${j.extra_count||0} 位人员的待回访任务，原名单保留。`;
      closeAppendModal();
      loadDispatch();
    } else {
      document.getElementById('appendModalMsg').textContent='追加失败：'+(j.msg||'未知错误');
    }
  }catch(e){ document.getElementById('appendModalMsg').textContent='请求失败：'+e; }
}

// 清空重生成（覆盖模式）：清空当日全部名单后按当前配置重来
// v10.28.55：1) 先显示"将清空 N 条待回访"二次确认；2) 提供「恢复上一次的名单」按钮兜底
async function clearRegenWillClear(pd){
    // 粗略估算：当前 + 未来日期全部「待回访」任务数（保留昨日/上周的不动）
    const snap = (dData && dData.today) || {};
    const items = (snap.items) || [];
    const cnt = items.filter(x => (x.created_date===pd && x.status==='待回访' && !x.manual)).length;
    return cnt;
}
document.getElementById('btnClearRegen').onclick=async()=>{
  const body=collectStaffConfig();
  const pd=document.getElementById('planDate').value||new Date().toISOString().slice(0,10);
  // v10.28.55：先列出本次要清的任务数 + 给出「恢复名单」兜底
  let willRemove = 0;
  try{ willRemove = await clearRegenWillClear(pd); }catch(_){}
  let backups = [];
  try{ const r = await fetch('/api/list_backups'); const j = await r.json(); backups = (j && j.backups) || []; }catch(_){}
  const restoreHtml = backups.length
    ? `<div style="margin-top:10px;padding:8px 10px;background:#fffbeb;border:1px solid #fde68a;border-radius:6px;font-size:12px">
         ⚠ 误清后可用此按钮回滚（最近一份 ${backups[0]}）：
         <button id="restoreLastBtn" class="btn-ghost" style="margin-left:6px;color:#b45309">↩ 恢复上一次的名单</button>
       </div>`
    : '';
  const msg = `确定要「清空并重新生成」「${pd}」的分配名单吗？\n\n`
            + `本次将清空：${willRemove} 条「待回访+非手动」任务（其他日期的「待回访」不动）。\n`
            + `系统已自动备份当前名单到「assignments.bak.<时间>.json」，如误操作可一键回滚。`;
  if(!confirm(msg))return;
  dTip().textContent=`正在保存配置并清空重生成（计划日期 ${pd}）...`;
  try{
    const r1=await fetch('/api/staff',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j1=await r1.json();
    if(!j1.ok){ dTip().textContent='配置保存失败，未执行分配。'; return; }
    const r2=await fetch('/api/redispatch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({gen_date:pd, mode:'force'})});
    const j2=await r2.json();
    dTip().textContent=j2.ok?`分配名单已清空重生成（计划日期 ${pd}），共清空 ${willRemove} 条。`:('分配失败：'+(j2.msg||'未知错误'));
    if(j2.ok)loadDispatch();
  }catch(e){ dTip().textContent='分配失败：'+e; }
};
// v10.28.55：恢复上一次的名单（强制二次确认，避免误操作）
document.addEventListener('click', async function(ev){
  if(ev.target && ev.target.id==='restoreLastBtn'){
    if(!confirm('确定恢复「上一次清空前」的名单吗？\n当前在屏名单会被覆盖（系统已自动备份当前名单）。'))return;
    try{
      const r = await fetch('/api/restore_assignments',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});
      const j = await r.json();
      dTip().textContent = j.ok ? `已恢复 ${j.backup}` : ('恢复失败：'+(j.msg||'未知错误'));
      if(j.ok)loadDispatch();
    }catch(e){ dTip().textContent='恢复失败：'+e; }
  }
});

// 同步刷新任务：按当前配置重新平衡已生成任务的归属/配额，保留已回访记录
document.getElementById('btnSyncTasks').onclick=async()=>{
  const pd=document.getElementById('planDate').value||new Date().toISOString().slice(0,10);
  if(!confirm(`确定按当前配置「同步刷新」「${pd}」的已生成任务吗？\n（重新平衡待回访任务的归属与配额，已回访/已作废记录保留）`))return;
  dTip().textContent='正在同步刷新任务...';
  try{
    const res=await fetch('/api/redispatch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({gen_date:pd, mode:'sync'})});
    const j=await res.json();
    dTip().textContent=j.ok?'已按当前配置同步刷新任务。':('同步刷新失败：'+(j.msg||'未知错误'));
    if(j.ok)loadDispatch();
  }catch(e){ dTip().textContent='同步刷新失败：'+e; }
};

// 批量改派：将勾选的【待回访】任务改派给指定接待人（已回访/已作废的不动）
document.getElementById('batchReassignBtn').onclick=async()=>{
  const ids=[...document.querySelectorAll('.row-sel:checked')].map(cb=>cb.dataset.id);
  const solver=document.getElementById('batchSolver').value;
  const tip=document.getElementById('batchTip');
  if(!ids.length){ tip.textContent='请先勾选要改派的任务'; return; }
  if(!solver){ tip.textContent='请选择改派目标接待人'; return; }
  if(!confirm(`确定将选中的 ${ids.length} 条【待回访】任务改派给「${solver}」吗？\n（已回访/已作废的任务不会被改动）`))return;
  try{
    const res=await fetch('/api/reassign',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ids,solver,only_pending:true})});
    const j=await res.json();
    if(j.ok){ tip.textContent=`已改派 ${j.updated} 条（跳过 ${j.skipped||0} 条非待回访）`; loadDispatch(); }
    else { tip.textContent='改派失败：'+(j.msg||'未知错误'); }
  }catch(e){ tip.textContent='改派失败：'+e; }
};

// 作废某接待人名下所有待回访任务（释放回待分配池，下次追加排班可重新分配）
document.getElementById('cancelSolverBtn').onclick=async()=>{
  const solver=document.getElementById('cancelSolver').value;
  if(!solver){ alert('请先选择要作废的接待人'); return; }
  if(!confirm(`确定作废「${solver}」名下所有【待回访】任务吗？\n这些协议将释放回待低频用户库，下次「➕追加排班」可被重新分配。\n（已回访/已作废的任务不受影响）`))return;
  try{
    const res=await fetch('/api/cancel_solver',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({solver})});
    const j=await res.json();
    if(j.ok){ alert(j.msg||`已作废 ${j.removed} 条`); loadDispatch(); }
    else { alert('作废失败：'+(j.msg||'未知错误')); }
  }catch(e){ alert('作废失败：'+e); }
};

// ===== v10.28.55 同事访问链接常驻条（顶部，避免发错 localhost 给同事） =====
function refreshLanAccessBanner(){
  if(!window.__SERVE__) return; // 仅本地服务模式下显示（直接双击打开 HTML 文件时不显示）
  try{
    // v10.28.55：把当前 URL 的 token 拼到 /api/lan_info，确保 me_token 不为空
    var myTk = new URLSearchParams(location.search).get('token') || '';
    var tkQ = myTk ? ('?token='+encodeURIComponent(myTk)) : '';
    fetch('/api/lan_info'+tkQ).then(function(r){return r.json();}).then(function(j){
      var ips=(j.ips&&j.ips.length)?j.ips:[j.ip];
      // v10.28.55：URL 拼 me_token，否则同事点开会落到登录页
      var meTk = j.me_token || myTk || '';
      var urls=ips.map(function(ip){
        var u='http://'+ip+':'+j.port+'/';
        return meTk ? u+'?token='+encodeURIComponent(meTk) : u;
      });
      var banner=document.getElementById('lanAccessBanner');
      var span=document.getElementById('lanAccessUrls');
      if(!banner||!span) return;
      span.textContent=urls.join('  或  ');
      banner.style.display='block';
      var tip=document.getElementById('lanAccessTip');
      if(tip) tip.textContent = meTk
        ? ((j.firewall_ok===false)
            ? '⚠ 防火墙未放行，同事可能打不开（请先双击 open_firewall.bat 自动放行）。链接已带 token，可直接打开'
            : '链接已带登录 token，可直接发给同网段同事/手机（哪个能打开用哪个）')
        : '⚠ 当前未登录（me_token 为空），同事打开会落到登录页。请先用账号密码登录本机看板后再点此链接';
      var copyBtn=document.getElementById('copyLanLinkBtn');
      if(copyBtn) copyBtn.onclick=function(){
        try{ navigator.clipboard.writeText(urls[0]); }catch(e){}
        copyBtn.textContent='已复制'; setTimeout(function(){copyBtn.textContent='复制';},1500);
      };
    }).catch(function(){});
  }catch(e){}
}
refreshLanAccessBanner();

// ===== 生成回访链接（同网络访问） =====
document.getElementById('genLinkBtn').onclick=async()=>{
  try{
    // v10.28.55：把当前 URL 的 token 拼到请求，确保 me_token 能正确拿到
    var myTk = new URLSearchParams(location.search).get('token') || '';
    var tkQ = myTk ? ('?token='+encodeURIComponent(myTk)) : '';
    const res=await fetch('/api/lan_info'+tkQ);
    const j=await res.json();
    const mods=[...document.querySelectorAll('#linkMods input:checked')].map(c=>c.value);
    if(!mods.length){ alert('请至少勾选一个对外可见模块'); return; }
    const first=mods[0];
    // v10.28.55：必须拼上 token，否则同事点开会落到登录页
    let meTk = (j && j.me_token) || myTk || '';
    if(!meTk){
      try{
        var meTkQ = myTk ? ('?token='+encodeURIComponent(myTk)) : '';
        const r2 = await fetch('/api/me_token'+meTkQ);
        const j2 = await r2.json();
        if(j2 && j2.ok && j2.token){ meTk = j2.token; }
      }catch(_){}
    }
    const q=`tab=${first}&mods=${encodeURIComponent(mods.join(','))}`;
    const tk = meTk ? `&token=${encodeURIComponent(meTk)}` : '';
    const ips=(j.ips&&j.ips.length)?j.ips:[j.ip];
    const urls=ips.map(ip=>`http://${ip}:${j.port}/?${q}${tk}`);
    document.getElementById('linkInput').value=urls[0];
    // v10.28.55：未登录时给明确提示，避免发给同事后对方被卡登录页
    const noLoginWarn = meTk ? '' :
      `<div style="color:#b91c1c;background:#fef2f2;border:1px solid #fecaca;padding:8px 10px;border-radius:6px;margin-bottom:8px">`
      + `⚠ 当前未登录（无法拿到 me_token），同事点开链接会落到登录页。请先在本机用账号密码登录后，再点此按钮。</div>`;
    // v10.28.55：防火墙未放行时给出明确告警，避免同事反复打不开却无从排查
    const fwWarn = (j.firewall_ok===false)
      ? `<div style="color:#b91c1c;background:#fef2f2;border:1px solid #fecaca;padding:8px 10px;border-radius:6px;margin-bottom:8px">`
        + `⚠ 检测到本机防火墙尚未放行 <b>${j.port}</b> 端口，同事很可能打不开。请<b>右键 open_firewall.bat → 以管理员身份运行</b>一次（规则会一直保留，之后双击 start.bat 即可）。</div>`
      : '';
    const label=ips.length>1?'有多个候选局域网地址，发给同事后「哪个能打开就用哪个」：<br>':'本机内网地址：<br>';
    document.getElementById('lanIpHint').innerHTML=noLoginWarn+fwWarn+label+urls.map(u=>`<span style="font-family:monospace;word-break:break-all">${u}</span>`).join('<br>');
    document.getElementById('linkModal').classList.add('show');
    document.getElementById('linkInput').focus();
  }catch(e){ alert('获取回访链接失败：'+e+'（请确认通过本地服务地址访问，而非直接打开文件）'); }
};
document.getElementById('copyLinkBtn').onclick=async()=>{
  const inp=document.getElementById('linkInput'); inp.select();
  try{ await navigator.clipboard.writeText(inp.value); }
  catch(e){ try{ document.execCommand('copy'); }catch(_){} }
  const btn=document.getElementById('copyLinkBtn'); btn.textContent='已复制'; setTimeout(()=>btn.textContent='复制',1500);
};
// v10.28.55：测试链接 —— 新窗口打开预览验证（手机端可用「在浏览器中打开」扫码）
document.getElementById('testLinkBtn').onclick=()=>{
  const inp=document.getElementById('linkInput');
  if(!inp.value || inp.value==='—'){ alert('请先生成回访链接'); return; }
  window.open(inp.value, '_blank', 'noopener');
};
document.getElementById('linkModalClose').onclick=()=>document.getElementById('linkModal').classList.remove('show');
document.getElementById('linkModal').onclick=(e)=>{ if(e.target.id==='linkModal')document.getElementById('linkModal').classList.remove('show'); };

// ===== v10.28.55 人员权限弹窗（账号密码登录 + 角色 + 手机白名单 + 模块） =====
const PERM_MODULES = [
  {v:'dispatch', l:'回访排班'}, {v:'dispatch_schedule', l:'回访调度'},
  {v:'dispatch_overview', l:'排班总览'}, {v:'dispatch_history', l:'历史排班'},
  {v:'all', l:'全部活跃协议'}, {v:'owe', l:'欠租催收'}, {v:'lf', l:'低频用户'},
  {v:'reception', l:'回访看板'},
];
// 角色预设：选角色即一键勾好对应模块，仍可手动微调
const ROLE_PRESETS = {
  '管理员':   ['all'],
  '客服主管': ['reception','dispatch','dispatch_schedule','dispatch_overview'],
  '客服':     ['reception'],
  '财务':     ['dispatch_overview','dispatch_history'],
  '排班专员': ['dispatch','dispatch_schedule','dispatch_overview','dispatch_history'],
};
let permData = [];
async function openPermModal(){
  // v10.28.55：从 /api/auth 拉取账号权限（含 username / modules / scope / phone_allow）
  try{
    const j=await fetch('/api/auth').then(r=>r.json());
    const users=(j&&Array.isArray(j.users))?j.users:[];
    permData=JSON.parse(JSON.stringify(users));
  }catch(e){ permData=[]; }
  renderPermList();
  document.getElementById('permMsg').textContent='';
  document.getElementById('permModal').classList.add('show');
}
function renderPermList(){
  const wrap = document.getElementById('permList');
  if(!permData.length){ wrap.innerHTML='<div style="color:#999;padding:10px;font-size:13px">暂无账号，请在上方填写账号/显示名/密码后点「添加账号」。</div>'; return; }
  wrap.innerHTML = permData.map((p,i)=>{
    const scopeTxt = Array.isArray(p.scope) ? p.scope.join(',') : (p.scope||'全部');
    const phTxt = Array.isArray(p.phone_allow) ? p.phone_allow.join(',') : (p.phone_allow||'全部');
    const roleOpts = Object.keys(ROLE_PRESETS).map(r=>`<option value="${r}" ${(p.role||'')===r?'selected':''}>${r}</option>`).join('');
    return `
    <div class="perm-row" style="border-bottom:1px solid var(--line);padding:10px 4px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
        <b style="font-size:14px">${esc2(p.username||'')}</b>
        <button class="btn-ghost perm-del" data-i="${i}" style="padding:3px 8px;font-size:12px">删除</button>
      </div>
      <div style="font-size:12px;color:#444;margin-bottom:6px">显示名：<b>${esc2(p.name||'—')}</b>${p.token?` ｜ token：<code style="background:#eef4fb">${esc2(p.token)}</code>`:''}</div>
      <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:6px">
        <span style="font-size:12px;color:#666">角色：
          <select class="perm-role" data-i="${i}" style="padding:3px 6px;border:1px solid var(--line);border-radius:6px;font-size:12px">
            <option value="">自定义</option>${roleOpts}
          </select>
        </span>
        <label style="font-size:13px;color:#333"><input type="checkbox" class="perm-sync" data-i="${i}" ${p.can_sync?'checked':''}> 可同步数据库</label>
      </div>
      <div class="perm-mods" style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:6px">
        ${PERM_MODULES.map(m=>`<label class="staff-card" style="cursor:pointer"><input type="checkbox" class="perm-mod" data-i="${i}" value="${m.v}" ${(p.modules||[]).includes(m.v)?'checked':''}><span class="name">${m.l}</span></label>`).join('')}
      </div>
      <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">
        <span style="font-size:12px;color:#666">数据范围：<input class="perm-scope" data-i="${i}" value="${esc2(scopeTxt)}" placeholder="全部 或 城市关键词,逗号分隔" style="padding:3px 6px;border:1px solid var(--line);border-radius:6px;font-size:12px;width:180px"></span>
        <span style="font-size:12px;color:#666">手机白名单：<input class="perm-phone" data-i="${i}" value="${esc2(phTxt)}" placeholder="全部 或 手机号前缀,逗号分隔" style="padding:3px 6px;border:1px solid var(--line);border-radius:6px;font-size:12px;width:200px"></span>
        <button class="btn-ghost perm-copy" data-i="${i}" style="padding:3px 10px;font-size:12px">复制免登录链接</button>
      </div>
    </div>`;
  }).join('');
  wrap.querySelectorAll('.perm-del').forEach(b=>b.onclick=()=>{ permData.splice(parseInt(b.dataset.i),1); renderPermList(); });
  wrap.querySelectorAll('.perm-mod').forEach(c=>c.onchange=()=>{ const i=+c.dataset.i; if(c.checked){ if(!permData[i].modules.includes(c.value)) permData[i].modules.push(c.value); } else { permData[i].modules=permData[i].modules.filter(m=>m!==c.value); } });
  wrap.querySelectorAll('.perm-sync').forEach(c=>c.onchange=()=>{ permData[+c.dataset.i].can_sync = c.checked; });
  wrap.querySelectorAll('.perm-role').forEach(s=>s.onchange=()=>{ const i=+s.dataset.i; const r=s.value; if(r&&ROLE_PRESETS[r]){ permData[i].role=r; permData[i].modules=ROLE_PRESETS[r].slice(); renderPermList(); } else { permData[i].role=''; } });
  wrap.querySelectorAll('.perm-scope').forEach(c=>c.onchange=()=>{ const i=+c.dataset.i; const v=c.value.trim(); permData[i].scope = v ? v.split(',').map(s=>s.trim()).filter(Boolean) : '全部'; });
  wrap.querySelectorAll('.perm-phone').forEach(c=>c.onchange=()=>{ const i=+c.dataset.i; const v=c.value.trim(); permData[i].phone_allow = v ? v.split(',').map(s=>s.trim()).filter(Boolean) : '全部'; });
  wrap.querySelectorAll('.perm-copy').forEach(b=>b.onclick=async()=>{ await copyPermLink(parseInt(b.dataset.i)); });
}
async function copyPermLink(idx){
  const p=permData[idx]; if(!p) return;
  try{
    const res=await fetch('/api/lan_info'); const j=await res.json();
    const ips=(j.ips&&j.ips.length)?j.ips:[j.ip];
    const urls=ips.map(ip=>`http://${ip}:${j.port}/?token=${encodeURIComponent(p.token||'')}`);
    try{ await navigator.clipboard.writeText(urls[0]); }catch(e){ try{ const t=document.createElement('textarea');t.value=urls[0];document.body.appendChild(t);t.select();document.execCommand('copy');document.body.removeChild(t);}catch(_){} }
    const label=ips.length>1?`已复制 ${p.name} 的免登录链接（多个候选，哪个能打开用哪个）：<br>`:`已复制 ${p.name} 的免登录链接：<br>`;
    document.getElementById('permMsg').innerHTML=label+urls.map(u=>`<span style="font-family:monospace;word-break:break-all">${u}</span>`).join('<br>')+'<br><span style="color:#888">（对方用此链接免登录直接进；也可让其用账号密码登录）</span>';
  }catch(e){ document.getElementById('permMsg').textContent='生成链接失败：'+e+'（请通过本地服务地址访问）'; }
}
document.getElementById('permBtn').onclick=openPermModal;
document.getElementById('permModalClose').onclick=()=>document.getElementById('permModal').classList.remove('show');
document.getElementById('permModal').onclick=(e)=>{ if(e.target.id==='permModal')document.getElementById('permModal').classList.remove('show'); };
function genToken(){
  const cs='ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789';
  let s=''; for(let i=0;i<16;i++) s+=cs[Math.floor(Math.random()*cs.length)];
  return 'lf_'+s;
}
document.getElementById('permAddBtn').onclick=()=>{
  const uInp=document.getElementById('permUsername'); const u=uInp.value.trim();
  const nInp=document.getElementById('permName'); const n=nInp.value.trim();
  const pInp=document.getElementById('permPw'); const pw=pInp.value;
  if(!u){ document.getElementById('permMsg').textContent='请填写登录账号'; return; }
  if(!pw){ document.getElementById('permMsg').textContent='请填写登录密码（将哈希存储，不存明文）'; return; }
  if(permData.some(p=>p.username===u)){ document.getElementById('permMsg').textContent='该账号已存在'; return; }
  permData.push({username:u, name:n||u, role:'客服', password:pw, token:genToken(),
                 modules:ROLE_PRESETS['客服'].slice(), can_sync:false, scope:'全部', phone_allow:'全部'});
  uInp.value=''; nInp.value=''; pInp.value=''; renderPermList();
};
document.getElementById('permSaveBtn').onclick=async()=>{
  try{
    // 账号密码体系：把每个账号的 username/name/role/password/modules/phone_allow 一并提交
    const res=await fetch('/api/staff',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({users:permData.map(p=>({username:p.username,name:p.name,role:p.role,password:p.password||'',
        token:p.token,modules:p.modules,can_sync:p.can_sync,scope:p.scope,phone_allow:p.phone_allow}))})});
    const j=await res.json();
    if(j.ok){ document.getElementById('permMsg').textContent='账号权限已保存（密码已哈希存储）。'; }
    else document.getElementById('permMsg').textContent='保存失败。';
  }catch(e){ document.getElementById('permMsg').textContent='保存失败：'+e; }
};

// ===== 人员管理弹窗 =====
let modalStaffList=[];
function openStaffModal(){
  modalStaffList=[...((dData.staff&&dData.staff.staff)||[])];
  renderStaffList();
  document.getElementById('staffModal').classList.add('show');
  document.getElementById('staffModalMsg').textContent='';
}
function renderStaffList(){
  const tbody=document.getElementById('staffListBody');
  if(!modalStaffList.length){ tbody.innerHTML='<tr><td style="color:#999;padding:8px">暂无人员，请添加</td></tr>'; return; }
  tbody.innerHTML=modalStaffList.map((name,idx)=>`<tr><td>${esc2(name)}</td><td style="text-align:right"><button class="btn-ghost" data-idx="${idx}" style="padding:3px 8px;font-size:12px">删除</button></td></tr>`).join('');
  tbody.querySelectorAll('button').forEach(b=>b.onclick=()=>{ modalStaffList.splice(parseInt(b.dataset.idx),1); renderStaffList(); });
}
document.getElementById('manageStaffBtn').onclick=openStaffModal;
document.getElementById('staffModalCancel').onclick=()=>document.getElementById('staffModal').classList.remove('show');
document.getElementById('staffModal').onclick=(e)=>{ if(e.target.id==='staffModal')document.getElementById('staffModal').classList.remove('show'); };
document.getElementById('addStaffBtn').onclick=()=>{
  const input=document.getElementById('newStaffName');
  const name=input.value.trim();
  if(!name){ document.getElementById('staffModalMsg').textContent='请输入姓名'; return; }
  if(modalStaffList.includes(name)){ document.getElementById('staffModalMsg').textContent='该人员已存在'; return; }
  modalStaffList.push(name);
  input.value='';
  renderStaffList();
  document.getElementById('staffModalMsg').textContent='';
};
document.getElementById('newStaffName').onkeydown=(e)=>{ if(e.key==='Enter')document.getElementById('addStaffBtn').click(); };
document.getElementById('staffModalSave').onclick=async()=>{
  const body={staff:modalStaffList.filter(Boolean), today_staff:[], quotas:{}, daily_quota:document.getElementById('quotaDefault').value, recall_days:document.getElementById('recallInput').value, recall_cooldown_days:document.getElementById('recallCooldown').value};
  try{
    const res=await fetch('/api/staff',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j=await res.json();
    if(j.ok){ document.getElementById('staffModal').classList.remove('show'); dTip().textContent='人员名单已保存。'; loadDispatch(); }
    else { document.getElementById('staffModalMsg').textContent='保存失败。'; }
  }catch(e){ document.getElementById('staffModalMsg').textContent='保存失败：'+e; }
};

// ===== 历史排班查询 =====
let historyDates=[], historyPage=1, historyData=null, historyFocusCat='';
const H_PAGE=50;
async function loadHistoryDates(){
  try{
    const res=await fetch('/api/history_dates');
    const j=await res.json();
    historyDates=j.dates||[];
  }catch(e){}
}
async function loadHistory(date){
  const body=document.getElementById('historyBody');
  const meta=document.getElementById('historyMeta');
  const staffWrap=document.getElementById('historyStaff');
  if(!date){ body.innerHTML=''; meta.textContent=''; staffWrap.innerHTML=''; return; }
  try{
    const res=await fetch('/api/history?date='+encodeURIComponent(date));
    const j=await res.json();
    if(!j.found){ body.innerHTML='<tr><td colspan="6" style="color:#999;text-align:center;padding:12px">暂无该日期的排班记录</td></tr>'; meta.textContent=''; staffWrap.innerHTML=''; return; }
    historyData=j;
    historyPage=1;
    historyFocusCat='';
    renderHistCatStat(j);
    meta.textContent=`生成时间：${j.created_at||'-'}，共 ${j.assignments?j.assignments.length:0} 条`;
    staffWrap.innerHTML=(j.staff||[]).map((s,i)=>{
      const q=(j.quotas||{})[s]||'默认';
      return `<span class="badge">${esc2(s)} (${q})</span>`;
    }).join('')||(j.staff||[]).length===0?'<span class="badge empty">无排班人员</span>':'';
    renderHistory();
  }catch(e){ body.innerHTML='<tr><td colspan="6" style="color:#c0392b;text-align:center;padding:12px">加载失败：'+esc2(e)+'</td></tr>'; }
}
function renderHistCatStat(j){
  const wrap=document.getElementById('histCatStat'); if(!wrap) return;
  const stats=j.cat_stats||{};
  const cats=[['00','其他/未匹配']].concat((dData.cats||[]).map(c=>[c.key,c.name]));
  let total=0; cats.forEach(([k])=>{ total+=(stats[k]||0); });
  const nrSum=(dData.cats||[]).filter(c=>c.need_recall).reduce((s,c)=>s+(stats[c.key]||0),0);
  wrap.innerHTML='<div class="cat-stat-title">回访分类统计（点击数字下钻，共 '+total+' 条｜需再次回访 '+nrSum+' 条）</div><div class="cat-stat-row">'
    + cats.map(([k,n])=>{
        const col=CAT_COLORS[k]||'#95a5a6'; const num=stats[k]||0;
        const active=historyFocusCat===k?'active':'';
        const nameShown=(n||'').length>10?(n.slice(0,10)+'…'):n;
        return `<button class="cat-pill ${active}" style="--c:${col}" onclick="historyFocusCat='${k}'; renderHistory();"><b>${num}</b><span>${esc2(k)} ${esc2(nameShown)}</span></button>`;
      }).join('')
    + `<button class="cat-pill ${historyFocusCat===''?'active':''}" onclick="historyFocusCat=''; renderHistory();"><b>${total}</b><span>全部</span></button>`
    + '</div>';
}
function renderHistory(){
  const base=(historyData&&historyData.realtime_items&&historyData.realtime_items.length)?historyData.realtime_items:(historyData&&historyData.assignments)||[];
  const list= historyFocusCat ? base.filter(x=>(x.rec_category||'00')===historyFocusCat) : base;
  const pages=Math.max(1,Math.ceil(list.length/H_PAGE));
  if(historyPage>pages)historyPage=pages;
  const slice=list.slice((historyPage-1)*H_PAGE,historyPage*H_PAGE);
  document.getElementById('historyBody').innerHTML=slice.map((it,i)=>`<tr>
    <td>${(historyPage-1)*H_PAGE+i+1}</td>
    <td>${it.agreement_id}</td>
    <td>${esc2(it.consumer_id||it.user_id||'-')}</td>
    <td>${esc2(it.phone)}</td>
    <td>${esc2(it.assigned_solver)}</td>
    <td>${esc2(it.planned_time)}</td>
  </tr>`).join('');
  document.getElementById('historyPager').innerHTML=list.length?(`共 ${list.length} 条 · 第 ${historyPage}/${pages}页 `
    +`<button ${historyPage<=1?'disabled':''} onclick="historyPage--;renderHistory()">上页</button>`
    +`<button ${historyPage>=pages?'disabled':''} onclick="historyPage++;renderHistory()">下页</button>`):'';
}
document.getElementById('historyDate').onchange=()=>{ loadHistory(document.getElementById('historyDate').value); };

document.getElementById('clearHistoryBtn').onclick=async()=>{
  if(!confirm('确定清空全部历史排班快照吗？此操作会删除所有日期的排班历史记录，且不可恢复。'))return;
  try{
    const res=await fetch('/api/clear_history',{method:'POST'});
    const j=await res.json();
    alert(j.ok?'历史排班已清空。':('清空失败：'+(j.msg||'未知错误')));
    if(j.ok){ historyData=null; document.getElementById('historyBody').innerHTML=''; document.getElementById('historyPager').innerHTML=''; document.getElementById('historyStaff').innerHTML=''; document.getElementById('historyMeta').textContent=''; loadHistoryDates(); }
  }catch(e){ alert('清空失败：'+e); }
};

// 支持链接深链：?tab=xxx 直接定位到对应视图；?mods=a,b 限制对方可见模块；?user=姓名 按人权限
// v10.21.1 修复：userRaw 分支必须先取 /api/staff（dData.staff 是 Promise.all 异步填充的），
//   否则同步读 dData.staff.user_permissions 永远是空 → 命中 fallback，授权形同虚设。
const tabMap={all:'all',owe:'owe',lf:'lf',reception:'reception',dispatch:'dispatch',schedule:'dispatch_schedule',overview:'dispatch_overview',history:'dispatch_history'};
function _applySharedUI(allowed, canSync, t){
  if(allowed){
    document.querySelectorAll('#tabs button').forEach(b=>{ if(!allowed.has(b.dataset.v)) b.style.display='none'; });
    document.body.classList.add('shared');
    const hideIds=['dispatch-cfg','saveStaffBtn','genDispatchBtn','manageStaffBtn','genLinkBtn','permBtn','clearTodayBtn','clearAssignmentsBtn','clearHistoryBtn','batchBar','updateBtn','updateUrl','updateTip','btnSync'];
    hideIds.forEach(id=>{ const el=document.getElementById(id); if(el) el.style.display='none'; });
    if(canSync){ const sb=document.getElementById('btnSync'); if(sb) sb.style.display=''; }
    const banner=document.getElementById('sharedBanner');
    if(banner){ banner.style.display='block'; banner.textContent = canSync ? ('共享查看模式：你仅能看到管理员授权开放的模块；你拥有「同步数据库」权限。') : ('共享查看模式：你仅能看到管理员授权开放的模块，且无法修改排班配置。如需操作请使用本机管理端。'); }
  }
  if(t && tabMap[t]){
    const v=tabMap[t];
    if(!allowed || allowed.has(v)){ state.view=v; }
  }
  if(allowed && !allowed.has(state.view)){ state.view=[...allowed][0]; }
  document.querySelectorAll('#tabs button').forEach(b=>b.classList.toggle('active', b.dataset.v===state.view));
}
// v10.28.55：权限由后端注入 window.__AUTH__（token 校验已在服务端完成）。
// 前端只负责按 modules 隐藏 tab、按 scope 过滤数据行。不再信任 ?user= / ?mods= 等前端参数。
function applyScope(scope, phoneAllow){
  // scope: '全部' 或 [城市关键词]；phoneAllow: '全部' 或 [手机号前缀]。
  // 两个维度取「与」：城市命中 且 手机号前缀命中（任一维度为全部则不限该维度）。
  let keywords=[];
  if(Array.isArray(scope)) keywords=scope;
  else if(typeof scope==='string' && scope && scope!=='全部') keywords=[scope];
  let phones=[];
  if(Array.isArray(phoneAllow)) phones=phoneAllow;
  else if(typeof phoneAllow==='string' && phoneAllow && phoneAllow!=='全部') phones=[phoneAllow];
  window.__SCOPE__ = keywords.length ? keywords : null;
  window.__PHONE_ALLOW__ = phones.length ? phones : null;
  if(!window.__SCOPE__ && !window.__PHONE_ALLOW__){
    if(window.__ITEMS_ALL__) dData.items=window.__ITEMS_ALL__;
    return;
  }
  if(!window.__ITEMS_ALL__ && dData.items) window.__ITEMS_ALL__=dData.items;
  const all=window.__ITEMS_ALL__||dData.items||[];
  dData.items = all.filter(r=>{
    let okScope=true, okPhone=true;
    if(window.__SCOPE__){
      const hay=[r.city,r.area,r.cloc,r.lla,r.province].map(x=>x||'').join(' ');
      okScope=window.__SCOPE__.some(k=>hay.indexOf(k)>=0);
    }
    if(window.__PHONE_ALLOW__){
      const ph=(r.phone||'')+'|'+(r.cur_phone||'');
      okPhone=window.__PHONE_ALLOW__.some(p=>ph.indexOf(p)>=0);
    }
    return okScope && okPhone;
  });
}
async function applyDeepLink(){
  const params=new URLSearchParams(location.search);
  const t=params.get('tab');
  let allowed=null, canSync=false, scope='全部', phoneAllow='全部';
  const auth=(typeof window.__AUTH__!=='undefined')?window.__AUTH__:null;
  if(auth){
    if(auth.is_admin || (auth.modules||[]).indexOf('all')>=0){ allowed=null; }
    else { allowed=new Set(auth.modules||[]); }
    canSync=!!auth.can_sync;
    scope=auth.scope||'全部';
    phoneAllow=auth.phone_allow||'全部';
  }
  _applySharedUI(allowed, canSync, t);
  applyScope(scope, phoneAllow);
}

// 仅在本地服务模式下显示「生成回访链接」（直接打开 HTML 文件时无此接口）
if(!window.__SERVE__){
  const gl=document.getElementById('genLinkBtn');
  if(gl) gl.style.display='none';
}

// v10.21.1：先按当前 state 渲染一次（避免空白），再异步应用深链（含按人权限）后重渲染
render();
applyDeepLink().then(()=>{ render(); });

// v10.21.5：电池电量实时刷新 —— 按电池 SN 批量调 /api/battery_now 覆盖快照值（服务台口径）
const _batteryCache = new Map();
async function refreshBatteryNow(){
  try{
    if(!dData.items || !dData.items.length) return;
    if(!['dispatch','dispatch_schedule','dispatch_overview','dispatch_history','all'].includes(state.view||'')) return;
    const sns = [];
    const seen = new Set();
    for(const it of dData.items){
      const sn = (it.bsn||'').toString().trim();
      if(!sn || seen.has(sn)) continue;
      seen.add(sn); sns.push(sn);
      if(sns.length>=25) break;
    }
    if(!sns.length) return;
    let payload;
    try{
      const resp = await fetch('/api/battery_now?sn='+encodeURIComponent(sns.join(',')));
      payload = await resp.json();
    }catch(_){ return; }
    if(!payload || !payload.ok || !payload.items) return;
    let changed = false;
    const nowMs = Date.now();
    for(const it of dData.items){
      const sn = (it.bsn||'').toString().trim();
      const nb = payload.items[sn];
      if(!nb) continue;
      const newSoc = (nb.soc!==undefined && nb.soc!==null) ? String(nb.soc) : '';
      if((it.soc||'') !== newSoc || (it.onl||'') !== (nb.online||'') || !_batteryCache.has(sn)){
        it.soc = newSoc; it.onl = nb.online||it.onl;
        _batteryCache.set(sn, {soc: newSoc, online: nb.online||'', ts: nowMs});
        changed = true;
      }
    }
    if(changed) render();
  }catch(e){ /* 静默失败，下轮再试 */ }
}
setInterval(refreshBatteryNow, 30000);
// 视图切换时也立即拉一次
const _origSwitch = window.__switchView__ || ((v)=>{ state.view=v; render(); });
window.addEventListener('hashchange', refreshBatteryNow);
refreshBatteryNow();

// v10.28.55:URL 含 ?sync=1 自动触发后端从内网抽数、生成看板、等完成后刷新页面
//  v10.28.55 修复:start.bat 改成纯 ASCII,在 GBK 控制台下不会乱码导致 cmd 把 if/for/where 当成外部命令。
// 复用现有 /sync + /sync_status 接口(已存在于 serve.py),不引入新依赖。
(function(){
  try{
    const sp = new URL(location.href).searchParams.get('sync');
    if(sp !== '1') return;
    const bar = document.createElement('div');
    bar.id = '_sync_top_bar';
    bar.style.cssText = 'position:fixed;top:0;left:0;right:0;background:#1F4E78;color:#fff;text-align:center;padding:9px 12px;font-size:13px;z-index:999999;font-weight:600;line-height:1.7;box-shadow:0 2px 10px rgba(0,0,0,.18)';
    bar.innerHTML = '⏳ 正在从内网抽数 → 重建 records.json → 重新生成看板…';
    (document.body||document.documentElement).appendChild(bar);
    const t0 = Date.now();
    function poll(afterKick){
      fetch('/sync_status',{cache:'no-store'}).then(r=>r.json()).then(s=>{
        const stepInfo = (s&&s.log&&s.log.length) ? ('（步骤 '+s.step+'/'+s.log.length+'）') : '';
        if(s && s.running){
          bar.innerHTML = '⏳ 正在从内网抽数 ' + stepInfo + '…（已用 '+Math.round((Date.now()-t0)/1000)+'秒）';
          setTimeout(poll, 1500);
        }else if(s && s.done){
          bar.innerHTML = '✅ 同步完成!3秒后刷新看板…';
          setTimeout(()=>location.replace('/?_=' + Date.now()), 3000);
        }else if(s && s.error){
          bar.innerHTML = '❌ 同步失败:' + (s.error||'未知错误') + '<br><small style="opacity:.85">查看 out/sync_error.log;或确认 db_conf.json 已填真实内网凭据</small>';
        }else{
          // 同步已结束但未标记 done/error(可能 db_conf 占位符未填):拉一次 records.json 看是否真有数据
          fetch('/api/version',{cache:'no-store'}).then(r=>r.json()).then(v=>{
            if(afterKick){
              // 已经点击过 sync,但没生效,提示手动用顶部 [SYNC] 按钮
              bar.innerHTML = '❌ 同步未触发。请点击顶部右侧的「[SYNC] 同步数据库」按钮或确认 db_conf.json 已填。';
            }else{
              setTimeout(poll, 1500);
            }
          });
        }
      }).catch(e=>{
        bar.innerHTML = '❌ 网络异常:' + e + '(服务是否已启动?)';
      });
    }
    // 主动触发一次同步
    fetch('/sync',{cache:'no-store',method:'POST'}).then(r=>r.json()).then(d=>{
      if(d && d.ok){
        setTimeout(poll, 800);
      }else{
        bar.innerHTML = '⚠️ ' + (d && d.msg || '同步触发失败') + ' · 等待手动同步';
        setTimeout(poll, 1500);
      }
    }).catch(e=>{
      bar.innerHTML = '⚠️ 无法触发同步:' + e + ' · 等待手动同步';
      setTimeout(poll, 1500);
    });
  }catch(e){ /* 静默 */ }
})();

// ==================== v10.28.55 回访实际效果 Tab ====================
(function(){
  const GRADES = {
    S1:{n:'已换电·当日促成',c:'#0a8a3a'}, S2:{n:'已换电·1-7天促成',c:'#2bb55a'},
    S3:{n:'已换电·8-30天促成',c:'#7acb80'}, S4:{n:'已换电·31-90天促成',c:'#b8e07b'},
    S5:{n:'已换电·90天+促成',c:'#cfe8a0'}, S6:{n:'在租沉默·未促成',c:'#f3b441'},
    S7:{n:'已退订·挽回失败',c:'#9aa4b2'}, S8:{n:'已归还·未再借',c:'#e58a3a'},
    S9:{n:'电池已回收',c:'#d2603a'}, S10:{n:'退订中·未结案',c:'#b084cc'}
  };
  const CONV = ['S1','S2','S3','S4'];       // 有效促成（90天内）
  const ORDER = ['S1','S2','S3','S4','S5','S6','S7','S8','S9','S10'];
  let efPage = 1, efFiltered = [], efSortKey = '';

  function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g, m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m])); }

  // ---- v10.28.55：接待人姓名兜底 ----
  // 数据库里 solver_user_name 存的是员工数字 ID（0/1/2/...），后端员工表探测失败时
  // records.json 里的 solver 字段就是裸数字，用户看到「0、1、2...」不知道是啥。
  // 前端做一层友好兜底：1~6 位纯数字一律显示「员工#N」，不依赖 records.json 重跑。
  function fmtSolver(name){
    if(name==null) return '';
    const s=String(name).trim();
    if(!s) return '';
    // 1~6 位纯数字（员工 ID 通常 < 100000；手机号 11 位/协议 ID 13+ 位不会被误判）
    if(/^\d{1,6}$/.test(s)) return '员工#'+s;
    return s;
  }
  // 接待人姓名排序权重：纯数字（员工#N）排最后；正常姓名按 Unicode
  function solverSortKey(name){
    const m=String(name||'').match(/^员工#(\d+)$/);
    if(m) return 'zz_' + String(Number(m[1])).padStart(8,'0');
    return String(name||'');
  }

  // ---- v10.28.55：构建 aid → phone / pid / battery_sn 索引（reception_detail 里没写入手机号，
  //     必须从 DATA.rows 用 aid 关联补上，否则"手机号"列永远横杆）----
  const _aidToPhone = {};   // aid -> 手机号
  const _aidToUid = {};     // aid -> uid（用户ID）
  const _aidToPid = {};     // aid -> 电池产品ID（records 里 pid 是 battery_product_id）
  const _aidToBsn = {};     // aid -> 电池SN
  (function(){
    const rows = (DATA && DATA.rows) || [];
    for(let i=0;i<rows.length;i++){
      const r = rows[i];
      // 优先用 cur_phone（cb_user 当前手机号），fallback phone（协议表手机）
      const ph = (r.cph && String(r.cph).trim()) || (r.ph && String(r.ph).trim()) || '';
      if(r.id){ _aidToPhone[r.id] = ph; _aidToUid[r.id] = r.uid || ''; _aidToPid[r.id] = r.pid || ''; _aidToBsn[r.id] = r.bsn || ''; }
    }
  })();

  // ---- 取明细：优先用 DATA.reception_detail（records.json 已带 effect_grade）----
  function efSource(){
    const d = (DATA && DATA.reception_detail) || [];
    return d.map(r=>{
      const ph = (r.phone && String(r.phone).trim()) || _aidToPhone[r.aid] || '';
      const uid = r.uid || _aidToUid[r.aid] || '';
      const pid = r.pid || _aidToPid[r.aid] || '';
      const bsn = r.battery_sn || _aidToBsn[r.aid] || '';
      return {
        // v10.28.55：保留 aid（协议ID），明细表新增此列
        aid: r.aid||'', time: r.time||'', solver: r.solver||'', tags: r.tags||[], type: r.type||'',
        status: r.agreement_status||'', raw: r._agreement_status_raw||'',
        grade: r.effect_grade||'S6', delta: (r.delta_days==null?null:r.delta_days),
        first: r.first_take_at||'', bct: r.battery_circ_time||'', bct_full: r.battery_circ_full||'',
        pid: pid, uid: uid, phone: ph, bsn: bsn, detail: r.detail||''
      };
    });
  }

  // ---- 填充下拉选项（只填一次）----
  let efOptsDone = false;
  // v10.28.55：chip+推荐下拉 重写 —— 默认只显示已选 chip；输入搜索弹出候选下拉；
  //              点击候选 / chip 即时切换选中；Enter / Esc 关闭下拉；失焦关闭。
  function _bindSearchBox(){
    document.querySelectorAll('.ef-multiselect').forEach(box=>{
      const inp = box.querySelector('.ef-search');
      const sel = box.querySelector('select');
      const sg  = box.querySelector('.ef-suggest');
      const cp  = box.querySelector('.ef-chips');
      if(!inp || !sel || !sg || !cp) return;

      const _renderChips = ()=>{
        const selVals = Array.from(sel.selectedOptions);
        cp.innerHTML = selVals.map(o=>{
          const v = o.value;
          return `<span class="ef-chip-tag" data-val="${esc(v)}" title="${esc(v)}（点击移除）">${esc(v)}<span class="ef-x">×</span></span>`;
        }).join('');
        // 更新 placeholder
        inp.placeholder = selVals.length>0
          ? `🔍 已选 ${selVals.length} 个·可继续搜索追加`
          : (sel.id === 'efSolver' ? '🔍 输入姓名搜索…' : '🔍 输入标签搜索…');
      };

      const _renderSuggest = ()=>{
        const kw = (inp.value || '').trim().toLowerCase();
        const selVals = new Set(Array.from(sel.selectedOptions).map(o=>o.value));
        let list;
        if(!kw){
          // 空搜索：显示前 20 个未选项（按字母排序）
          list = Array.from(sel.options).filter(o=>!selVals.has(o.value)).slice(0,20);
        } else {
          // 关键词过滤：匹配 AND（按前缀优先 + 包含次之）
          const m1=[], m2=[];
          for(const opt of sel.options){
            const t = (opt.textContent||'').toLowerCase();
            if(t.startsWith(kw)) m1.push(opt);
            else if(t.indexOf(kw) >= 0) m2.push(opt);
          }
          list = [...m1, ...m2].slice(0, 20);
        }
        if(list.length === 0){
          sg.innerHTML = `<div class="ef-sg" style="cursor:default;color:#999">无匹配项</div>`;
          sg.hidden = false;
          return;
        }
        sg.innerHTML = list.map(o=>{
          const isSel = selVals.has(o.value);
          const t = (o.textContent||'').replace(/</g,'&lt;');
          // 高亮命中片段
          let hi = esc(t);
          if(kw){
            const idx = t.toLowerCase().indexOf(kw);
            if(idx>=0){
              hi = esc(t.slice(0,idx)) + '<b style="background:#fef3c7;color:#92400e">' +
                   esc(t.slice(idx, idx+kw.length)) + '</b>' + esc(t.slice(idx+kw.length));
            }
          }
          return `<div class="ef-sg ${isSel?'sel':''}" data-val="${esc(o.value)}">
            <span>${hi}</span><span class="ef-check">${isSel?'✓':'+'}</span>
          </div>`;
        }).join('');
        sg.hidden = false;
      };

      const _hide = ()=>{ sg.hidden = true; };
      const _toggle = (val)=>{
        const opt = Array.from(sel.options).find(o=>o.value === val);
        if(!opt) return;
        opt.selected = !opt.selected;
        _renderChips();
        _renderSuggest();
        efApplyFilter();
      };

      // 输入 → 重渲染候选
      inp.addEventListener('input', ()=> _renderSuggest());
      // 聚焦 → 显示候选
      inp.addEventListener('focus', ()=> _renderSuggest());
      // 失焦 → 延迟关闭（点击候选有时间）
      inp.addEventListener('blur', ()=> setTimeout(_hide, 150));

      // 候选点击
      sg.addEventListener('mousedown', (e)=>{ e.preventDefault(); }); // 防止 blur 先触发
      sg.addEventListener('click', (e)=>{
        const t = e.target.closest('.ef-sg');
        if(!t || !t.dataset.val) return;
        _toggle(t.dataset.val);
        inp.focus();
      });

      // chip 点击 → 移除
      cp.addEventListener('click', (e)=>{
        const t = e.target.closest('.ef-chip-tag');
        if(!t || !t.dataset.val) return;
        _toggle(t.dataset.val);
      });

      // 键盘：Enter 选中第一个候选 / Esc 关闭
      inp.addEventListener('keydown', (e)=>{
        if(e.key === 'Enter'){
          e.preventDefault();
          const first = sg.querySelector('.ef-sg[data-val]');
          if(first) _toggle(first.dataset.val);
        } else if(e.key === 'Escape'){
          _hide();
          inp.blur();
        } else if(e.key === 'Backspace' && !inp.value){
          // 输入框为空时按退格 → 移除最后一个 chip
          const sels = Array.from(sel.selectedOptions);
          if(sels.length){
            sels[sels.length-1].selected = false;
            _renderChips();
            _renderSuggest();
            efApplyFilter();
          }
        }
      });

      // select 变化（来自全选/清空按钮） → 重渲染
      sel.addEventListener('change', ()=>{ _renderChips(); _renderSuggest(); });

      // 暴露给全选/清空按钮回调
      box._renderChips = _renderChips;
      box._renderSuggest = _renderSuggest;
    });
  }
  function efFillOpts(rows){
    if(efOptsDone) return;
    const sv = document.getElementById('efSolver'), tg = document.getElementById('efTag');
    const st = document.getElementById('efStatus'), gd = document.getElementById('efGrade');
    if(!sv||!tg||!st||!gd) return;
    // v10.28.55：接待人下拉用 fmtSolver 兜底显示真实姓名（处理 0-19 裸数字 ID），
    //              排序时把「员工#N」集中放到列表尾部，正常姓名按 Unicode 排序。
    [...new Set(rows.flatMap(r=>(r.solvers&&r.solvers.length)?r.solvers:[r.solver]).map(fmtSolver))]
      .filter(Boolean).sort((a,b)=> solverSortKey(a).localeCompare(solverSortKey(b),'zh-Hans-CN'))
      .forEach(v=> sv.insertAdjacentHTML('beforeend',`<option value="${esc(v)}">${esc(v)}</option>`));
    const tagSet=new Set(); rows.forEach(r=>(r.tags||[]).forEach(t=>tagSet.add(t)));
    [...tagSet].sort().forEach(v=>
      tg.insertAdjacentHTML('beforeend',`<option value="${esc(v)}">${esc(v)}</option>`));
    [...new Set(rows.map(r=>r.status))].filter(Boolean).sort().forEach(v=>
      st.insertAdjacentHTML('beforeend',`<option value="${esc(v)}">${esc(v)}</option>`));
    ORDER.forEach(g=>
      gd.insertAdjacentHTML('beforeend',`<option value="${g}">${GRADES[g].n}</option>`));
    // v10.28.55：chip+推荐下拉 绑定（一次性，绑定后渲染 chip 容器）
    _bindSearchBox();
    // 初次渲染 chip 容器（空选时仅显示搜索框 + 提示）
    document.querySelectorAll('.ef-multiselect').forEach(b=>{ if(b._renderChips) b._renderChips(); });
    efOptsDone = true;
  }

  // ---- 筛选 ----
  // v10.28.55：接待人 / 标签 支持多选（<select multiple>）。空选（未选任何项）视为「全部」。
  function _selVals(id){
    const el=document.getElementById(id);
    if(!el) return [];
    return Array.from(el.selectedOptions).map(o=>o.value).filter(v=>v!=='');
  }
  function efApplyFilter(){
    const df=document.getElementById('efDateFrom').value, dt=document.getElementById('efDateTo').value;
    const svArr=_selVals('efSolver'), tgArr=_selVals('efTag');
    const gd=document.getElementById('efGrade').value, st=document.getElementById('efStatus').value;
    efFiltered = efSource().filter(r=>{
      const d=(r.time||'').slice(0,10);
      if(df && d && d<df) return false;
      if(dt && d && d>dt) return false;
      // v10.28.55：多选——任一命中即保留（接待人看 solvers 列表，标签看 tags 列表）
      // v10.28.55：接待人筛选值已用 fmtSolver 格式化（员工#N），比对时也要把 r.solvers 转一遍
      if(svArr.length){
        const sl = ((r.solvers && r.solvers.length) ? r.solvers : [r.solver]).map(fmtSolver).filter(Boolean);
        if(!sl.some(x=>svArr.includes(x))) return false;
      }
      if(tgArr.length){
        const tl = (r.tags && r.tags.length) ? r.tags : [];
        if(!tl.some(x=>tgArr.includes(x))) return false;
      }
      if(gd && r.grade!==gd) return false;
      if(st && r.status!==st) return false;
      return true;
    });
    efPage = 1;
  }

  // ---- v10.28.55：单次遍历同时算 KPI / 漏斗 / 排行 / 分布（避免 50k 行 × 多次 filter 卡顿）----
  // v10.28.55：by_solver / by_tag 用 Set 计数 distinct aid，让"总接待 vs 促成"能真实反映独立用户
  function efAggregate(){
    const buckets = {S1:0,S2:0,S3:0,S4:0,S5:0,S6:0,S7:0,S8:0,S9:0,S10:0};
    const dist = {'0d':0,'1d':0,'3d':0,'7d':0,'15d':0,'30d':0,'90d+':0};
    const bySolverSet = {}, byTagSet = {};
    const aidsTotal = new Set(), aidsConv = new Set();
    let conv = 0, c30 = 0;
    for(let i=0;i<efFiltered.length;i++){
      const r = efFiltered[i];
      buckets[r.grade] = (buckets[r.grade]||0) + 1;
      const isConv = CONV.indexOf(r.grade) >= 0;
      const aid = r.aid || '';
      if(aid){
        aidsTotal.add(aid);
        if(isConv) aidsConv.add(aid);
      }
      const rs = (r.solvers && r.solvers.length) ? r.solvers : [r.solver];
      for(let si=0; si<rs.length; si++){
        // v10.28.55：接待人姓名兜底（0/1/2...裸数字 → 员工#N）
        const sk = fmtSolver(rs[si]) || '（未记录接待人）';
        const sset = bySolverSet[sk] || (bySolverSet[sk]={total:new Set(),conv:new Set()});
        if(aid){ sset.total.add(aid); if(isConv) sset.conv.add(aid); }
      }
      const tags = (r.tags && r.tags.length) ? r.tags : ['（无标签）'];
      for(let j=0;j<tags.length;j++){
        const tk = tags[j];
        const tset = byTagSet[tk] || (byTagSet[tk]={total:new Set(),conv:new Set()});
        if(aid){ tset.total.add(aid); if(isConv) tset.conv.add(aid); }
      }
      if(isConv){
        conv++;
        if(r.grade !== 'S4') c30++;
        if(r.delta != null){
          const d = r.delta;
          if(d <= 0)        dist['0d']++;
          else if(d <= 1)   dist['1d']++;
          else if(d <= 3)   dist['3d']++;
          else if(d <= 7)   dist['7d']++;
          else if(d <= 15)  dist['15d']++;
          else if(d <= 30)  dist['30d']++;
          else if(d <= 90)  dist['30d']++;   // 31~90 天并入 30d
          else              dist['90d+']++;
        }
      }
    }
    // 转为排行结构（total/conv 为 Set 大小 = 独立 aid 数）
    // v10.28.55：直接输出 {name:{total,conv,rate}} 对象形态，避免下游用 Object.entries 处理
    //              数组时被索引（如 0/1/2）"伪装"成接待人名
    const toRank = (mp) => {
      const out = {};
      for(const k in mp){
        const t = mp[k].total.size, c = mp[k].conv.size;
        out[k] = {name:k, total:t, conv:c, rate: t?+(c*100/t).toFixed(1):0};
      }
      return out;
    };

    // v10.28.55：按日/周/月统计 —— 当下时刻 vs 历史 7/30 天
    // 用 effect_grade 与原接待时间 (r.time) 切窗；分子=达成促成的记录数 (S1~S4)
    const now = new Date();
    const todayKey = now.toISOString().slice(0,10);
    // v10.28.55：新增 昨日 / 最近3天
    const yestKey = new Date(now.getTime() - 86400e3).toISOString().slice(0,10);
    const _3dAgo  = new Date(now.getTime() - 2*86400e3).toISOString().slice(0,10); // 含今日=3天窗口
    const _7dAgo = new Date(now.getTime() - 7*86400e3).toISOString().slice(0,10);
    const _30dAgo = new Date(now.getTime() - 30*86400e3).toISOString().slice(0,10);
    // 周一为本周第一天（week=Mon~Sun）
    const dow = (now.getDay() + 6) % 7; // 0=Mon
    const monKey = new Date(now.getTime() - dow*86400e3).toISOString().slice(0,10);
    const monthKey = todayKey.slice(0,7) + '-01';
    const byPeriod = {
      yesterday: {total:0, conv:0, rate:0},
      today:    {total:0, conv:0, rate:0},
      this_week:{total:0, conv:0, rate:0},
      this_month:{total:0, conv:0, rate:0},
      last3d:   {total:0, conv:0, rate:0},
      last7d:   {total:0, conv:0, rate:0},
      last30d:  {total:0, conv:0, rate:0},
      all:      {total:efFiltered.length, conv:conv, rate: efFiltered.length?+(conv*100/efFiltered.length).toFixed(1):0}
    };
    for(let i=0;i<efFiltered.length;i++){
      const r=efFiltered[i];
      const d=(r.time||'').slice(0,10);
      if(!d) continue;
      const isConv = CONV.indexOf(r.grade) >= 0;
      if(d===yestKey){ byPeriod.yesterday.total++; if(isConv) byPeriod.yesterday.conv++; }
      if(d===todayKey){ byPeriod.today.total++; if(isConv) byPeriod.today.conv++; }
      if(d>=monKey && d<=todayKey){ byPeriod.this_week.total++; if(isConv) byPeriod.this_week.conv++; }
      if(d>=monthKey && d<=todayKey){ byPeriod.this_month.total++; if(isConv) byPeriod.this_month.conv++; }
      if(d>=_3dAgo  && d<=todayKey){ byPeriod.last3d.total++; if(isConv) byPeriod.last3d.conv++; }
      if(d>=_7dAgo  && d<=todayKey){ byPeriod.last7d.total++; if(isConv) byPeriod.last7d.conv++; }
      if(d>=_30dAgo && d<=todayKey){ byPeriod.last30d.total++; if(isConv) byPeriod.last30d.conv++; }
    }
    ['today','this_week','this_month','last7d','last30d'].forEach(k=>{
      const v=byPeriod[k];
      v.rate = v.total ? +(v.conv*100/v.total).toFixed(1) : 0;
    });

    return {t: efFiltered.length, distinctTotal: aidsTotal.size, distinctConv: aidsConv.size,
            conv, c30, buckets, dist, bySolver: toRank(bySolverSet), byTag: toRank(byTagSet),
            byPeriod};
  }

  // ---- 渲染 KPI ----
  // v10.28.55：参数增加 unsub10（退订中·未结案）
  // v10.28.55：6 张卡均加 tooltip 解释口径，避免「为什么 30 天促成人数多于协议促成数但比率反而更高」等疑惑；
  //              「已退订」=0 时显示 hint 提示「之前回访过但已终止协议的记录已计入 S7，需要数据支持」
  function efRenderKpi(t, distinctTotal, distinctConv, c30, silent, unsub, unsub10){
    const pct=(a,b)=>b?((a*100)/b).toFixed(1)+'%':'0.0%';
    // v10.28.55：在租沉默占比 / 退订占比 / 退订中占比
    const silentPct = pct(silent, t);
    const unsubPct  = pct(unsub, t);
    const unsub10Pct= pct(unsub10||0, t);
    const tooltips = {
      '': `总接待记录数（raw 接待次数：同一用户多次被接待都计入），用于指标准确度参照`,
      distinct: `接待去重总人数：按「接待人 ID」+「接待时间」去重后的独立接待人次数。\n公式：COUNT(DISTINCT solver_id, rec_date)\n当前：${distinctTotal} 人次`,
      conv: `促成换电（独立协议）\n公式：COUNT(DISTINCT aid WHERE grade IN S1~S4) = ${distinctConv}\n分母：独立协议总数 = ${distinctTotal}\n${distinctTotal?'= '+((distinctConv*100/distinctTotal).toFixed(1)+'%'):''}`,
      c30: `30天内促成\n公式：COUNT(grade IN S1~S3 AND 30天内促成) = ${c30}\n分母：总接待记录数 = ${t}\n${t?'= '+((c30*100/t).toFixed(1)+'%'):''}\n注：S4（31~90天促成）不计入`,
      silent: `在租沉默（S6）\n公式：COUNT(grade=S6) = ${silent}\n占总接待：${silentPct}\n说明：协议仍在租、回访后仍未促成的记录`,
      unsub: `已退订（S7）\n公式：COUNT(grade=S7) = ${unsub}\n占总接待：${unsubPct}\n说明：协议状态已变为 terminated/closed 的回访记录\n⚠ 当数值为 0 时表示：当前接待明细中协议状态已退订的记录确实为 0 条（系统统计了所有接待记录，包括已退订协议的历史接待，不会因协议退订而排除该次回访）`,
      unsub10: `退订中（S10）\n公式：COUNT(grade=S10) = ${unsub10||0}\n占总接待：${unsub10Pct}\n说明：协议处于 unsubscribing 状态，仍可挽回`
    };
    const cards=[
      {k:'',label:'总接待记录',val:t,sub:`独立协议 ${distinctTotal} 个`,c:'#1F4E78'},
      {k:'distinct',label:'接待去重总人数',val:distinctTotal,sub:`占比 ${pct(distinctTotal,t)} 总记录`,c:'#3a5a8c',tipKey:'distinct'},
      {k:'conv',label:'促成换电（独立协议）',val:distinctConv,sub:pct(distinctConv,distinctTotal)+' 协议促成率',c:'#0a8a3a'},
      {k:'c30',label:'30天内促成',val:c30,sub:`公式见 tooltip · ${pct(c30,t)}`,c:'#2bb55a'},
      {k:'silent',label:'在租沉默',val:silent,sub:`占比 ${silentPct} · 回访未促成`,c:'#f3b441'},
      {k:'unsub',label:'已退订 + 退订占比',val:unsub,sub:`${unsub} 条 / ${unsubPct} 总接待`,c:'#9aa4b2',hint: unsub===0 ? '<div style="margin-top:4px;color:#c0392b;font-size:11px">⚠ 当前接待明细中协议状态为 terminated/closed 的记录为 0。如发现实际已退订协议的回访未被计入，请检查协议状态字段。</div>' : ''},
      {k:'unsub10',label:'退订中 + 占比',val:unsub10||0,sub:`${unsub10||0} 条 / ${unsub10Pct} 总接待`,c:'#b084cc'}
    ];
    document.getElementById('efKpi').innerHTML = cards.map(c=>{
      const tip = c.tipKey ? tooltips[c.tipKey] : (tooltips[c.k] || '');
      return `
      <div class="kpi-card" data-k="${c.k}" title="${(tip||'').replace(/"/g,'&quot;')}"
        style="background:#fff;border:1px solid #d7dee7;border-left:4px solid ${c.c};
        border-radius:8px;padding:12px;cursor:${c.k?'pointer':'default'};transition:.15s">
        <div style="color:#6b7785;font-size:12px">${c.label} ${c.hint?'<span style="color:#c0392b">●</span>':''}</div>
        <div style="font-size:24px;font-weight:700;color:${c.c};margin:4px 0">${c.val}</div>
        <div style="font-size:11px;color:#9aa4b2">${c.sub}</div>${c.hint||''}
      </div>`;}).join('');
    document.querySelectorAll('#efKpi .kpi-card').forEach(el=>{
      el.onclick=()=>{
        const k=el.dataset.k; if(!k) return;
        const gd=document.getElementById('efGrade');
        if(k==='conv'){ gd.value=''; efGradeSet=['S1','S2','S3','S4']; }
        else if(k==='c30'){ efGradeSet=['S1','S2','S3']; }
        else if(k==='silent'){ efGradeSet=['S6']; }
        else if(k==='unsub'){ efGradeSet=['S7']; }
        else if(k==='unsub10'){ efGradeSet=['S10']; }
        renderEffect(true);
        document.getElementById('efDetailTbl').scrollIntoView({behavior:'smooth'});
      };
    });
  }

  // ---- 渲染漏斗 ----
  function efRenderFunnel(buckets){
    const t = efFiltered.length || 1;
    const mx = Math.max(1, ...ORDER.map(g => buckets[g]||0));
    document.getElementById('efFunnel').innerHTML = ORDER.map(g=>{
      const n = buckets[g] || 0;
      const w = Math.max(2, (n/mx*100));
      return `<div class="fn-row" data-g="${g}" title="${GRADES[g].n}：点击筛选"
        style="display:flex;align-items:center;gap:8px;margin-bottom:5px;cursor:pointer;font-size:12px">
        <span style="width:150px;color:#555;flex-shrink:0">${GRADES[g].n}</span>
        <span style="flex:1;background:#eef1f5;border-radius:4px;height:16px;overflow:hidden">
          <span style="display:block;width:${w}%;height:100%;background:${GRADES[g].c}"></span></span>
        <span style="width:60px;text-align:right;color:#333">${n} <span style="color:#aaa">${(n*100/t).toFixed(1)}%</span></span>
      </div>`;
    }).join('');
    document.querySelectorAll('#efFunnel .fn-row').forEach(el=>{
      el.onclick=()=>{ efGradeSet=[el.dataset.g]; renderEffect(true); };
    });
  }

  // ---- 排行（接待人 / 标签）----
  // v10.28.55：toRank 直接输出对象 {name:{total,conv,rate}}；fmtSolver 兜底数字 ID；
  //              排序时把「员工#N」集中放到列表尾部，正常姓名按 Unicode 排序
  function efRenderRank(byMap, elId, head){
    const isSolver = (elId === 'efSolverRank');
    // 双向兼容：数组/对象都能正确处理
    const arr = (Array.isArray(byMap) ? byMap : Object.values(byMap||{}))
      .map(x => ({k: x.name, total: x.total, conv: x.conv, rate: x.rate != null ? x.rate : (x.total?+(x.conv*100/x.total).toFixed(1):0)}));
    if(isSolver){
      arr.sort((a,b)=> solverSortKey(fmtSolver(a.k)).localeCompare(solverSortKey(fmtSolver(b.k)),'zh-Hans-CN'));
    } else {
      arr.sort((a,b)=>b.rate-a.rate||b.total-a.total);
    }
    const top = arr.slice(0,20);
    if(top.length===0){
      document.getElementById(elId).innerHTML = `<div style="color:#9aa4b2;font-size:12px;padding:10px;text-align:center">暂无数据</div>`;
      return;
    }
    document.getElementById(elId).innerHTML = `
      <table style="width:100%;font-size:12px;border-collapse:collapse">
        <tr style="background:#f3f6fb"><th style="text-align:left;padding:5px">${head}</th>
        <th>总接待</th><th>促成</th><th>促成率</th></tr>
        ${top.map(x=>{ const display = isSolver ? fmtSolver(x.k) : (x.k||'—');
          return `<tr class="rk-row" data-n="${esc(display)}" data-raw="${esc(x.k||'')}" style="cursor:pointer">
          <td style="padding:5px" title="原始 ID: ${esc(x.k||'')}">${esc(display)}</td>
          <td style="padding:5px;text-align:center">${x.total}</td>
          <td style="padding:5px;text-align:center">${x.conv}</td>
          <td style="padding:5px;text-align:center;font-weight:600;color:${x.rate>=30?'#0a8a3a':x.rate>=15?'#c8881a':'#999'}">${x.rate}%</td>
        </tr>`;}).join('')}
      </table>`;
    // 绑定点击：把筛选下拉同步设置为被点的接待人 / 标签
    document.querySelectorAll('#'+elId+' .rk-row').forEach(el=>{
      el.onclick = () => {
        const target = (el.dataset.raw || el.dataset.n || '').toString();
        const sel = document.getElementById(isSolver?'efSolver':'efTag');
        if(!sel) return;
        // 如果目标原始是数字 ID（即裸名），筛选时按 fmtSolver 后的展示值进行匹配
        const matchVal = isSolver ? fmtSolver(target) : target;
        let has = false;
        for(const opt of sel.options){ if(opt.value === matchVal){ has = true; break; } }
        if(has){
          // 多选模式：把已选项加入选择（用户可多选）
          const already = Array.from(sel.selectedOptions).map(o=>o.value);
          if(!already.includes(matchVal)){ sel.value = matchVal; /* single add to current selection */ }
          // 触发 onchange
          sel.dispatchEvent(new Event('change', {bubbles:true}));
        }
        document.getElementById('efDetailTbl').scrollIntoView({behavior:'smooth'});
      };
    });
  }

  // ---- v10.28.55：按日/周/月统计 ----
  function efRenderPeriod(byPeriod){
    if(!byPeriod) return;
    const rows = [
      ['昨日',     'yesterday', '←d', byPeriod.yesterday],
      ['今日',     'today',     'd', byPeriod.today],
      ['本周',     'this_week', 'w', byPeriod.this_week],
      ['本月',     'this_month','M', byPeriod.this_month],
      ['最近3天',  'last3d',    '3d', byPeriod.last3d],
      ['最近7天',  'last7d',    '7d',byPeriod.last7d],
      ['最近30天', 'last30d',   '30d',byPeriod.last30d],
      ['全部',     'all',       'Σ', byPeriod.all]
    ];
    document.getElementById('efPeriod').innerHTML = `
      <table style="width:100%;font-size:12px;border-collapse:collapse">
        <tr style="background:#f3f6fb">
          <th style="text-align:left;padding:5px">时段</th>
          <th>接待记录</th><th>促成记录</th><th>促成率</th><th>独立协议</th>
        </tr>
        ${rows.map(r=>{
          const total = r[3].total||0, conv = r[3].conv||0;
          const rate = total ? +(conv*100/total).toFixed(1) : 0;
          // 独立协议数需要 efDistCountByPeriod？这里直接用总/促成分子和部分窗口统计
          return `<tr><td style="padding:5px"><b>${r[0]}</b><span style="color:#9aa4b2;margin-left:6px">${r[2]}</span></td>
            <td style="padding:5px;text-align:center">${total}</td>
            <td style="padding:5px;text-align:center;color:#0a8a3a;font-weight:600">${conv}</td>
            <td style="padding:5px;text-align:center;font-weight:600;color:${rate>=30?'#0a8a3a':rate>=15?'#c8881a':'#999'}">${rate}%</td>
            <td style="padding:5px;text-align:center;color:#1F4E78">${(_byPeriodAidSums[r[1]]||0)}</td></tr>`;
        }).join('')}
      </table>`;
  }
  // 独立协议数（distinct aid）需要额外聚合一次
  const _byPeriodAidSums = {};
  (function(){
    const now = new Date();
    const todayKey = now.toISOString().slice(0,10);
    const _7dAgo = new Date(now.getTime()-7*86400e3).toISOString().slice(0,10);
    const _30dAgo = new Date(now.getTime()-30*86400e3).toISOString().slice(0,10);
    const dow = (now.getDay()+6)%7;
    const monKey = new Date(now.getTime()-dow*86400e3).toISOString().slice(0,10);
    const monthKey = todayKey.slice(0,7)+'-01';
    const sum = (filterFn)=>{
      const s=new Set();
      for(let i=0;i<efFiltered.length;i++){
        const r=efFiltered[i]; const d=(r.time||'').slice(0,10);
        if(!d || !r.aid) continue;
        if(filterFn(d)) s.add(r.aid);
      }
      return s.size;
    };
    _byPeriodAidSums.today      = sum(d=>d===todayKey);
    _byPeriodAidSums.this_week  = sum(d=>d>=monKey && d<=todayKey);
    _byPeriodAidSums.this_month = sum(d=>d>=monthKey && d<=todayKey);
    _byPeriodAidSums.last7d     = sum(d=>d>=_7dAgo && d<=todayKey);
    _byPeriodAidSums.last30d    = sum(d=>d>=_30dAgo && d<=todayKey);
    _byPeriodAidSums.all        = sum(()=>true);
  })();

  // ---- 时间分布 ----
  function efRenderDist(cnt){
    const keys=['0d','1d','3d','7d','15d','30d','90d+'];
    const mx = Math.max(1, ...keys.map(k => cnt[k]||0));
    document.getElementById('efDist').innerHTML = keys.map(k=>`
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:5px;font-size:12px">
        <span style="width:40px;color:#555">${k}</span>
        <span style="flex:1;background:#eef1f5;border-radius:4px;height:16px;overflow:hidden">
          <span style="display:block;width:${Math.max(2,(cnt[k]||0)/mx*100)}%;height:100%;background:#0a8a3a"></span></span>
        <span style="width:50px;text-align:right;color:#333">${cnt[k]||0}</span>
      </div>`).join('');
  }

  // v10.28.55：aid → 电池位置信息（从 DATA.rows 读取 compact 写入的字段），用于明细行展示徽章
  const _aidToStorage = {};
  if(DATA && DATA.rows){
    DATA.rows.forEach(x=>{
      if(x && x.battery_in_storage){
        _aidToStorage[x.id] = {in_storage:true, loc:x.battery_in_storage_loc||'', reason:x.battery_in_storage_reason||''};
      }
    });
  }
  // v10.28.55：明细行附「电池状态徽章」，电池已不在用户手中时显示醒目红标
  function _storageBadge(r){
    const info = _aidToStorage[r.aid];
    if(!info || !info.in_storage) return '';
    return `<span title="${esc(info.reason||'')} → ${esc(info.loc||'')}" style="display:inline-block;background:#fee2e2;color:#b91c1c;font-size:10px;padding:1px 6px;border-radius:9px;margin-left:4px;cursor:help">电池不在手中</span>`;
  }

  // ---- 明细表 ----
  function efRenderDetail(){
    const per=50, tot=efFiltered.length;
    const pages=Math.max(1,Math.ceil(tot/per));
    if(efPage>pages) efPage=pages;
    const slice=efFiltered.slice((efPage-1)*per, efPage*per);
    document.getElementById('efCount').textContent=`共 ${tot} 条`;
    document.getElementById('efDetailBody').innerHTML = slice.map((r,i)=>{
      const g=GRADES[r.grade]||GRADES.S6;
      return `<tr class="ef-tr" data-i="${(efPage-1)*per+i}" style="cursor:pointer;border-bottom:1px solid #eef1f5">
        <td style="padding:5px;font-family:monospace;font-size:12px;color:#1F4E78">${esc(r.uid||'—')}</td>
        <td style="padding:5px;font-family:monospace;font-size:12px">${esc(r.phone||'—')}</td>
        <td style="padding:5px;font-family:monospace;font-size:12px;color:#1F4E78">${esc(r.aid||'—')}</td>
        <td style="padding:5px;white-space:nowrap">${esc(r.time)}</td>
        <td style="padding:5px">${esc(((r.solvers && r.solvers.length) ? r.solvers : [r.solver]).map(fmtSolver).filter(Boolean).join('、') || '—')}</td>
        <td style="padding:5px;font-size:11px;color:#666">${esc((r.tags||[]).join('、'))}</td>
        <td style="padding:5px;text-align:center">${esc(r.status)}</td>
        <td style="padding:5px;white-space:nowrap">${esc(r.first||'—')}</td>
        <td style="padding:5px;text-align:center">${r.delta==null?'—':(r.delta<1?'当日':r.delta.toFixed(1)+'d')}</td>
        <td style="padding:5px;white-space:nowrap;font-size:11px">${esc(r.bct_full||r.bct||'—')}${_storageBadge(r)}</td>
        <td style="padding:5px;text-align:center"><span style="background:${g.c};color:${['S5'].includes(r.grade)?'#333':'#fff'};
          padding:2px 7px;border-radius:10px;font-size:11px;white-space:nowrap">${g.n}</span></td>
        <td style="padding:5px;font-size:11px">${esc(r.pid||'—')}</td>
        <td style="padding:5px;font-size:11px;color:#666;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(r.detail)}</td>
      </tr>`;
    }).join('') || `<tr><td colspan="13" style="padding:20px;text-align:center;color:#999">当前筛选无数据</td></tr>`;
    // 分页
    document.getElementById('efDetailPager').innerHTML = tot>per ? `
      <button class="btn" ${efPage<=1?'disabled':''} data-p="${efPage-1}">上一页</button>
      <span style="margin:0 8px;font-size:12px">第 ${efPage}/${pages} 页</span>
      <button class="btn" ${efPage>=pages?'disabled':''} data-p="${efPage+1}">下一页</button>` : '';
    document.querySelectorAll('#efDetailPager button').forEach(b=>{
      b.onclick=()=>{ efPage=+b.dataset.p; efRenderDetail(); };
    });
    // 行点击 → 展开时间轴
    document.querySelectorAll('#efDetailBody .ef-tr').forEach(tr=>{
      tr.onclick=()=>{
        const r=efFiltered[+tr.dataset.i]; if(!r) return;
        const nx=tr.nextElementSibling;
        if(nx&&nx.dataset.exp==='1'){ nx.remove(); return; }
        const g=GRADES[r.grade]||GRADES.S6;
        const tr2=document.createElement('tr'); tr2.dataset.exp='1';
        tr2.innerHTML=`<td colspan="13" style="background:#f8fafc;padding:12px">
          <div style="font-size:12px;line-height:1.9">
            <b>时间轴：</b>
            <span style="color:#1F4E78">接待 ${esc(r.time)}</span> →
            <span style="color:${r.first?'#0a8a3a':'#999'}">${r.first?'首次借出 '+esc(r.first):'接待后无借出'}</span> →
            <span style="color:#666">末次流通 ${esc(r.bct_full||r.bct||'—')}</span>
            ${r.delta!=null?` <span style="color:#0a8a3a">（第 ${r.delta<1?'当日':r.delta.toFixed(1)+' 天'}）</span>`:''}
          </div>
          <div style="font-size:12px;margin-top:6px"><b>判定依据：</b>
            <span style="background:${g.c};color:#fff;padding:2px 7px;border-radius:10px">${g.n}</span>
            ${r.grade==='S7'?'协议已退订，不再区分是否换电':CONV.includes(r.grade)?
              `接待后 ${r.delta<1?'当日':r.delta.toFixed(1)+' 天'}内发生「柜内借出电池」→ 计为促成`:
              '接待后至今未发生借出 → 未促成'}
          </div>
          <div style="font-size:12px;margin-top:6px;color:#555"><b>接待内容：</b>${esc(r.detail||'—')}</div>
        </td>`;
        tr.parentNode.insertBefore(tr2, tr.nextSibling);
      };
    });
  }

  // ---- 导出 CSV ----
  // v10.28.55：明细表头调整后，导出列同步更新（用户ID/手机号/协议ID 在前）
  function efExport(){
    const head=['用户ID','用户手机号','协议ID','接待时间','接待人','标签','协议状态',
                 '首次借出时间','第N天换电','末次流通','效果档位','效果','产品ID','接待内容'];
    // v10.28.55：接待人字段用 fmtSolver 兜底（数字 0-19 → 员工#N），保证导出文件直接可读
    const rows=efFiltered.map(r=>[r.uid||'',r.phone||'',r.aid||'',r.time,
      ((r.solvers && r.solvers.length) ? r.solvers : [r.solver]).map(fmtSolver).filter(Boolean).join('、') || '—',
      (r.tags||[]).join('、'),r.status,
      r.first||'',(r.delta==null?'':(r.delta<1?'当日':r.delta.toFixed(2))),(r.bct_full||r.bct||''),
      r.grade,(GRADES[r.grade]||{}).n||'',r.pid,r.detail]);
    const csv=[head,...rows].map(r=>r.map(c=>`"${String(c==null?'':c).replace(/"/g,'""')}"`).join(',')).join('\r\n');
    const blob=new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8;'});
    const a=document.createElement('a');
    a.href=URL.createObjectURL(blob);
    a.download=`回访效果明细_${efFiltered.length}条_${Date.now()}.csv`;
    a.click();
  }

  // ---- 主渲染 ----
  let efGradeSet=null;   // 多选档位（KPI/漏斗点击时设置）
  window.renderEffect=function(keepGrade){
    try{
      efFillOpts(efSource());
      efApplyFilter();
      if(efGradeSet){ efFiltered=efFiltered.filter(r=>efGradeSet.includes(r.grade)); efGradeSet=null; }
      // v10.28.55：单次遍历聚合 + 修复联动 + 数据就绪度横幅
      const agg = efAggregate();
      efRenderKpi(agg.t, agg.distinctTotal, agg.distinctConv, agg.c30, agg.buckets.S6||0, agg.buckets.S7||0, agg.buckets.S10||0);
      efRenderFunnel(agg.buckets);
      efRenderDist(agg.dist);
      efRenderPeriod(agg.byPeriod);
      efRenderRank(agg.bySolver, 'efSolverRank', '接待人');
      efRenderRank(agg.byTag,    'efTagRank',    '标签');
      efRenderDetail();
      efRenderReadyBanner();
    }catch(e){ console.error('renderEffect error', e); }
  };

  // ---- v10.28.55：数据就绪度横幅（顶部明显提示当前 records.json 是否被新版回填）----
  function efRenderReadyBanner(){
    const el = document.getElementById('efReady');
    if(!el) return;
    const m = (DATA && DATA._meta) || {};
    const ver = m.build_lists_version || '未知';
    const ready = !!m.effect_ready;
    const rr = (m.effect_ready_rows||0);
    const tr = (m.reception_detail_rows||0);
    const bg = ready ? '#fff7e6' : '#fde8e8';
    const bd = ready ? '#f3b441' : '#d2603a';
    const fg = ready ? '#7a5a18' : '#7a2b18';
    el.style.background = bg;
    el.style.border = `1px solid ${bd}`;
    el.style.color = fg;
    el.style.padding = '8px 12px';
    el.style.borderRadius = '6px';
    el.style.marginBottom = '10px';
    el.style.fontSize = '12px';
    el.innerHTML = ready
      ? `📊 <b>数据版本 ${esc(ver)}</b> · 接待明细 ${tr} 条 · 其中已打档 ${rr} 条 · 效果就绪 ✅<br>
         <span style="color:#888">筛选改变会自动重新统计 KPI / 漏斗 / 排行；点击行可看判定依据</span>`
      : `⚠️ <b>数据版本 ${esc(ver)}</b> · 当前 <b>所有接待明细 effect_grade 都为空</b>（${tr} 条）。<br>
         <b>原因：</b>records.json 是旧版本生成的，没有写 effect_grade。<br>
         <b>解决：</b>点击顶部「同步数据库」按钮（或重启服务后等自动同步），新版 v10.28.55 会给每条接待打 9 档效果标签。<br>
         <span style="color:#888">已自动降级：S6 在租沉默 兜底展示，但漏斗无真实促成数据。</span>`;
  }

  // ---- 事件绑定 ----
  function efBind(){
    ['efDateFrom','efDateTo','efSolver','efTag','efGrade','efStatus'].forEach(id=>{
      const el=document.getElementById(id); if(!el) return;
      el.onchange=()=>{ efGradeSet=null; renderEffect(); };
    });
    // v10.28.55：接待人 / 标签 多选下拉的「全选 / 清空」快捷按钮 ——
    //                操作完 select 后立刻刷新 chip 显示
    document.querySelectorAll('.ef-multiselect [data-act]').forEach(btn=>{
      btn.onclick=()=>{
        const el=document.getElementById(btn.dataset.sel); if(!el) return;
        const all = btn.dataset.act==='all';
        Array.from(el.options).forEach(o=>{ if(o.value!=='') o.selected=all; });
        // 找到 chip 容器刷新显示
        const box = el.closest('.ef-multiselect');
        if(box && box._renderChips) box._renderChips();
        efGradeSet=null; renderEffect();
      };
    });
    const rs=document.getElementById('efReset');
    if(rs) rs.onclick=()=>{
      ['efDateFrom','efDateTo','efSolver','efTag','efGrade','efStatus'].forEach(id=>{
        const el=document.getElementById(id);
        if(!el) return;
        if(el.tagName === 'SELECT' && el.multiple){
          Array.from(el.options).forEach(o=>{ o.selected = false; });
          const box = el.closest('.ef-multiselect');
          if(box && box._renderChips) box._renderChips();
        } else {
          el.value = '';
        }
      });
      efGradeSet=null; efPage=1; renderEffect();
    };
    const ex=document.getElementById('efExportCsv');
    if(ex) ex.onclick=efExport;
    const ex2=document.getElementById('efExportXlsx');
    if(ex2) ex2.onclick=()=>{ if(window.__SERVE__){
      // v10.28.55：与 CSV 同步，用户ID/手机号/协议ID 排前三
      const head=['用户ID','用户手机号','协议ID','接待时间','接待人','标签','协议状态',
                  '首次借出时间','第N天换电','末次流通','效果档位','效果','产品ID','接待内容'];
      // v10.28.55：XLSX 同步用 fmtSolver
      const rows=efFiltered.map(r=>[r.uid||'',r.phone||'',r.aid||'',r.time,
        ((r.solvers && r.solvers.length) ? r.solvers : [r.solver]).map(fmtSolver).filter(Boolean).join('、') || '—',
        (r.tags||[]).join('、'),r.status,
        r.first||'',(r.delta==null?'':(r.delta<1?'当日':r.delta.toFixed(2))),(r.bct_full||r.bct||''),
        r.grade,(GRADES[r.grade]||{}).n||'',r.pid,r.detail]);
      fetch('/api/export_analysis_xlsx',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({name:`回访效果明细_${efFiltered.length}条`,head,rows,numericCols:[]})
      }).then(r=>r.blob()).then(b=>{
        const a=document.createElement('a'); a.href=URL.createObjectURL(b);
        a.download=`回访效果明细_${efFiltered.length}条.xlsx`; a.click();
      }).catch(()=>alert('Excel 导出失败，请改用 CSV 导出'));
    } else { alert('Excel 导出需通过本地服务使用'); } };
  }
  efBind();
})();
</script>
</body></html>"""

html = (HTML.replace('__COLS__', COLS_JSON)
            .replace('__DATA__', DATA_JSON)
            .replace('__DATA_SUMMARY__', RECORDS_SUMMARY_JSON)
            .replace('__PHONE_FB__', _PHONE_FB_JSON)
            .replace('__VTAG__', __VERSION__, 1))
# 预填最新的更新直链，方便用户无需手填；只取第一个非注释、非空行的真直链
try:
    _lines = open(os.path.join(BASE, 'update_url.txt'), encoding='utf-8').read().splitlines()
    _upd = ''
    for _ln in _lines:
        _s = _ln.strip()
        if not _s or _s.startswith('#') or _s.startswith('//'):
            continue
        _upd = _s
        break
    html = html.replace('__DEFAULT_UPDATE_URL__', _upd or '')
except Exception:
    html = html.replace('__DEFAULT_UPDATE_URL__', '')
open(os.path.join(BASE, 'out', 'followup_dashboard.html'),'w',encoding='utf-8').write(html)
print('dashboard bytes:', len(html))
