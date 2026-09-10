# -*- coding: utf-8 -*-
# lowfreq_local · 本地 HTTP 服务（v10.21.6 · 2026-08-21）
#   v10.21.6：修复「同事同步数据库/追加排班，主服务器看不到」——数据本就在主服务器磁盘，只是 UI 缺实时通知。
#             新增 DATA_VERSION 全局计数器 + /api/version 端点：run_sync/_redispatch/_save_assignment/_reassign/
#             _cancel_solver/_clear_assignments/_clear_history 等写操作后 bump_data_version()；
#             前端每 5s 轮询 /api/version，变化即自动 loadDispatch() 刷新（主服务器与所有客户端同步可见）。
#   v10.21.5：修复「电量显示不是当前的」——build_lists 快照电量滞后于服务台实时电量。
#             新增 /api/battery_now?sn=... 端点，按 SN 实时查 cb_battery_status 最新一条 power（同服务台口径），
#             前端 dispatch 系列视图首屏+每 30s 增量轮询，按 SN 覆盖 dData.items 的 soc/onl，覆盖后即 render。
#   v10.21.4：修复「同网段同事打不开链接」——
#             1) get_lan_ip 改为 get_lan_ips，枚举全部网卡 IPv4（不再只取 connect(8.8.8.8) 的出口 IP，
#                避免 VPN 虚拟网卡 IP 被当作局域网地址）；过滤回环/APIPA(169.254)/CGNAT(100.64-127)，
#                按私有地址优先级排序返回多个候选，前端把候选链接全列出，同事哪个能开用哪个。
#             2) 新增 ensure_firewall_rule：启动时尝试 netsh 放行 TCP 8173 入站（需管理员权限，失败提示手动放行）。
#   v10.21.3：修复「未自动打开看板」——pythonw(run_silent.bat) 下 webbrowser.open 静默失败，
#             main() 改用平台原生 _open_browser()（Windows 优先 os.startfile，再回退 webbrowser / cmd start），
#             并先以后台线程启动 HTTP 服务、端口就绪后再打开，避免打开瞬间服务尚未 accept。
#   v10.21：_save_staff 增加 user_permissions（姓名→可见模块+可同步）持久化，支撑按人权限与 ?user= 专属链接。
#   v10.20：
#     - 协议状态文字全站统一：「生效中 / 欠租 / 退订中」（不再叫「正常」）。
#     - 新增「当前手机号」字段：5 个菜单（全部活跃协议/欠租催收/低频用户/回访排班/回访调度）展示。
#       后端 build_lists.py 按 user_id 查 cb_user.mobile / cb_user.phone / cb_user_mobile（3 档 fallback）。
#     - 追加排班重构：mode='extra' 分支 + extra_solvers(dict{name:quota})，仅对本次新增人员按配额分配，
#       原名单完全保留，避免单人回访数量翻倍。
#     - db_conf.json 新增 recent_swap_filter_days 配置项（默认 0 = 不过滤；想要"近 N 天换电不进回访"
#       就改成 15，立即生效无需重打包）。
#   v10.19.2：「标记为无需回访」下拉新增「空号联系不上」「系统数据错误·4814电池」两个 reason。
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
"""
低频看板 · 本地服务模式（在你的电脑上常驻运行，支持内网访问）
============================================================
双击 run_sync.bat 会启动本脚本：监听所有网卡(0.0.0.0:8173)提供看板，
本机访问 http://127.0.0.1:8173，内网同事访问 http://<本机内网IP>:8173；
并暴露 /sync 接口，让看板内「[SYNC] 同步数据库」按钮一键重新连库刷新；
另暴露 /api/* 接口支撑「回访排班」的自动分配、贴标签、+N天再次回访。

数据完全在本机/内网：浏览器 <-> 本脚本 <-> 阿里云 ADB，不经过任何云沙箱。
关闭这个黑色窗口（或 Ctrl+C）即停止服务。
"""
import os
import re
import sys
import json
import time
import threading
import webbrowser
import hashlib
import secrets
import subprocess
import urllib.request
import shutil
import io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from assign import (load_config, create_recall, run_assignment, UNREACHABLE,
                    auto_update_visit_status, get_replace_candidates, replace_assignment,
                    REC_CATEGORIES, NEED_RECALL_CATS, DEFAULT_CAT, load_categories, classify_recall,
                    load_no_followup_aids, NOFOLLOWUP_FILE)
from auto_update import extract_and_merge

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import env

# v10.28.55：Excel 导出依赖 openpyxl（已在 env.ensure_deps 声明）。缺失时仅导出接口报错，不影响服务启动。
try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    _HAS_OPENPYXL = True
except Exception:
    Workbook = None
    _HAS_OPENPYXL = False

SERVE_VERSION = 'v10.28.57'  # v10.28.57：性能专项——看板 HTML 2.1MB（列式编码）+ dashboard 走 gzip 并缓存压缩结果；assign 侧 records.json 内存缓存

# v10.28.55：服务健康诊断工具，供 start.py / 外部脚本检测 serve 是否真的在运行。
SERVE_STATUS_FILE = os.path.join(BASE, "out", "_serve_status.json")


def _write_serve_status(ok, port=0, error=None):
    """写一份"服务状态"到 out/_serve_status.json，供 start.py / troubleshoot.bat 诊断。

    ok=False 通常意味着服务没起来（端口未 bind），start.py 检测到后会打印原因给用户。
    """
    try:
        os.makedirs(os.path.dirname(SERVE_STATUS_FILE), exist_ok=True)
        with open(SERVE_STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump({"ok": bool(ok), "port": int(port or 0),
                       "error": error or "", "version": SERVE_VERSION,
                       "ts": int(time.time())}, f, ensure_ascii=False)
    except Exception:
        pass


def _pause_for_user(seconds):
    """让错误信息在窗口停留 N 秒。仅在 stdin 是 tty 时才交互等待（detached 进程 stdin=None）。
    v10.28.55：解决 detached 模式下 input() 立刻 EOF → serve 静默退出 → 用户看不到任何错误的根因。
    """
    try:
        if sys.stdin is not None and sys.stdin.isatty():
            try:
                input("按回车退出…")
            except Exception:
                time.sleep(seconds)
        else:
            time.sleep(seconds)
    except Exception:
        try:
            time.sleep(seconds)
        except Exception:
            pass



def load_no_followup_list():
    if not os.path.exists(NOFOLLOWUP_FILE):
        return []
    try:
        return json.load(open(NOFOLLOWUP_FILE, encoding='utf-8'))
    except Exception:
        return []


def save_no_followup_list(lst):
    os.makedirs(os.path.dirname(NOFOLLOWUP_FILE), exist_ok=True)
    json.dump(lst, open(NOFOLLOWUP_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
PORT = 8173
LISTEN_PORT = PORT  # 实际监听端口（端口被占用时会递增），供 /api/lan_info 返回

STEPS = [
    ("连库抽数 → out/records.json", "build_lists.py"),
    ("并入短信 Excel（按手机号）", "merge_sms_excel.py"),
    ("生成看板 HTML", "gen_dashboard.py"),
    ("导出空号/停机专项清单 Excel", "export_special_lists.py"),
    # v10.12 起：回访名单改为手动生成（用户在「回访排班」Tab 选人员+配接待量+选电池产品后一键生成）
]

sync_state = {
    "running": False,
    "step": 0,
    "total": len(STEPS),
    "log": [],
    "done": False,
    "error": None,
    "raw_stderr": "",      # 最后一步的完整 stderr，供前端展开查看
    "finished_at": None,
}

# v10.21.6：数据版本号——任何对 out/（records.json / assignments.json）的写操作完成后 +1，
# 主服务器与各客户端前端轮询 /api/version，发现变化即自动 loadDispatch() 刷新，
# 解决「同事同步数据库/追加排班，主服务器看不到」的问题（数据本就在主服务器磁盘，只是 UI 缺实时通知）。
DATA_VERSION = 0

# ===== v10.28.55：token 鉴权（后端硬拦截，非前端隐藏） =====
# 旧版 ?user=姓名 明文链接已停用（任何人可伪造）。现改为 staff_auth.json 中的随机 token，
# 白名单外一律 403。scope 为数据范围（"全部" 或 城市关键词数组）。
AUTH_FILE = os.path.join(BASE, "staff_auth.json")
# v10.28.55：首次安装种子（默认账号模板）。仅用于「本地 staff_auth.json 缺失时」的兜底复制，
# 永远不参与运行期鉴权；打包时只分发 seed，不打包真实 staff_auth.json（避免手动解压覆盖真实凭证）。
AUTH_SEED = os.path.join(BASE, "staff_auth.seed.json")


def load_auth():
    """读取权限配置；缺省返回空结构（所有访问均 403）。"""
    fp = AUTH_FILE
    if not os.path.exists(fp):
        return {"admin_token": "", "users": []}
    try:
        obj = json.load(open(fp, encoding="utf-8"))
        if not isinstance(obj, dict):
            return {"admin_token": "", "users": []}
        obj.setdefault("admin_token", "")
        obj.setdefault("users", [])
        return obj
    except Exception:
        return {"admin_token": "", "users": []}


def ensure_auth_file():
    """v10.28.55：登录凭证持久化兜底。

    规则（首次安装 vs 升级分流）：
      - 本地 staff_auth.json 已存在  → 永远保留（升级路径，绝不触碰用户改过的账号密码）；
      - 本地 staff_auth.json 缺失    → 从 staff_auth.seed.json 复制一份默认凭证（首次安装路径）；
      - 连 seed 都没有              → 不创建，load_auth() 返回空结构（所有访问 403，等待管理员配置）。

    这一层保证：任何「升级 / 手动解压 / 误删」场景，只要本地曾有过凭证就不会被清空。
    """
    if os.path.exists(AUTH_FILE):
        return False  # 已存在 → 保留，什么都不做
    if not os.path.exists(AUTH_SEED):
        return False  # 连种子都没有，放弃（让前端走管理员配置流程）
    try:
        shutil.copy2(AUTH_SEED, AUTH_FILE)
        print(f"[auth] 首次安装：已从种子恢复默认登录凭证 → {AUTH_FILE}")
        return True
    except Exception as e:
        print(f"[auth] 从种子恢复凭证失败：{e}")
        return False


def resolve_auth(token):
    """token→权限对象；无效返回 None（调用方应返回 403）。"""
    if not token:
        return None
    auth = load_auth()
    if auth.get("admin_token") and token == auth["admin_token"]:
        return {"name": "管理员", "is_admin": True, "modules": ["all"],
                "can_sync": True, "scope": "全部", "phone_allow": "全部", "role": "管理员"}
    for u in auth.get("users", []):
        if u.get("token") and token == u["token"]:
            return {"name": u.get("name", ""), "is_admin": False,
                    "modules": u.get("modules") or [], "can_sync": bool(u.get("can_sync")),
                    "scope": u.get("scope", "全部"), "phone_allow": u.get("phone_allow", "全部"),
                    "role": u.get("role", "")}
    return None


# ===== v10.28.55：账号密码登录（密码哈希存储，不存明文） =====
def hash_password(pw, salt=None):
    """返回 (salt, hash)；哈希算法 sha256(salt + ':' + pw)。"""
    if salt is None:
        salt = secrets.token_hex(8)
    h = hashlib.sha256((salt + ":" + (pw or "")).encode("utf-8")).hexdigest()
    return salt, h


def verify_password(pw, salt, h):
    if not salt or not h:
        return False
    return hashlib.sha256((salt + ":" + (pw or "")).encode("utf-8")).hexdigest() == h


def gen_token():
    """生成难猜的随机 token（去掉易混淆字符）。"""
    cs = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
    s = "".join(cs[secrets.randbelow(len(cs))] for _ in range(16))
    return "lf_" + s


def _norm_scope(scope):
    if isinstance(scope, list):
        return [str(x).strip() for x in scope if str(x).strip()] or "全部"
    if isinstance(scope, str):
        v = scope.strip()
        return v if v else "全部"
    return "全部"


def _norm_phone_allow(phone_allow):
    if isinstance(phone_allow, list):
        return [str(x).strip() for x in phone_allow if str(x).strip()] or "全部"
    if isinstance(phone_allow, str):
        v = phone_allow.strip()
        return v if v else "全部"
    return "全部"


LOGIN_HTML = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>低频看板 · 登录</title>
<style>html,body{height:100%}body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:#0f172a;margin:0;display:flex;align-items:center;justify-content:center}
.box{background:#fff;border-radius:16px;padding:30px 32px;width:min(380px,92vw);box-shadow:0 10px 40px rgba(0,0,0,.35)}
h2{margin:0 0 4px;color:#1F4E78;font-size:20px}
.sub{font-size:12px;color:#888;margin-bottom:18px}
.f{margin-bottom:14px}
.f label{display:block;font-size:13px;color:#444;margin-bottom:5px}
.f input{width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid #d7dee7;border-radius:9px;font-size:14px;outline:none}
.f input:focus{border-color:#1F4E78}
.btn{width:100%;background:#1F4E78;color:#fff;border:none;padding:11px;border-radius:9px;font-size:14px;font-weight:700;cursor:pointer}
.btn:disabled{opacity:.6;cursor:default}
.msg{font-size:13px;margin-top:12px;min-height:18px}
.msg.err{color:#b91c1c}.msg.ok{color:#15803d}
.tip{font-size:12px;color:#999;margin-top:14px;line-height:1.6}
.tip code{background:#f1f5f9;padding:1px 5px;border-radius:4px}</style></head>
<body><div class="box">
<h2>低频用户 · 催收回访看板</h2>
<div class="sub">请登录后查看（账号由管理员在「人员权限」中创建）</div>
<form id="loginForm">
  <div class="f"><label>账号</label><input id="u" autocomplete="username" placeholder="请输入账号"></div>
  <div class="f"><label>密码</label><input id="p" type="password" autocomplete="current-password" placeholder="请输入密码"></div>
  <button class="btn" id="loginBtn" type="submit">登 录</button>
  <div class="msg" id="msg"></div>
  <div class="tip" id="recoverTip" style="display:none">
    忘记/丢失账号密码？<a href="javascript:recoverDefault()" style="color:#1F4E78">用默认凭证重置管理员</a>
  </div>
</form>
</div>
<script>
const form=document.getElementById('loginForm');
const msg=document.getElementById('msg');
const btn=document.getElementById('loginBtn');
const recoverTip=document.getElementById('recoverTip');
function recoverDefault(){
  if(!confirm('将把管理员账号恢复为默认账号密码（普通用户不受影响）。\\n恢复后请立即在「人员权限」中修改密码。\\n确认继续？')) return;
  fetch('/api/reset_admin_default',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})
    .then(r=>r.json()).then(j=>{
      if(j.ok){
        msg.className='msg ok';
        msg.textContent='已重置为默认凭证，请用默认账号登录（'+ (j.username||'admin') +'）。';
        recoverTip.style.display='none';
      } else {
        msg.className='msg err'; msg.textContent=(j.msg||'重置失败');
      }
    }).catch(e=>{ msg.className='msg err'; msg.textContent='网络错误：'+e; });
}
form.addEventListener('submit', async (e)=>{
  e.preventDefault();
  const u=document.getElementById('u').value.trim();
  const p=document.getElementById('p').value;
  if(!u||!p){ msg.className='msg err'; msg.textContent='请输入账号和密码'; return; }
  btn.disabled=true; msg.className='msg'; msg.textContent='登录中…';
  try{
    const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p})});
    const j=await r.json();
    if(j.ok && j.token){
      try{ sessionStorage.setItem('dash_token', j.token); }catch(e){}
      const base=location.pathname;
      location.href = base + (base.indexOf('?')>=0?'&':'?') + 'token=' + encodeURIComponent(j.token);
    } else {
      msg.className='msg err'; msg.textContent=(j.msg||'登录失败');
      recoverTip.style.display='block';   // v10.28.55：登录失败才显示「找回默认密码」
      btn.disabled=false;
    }
  }catch(err){
    msg.className='msg err'; msg.textContent='网络错误：'+err;
    recoverTip.style.display='block';
    btn.disabled=false;
  }
});
</script></body></html>"""

FORBIDDEN_HTML = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>无访问权限</title>
<style>body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:#f0f3f7;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
.box{background:#fff;border:1px solid #e1e6ec;border-radius:14px;padding:26px 30px;width:min(460px,92vw);box-shadow:0 4px 18px rgba(31,78,120,.08);text-align:center}
h2{color:#991b1b;margin:0 0 8px;font-size:19px}
p{font-size:13px;color:#555;line-height:1.7}.mono{font-family:Menlo,Consolas,monospace;background:#f3f5f8;padding:2px 6px;border-radius:5px}</style></head>
<body><div class="box">
<h2>⛔ 无访问权限</h2>
<p>无法查看或链接失效</p>
</div></body></html>"""


def bump_data_version():
    """标记 out/ 数据已变化，通知所有前端自动刷新。"""
    global DATA_VERSION
    DATA_VERSION += 1

FALLBACK_HTML = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>低频看板 · 首次同步</title>
<style>body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:#f0f3f7;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
.box{background:#fff;border:1px solid #e1e6ec;border-radius:14px;padding:26px 30px;width:min(480px,92vw);box-shadow:0 4px 18px rgba(31,78,120,.08)}
h2{color:#1F4E78;margin:0 0 8px;font-size:19px}
.log{background:#0f172a;color:#cbd5e1;font-size:12px;line-height:1.6;padding:10px 12px;border-radius:8px;max-height:240px;overflow:auto;white-space:pre-wrap;font-family:Menlo,Consolas,monospace;margin-top:10px}
.bar{height:6px;background:#e6edf5;border-radius:4px;overflow:hidden;margin:12px 0}
.bar i{display:block;height:100%;background:#1F4E78;width:0;transition:width .4s}
.btn{margin-top:14px;background:#1F4E78;color:#fff;border:none;padding:10px 18px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:700}
.hint{font-size:12px;color:#888;margin-top:10px}.err{border:1px solid #fca5a5;background:#fef2f2;color:#991b1b;padding:10px;border-radius:8px;margin-top:10px;font-size:12px;white-space:pre-wrap;max-height:260px;overflow:auto;display:none}.show{display:block}</style></head>
<body><div class="box">
<h2>首次同步中…</h2>
<div>正在连接数据库生成看板，约需 1~3 分钟，完成后将自动刷新。</div>
<div class="bar"><i id="bar"></i></div>
<div class="log" id="log">准备中…</div>
<div id="errBox" class="err"></div>
<div class="hint">如需手动触发：<button class="btn" id="syncBtn">[SYNC] 立即同步数据库</button> <button class="btn" id="copyBtn" style="display:none;background:#555">[COPY] 复制错误日志</button></div>
</div>
<script>
let lastErr='';
async function poll(){
  try{
    const st=await fetch('/sync_status').then(r=>r.json());
    document.getElementById('log').textContent=(st.log||[]).join('\\n')||'同步中…';
    const pct=st.total?Math.round(st.step/st.total*100):(st.running?10:100);
    document.getElementById('bar').style.width=pct+'%';
    if(!st.running && st.finished_at){
      if(st.error){
        lastErr=(st.log||[]).join('\\n')+'\\n\\n===== 详细错误 =====\\n'+(st.raw_stderr||'');
        document.getElementById('log').textContent+='\\n\\n[FAIL] 同步失败：'+st.error;
        document.getElementById('errBox').textContent=lastErr;
        document.getElementById('errBox').classList.add('show');
        document.getElementById('copyBtn').style.display='inline-block';
      }else { location.reload(); }
      return;
    }
  }catch(e){}
  setTimeout(poll,3000);
}
poll();
document.getElementById('syncBtn').onclick=async()=>{ await fetch('/sync',{method:'POST'}); };
document.getElementById('copyBtn').onclick=async()=>{
  try{ await navigator.clipboard.writeText(lastErr); alert('已复制，请粘贴给技术支持'); }catch(e){ alert('复制失败，请手动选中错误框内容复制'); }
};
</script>
</body></html>"""


DEFAULT_TAGS = {
    "levels": [
        {"id": "L1", "name": "一级", "options": ["换电柜咨询类", "换电柜操作类", "沉默用户回访", "充电宝操作类", "充电器咨询类"]},
        {"id": "L2", "name": "二级", "options": ["换电柜硬件类", "换电柜退款类", "新增用户回访", "充电宝硬件类", "无效咨询"]},
        {"id": "L3", "name": "三级", "options": ["换电柜软件类", "逾期用户回访", "充电宝咨询类", "充电宝软件类", "即将到期用户外呼"]},
    ],
    "outcomes": ["外呼未接通", "已接通", "用户表示继续", "准备退订", "电池丢失",
                 "表明身份挂机", "电池已归还", "非本人接听", "门店/公关类", "其他"],
}


def run_sync():
    sync_state["running"] = True
    sync_state["done"] = False
    sync_state["error"] = None
    sync_state["raw_stderr"] = ""
    sync_state["log"] = []
    sync_state["finished_at"] = None
    error_log_path = os.path.join(BASE, "out", "sync_error.log")
    try:
        for i, (name, script) in enumerate(STEPS, 1):
            sync_state["step"] = i
            sync_state["log"].append(f"[{i}/{len(STEPS)}] {name} ...")
            r = subprocess.run(
                [sys.executable, os.path.join(BASE, script)],
                cwd=BASE, capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            out = (r.stdout or "").strip()
            err = (r.stderr or "").strip()
            if out:
                sync_state["log"].append(out[-1500:])
            if r.returncode != 0:
                sync_state["log"].append(f"[FAIL] 第 {i} 步失败（{script} 返回码 {r.returncode}）")
                if err:
                    sync_state["log"].append(err[-2000:])
                    sync_state["raw_stderr"] = err
                sync_state["error"] = f"第 {i} 步失败（{script}）"
                # 写入错误日志，方便用户直接打开文件查看
                try:
                    os.makedirs(os.path.join(BASE, "out"), exist_ok=True)
                    with open(error_log_path, "w", encoding="utf-8") as f:
                        f.write(f"步骤 [{i}/{len(STEPS)}] {name} 失败\n脚本: {script}\n返回码: {r.returncode}\n\n")
                        f.write("===== stderr =====\n")
                        f.write(err)
                        f.write("\n===== stdout =====\n")
                        f.write(out)
                except Exception:
                    pass
                break
            sync_state["log"].append(f"[OK] 第 {i} 步完成")
        else:
            sync_state["done"] = True
            # 成功时清理旧错误日志
            try:
                if os.path.exists(error_log_path):
                    os.remove(error_log_path)
            except Exception:
                pass
    except Exception as e:
        sync_state["error"] = repr(e)
        sync_state["log"].append("[FAIL] 异常: " + repr(e))
    finally:
        sync_state["running"] = False
        sync_state["step"] = len(STEPS) if sync_state["done"] else sync_state["step"]
        sync_state["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        bump_data_version()  # 同步数据库（records.json 重建）后通知前端刷新


def get_lan_ips():
    """枚举本机所有非回环 IPv4，按"局域网可达性"排序，供同网段同事访问。

    关键：不再只取 connect(8.8.8.8) 的出口 IP——装了 VPN 时出口是 VPN 虚拟网卡，
    返回的是 VPN 内网地址，同事在真实 LAN 打不开。改为枚举所有网卡，过滤掉
    回环/APIPA(169.254)/CGNAT(100.64-127) 后按私有地址优先级排序返回多个候选。
    """
    import socket, subprocess, re, platform
    ips = set()
    # 兜底：出口探测（VPN 场景会误导，仅作最后兜底）
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    # 枚举所有网卡 IPv4
    try:
        if platform.system().lower().startswith("win"):
            out = subprocess.run(["ipconfig"], capture_output=True, text=True,
                                 encoding="gbk", errors="replace").stdout
            for m in re.finditer(r"IPv4[^\d]*(\d+\.\d+\.\d+\.\d+)", out):
                ips.add(m.group(1))
        else:
            out = subprocess.run(["ip", "-4", "addr"], capture_output=True, text=True,
                                 encoding="utf-8", errors="replace").stdout
            for m in re.finditer(r"inet (\d+\.\d+\.\d+\.\d+)", out):
                ips.add(m.group(1))
    except Exception:
        pass

    def _is_loopback(ip): return ip.startswith("127.")
    def _is_apipa(ip): return ip.startswith("169.254.")
    def _is_cgnat(ip):
        if ip.startswith("100."):
            return 64 <= int(ip.split(".")[1]) <= 127
        return False
    def _rank(ip):
        if ip.startswith("192.168."): return 0
        if ip.startswith("172."):
            return 1 if 16 <= int(ip.split(".")[1]) <= 31 else 4
        if ip.startswith("10."): return 2
        return 3

    cands = [ip for ip in ips if not _is_loopback(ip)]
    cands = [ip for ip in cands if not _is_apipa(ip) and not _is_cgnat(ip)]
    cands.sort(key=_rank)
    return cands or ["127.0.0.1"]


def get_lan_ip():
    """兼容旧调用：返回推荐的首选局域网 IP。"""
    return get_lan_ips()[0]


def ensure_firewall_rule(port):
    """尝试在 Windows 防火墙放行本服务入站（同事才能访问）。需管理员权限，失败则提示手动。

    v10.28.55：新增 profile=any（不限于"专用网络"，避免连上公共/来宾网络时规则不生效）；
    同时把实际端口写入 out/_serve_port.txt，供 open_firewall.bat 读取（端口漂移时仍可手动放行）。
    """
    if not sys.platform.startswith("win"):
        return
    try:
        os.makedirs(os.path.join(BASE, "out"), exist_ok=True)
        with open(os.path.join(BASE, "out", "_serve_port.txt"), "w") as _f:
            _f.write(str(port))
    except Exception:
        pass
    rule = "lowfreq_local_in"
    try:
        # 先删后加，避免重复运行报"已存在"
        subprocess.run(["netsh", "advfirewall", "firewall", "delete", "rule", f"name={rule}"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
        r = subprocess.run(
            ["netsh", "advfirewall", "firewall", "add", "rule", f"name={rule}",
             "dir=in", "action=allow", "protocol=TCP", f"localport={port}", "profile=any"],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode == 0:
            print(f"[OK] 已在 Windows 防火墙放行 TCP {port} 入站（规则名 {rule}），同网段同事可访问。")
        else:
            print(f"[WARN] 普通权限下防火墙未放行（需管理员）。正在尝试自动提权放行（会弹出一次 UAC，点「是」即可）…")
            _try_elevate_firewall(port)
    except Exception as e:
        print(f"[WARN] 防火墙处理异常：{e}")


def _try_elevate_firewall(port):
    """普通权限放行失败时，尝试以管理员身份运行 open_firewall.bat 自动放行（弹一次 UAC）。

    open_firewall.bat 已是 self-elevating 版：若当前已是管理员则直接放行，否则会再请求一次提权。
    这样双击 start.bat 启动服务时，无需用户手动右键管理员，也能完成防火墙放行。
    """
    if not sys.platform.startswith("win"):
        return
    try:
        bat = os.path.join(BASE, "open_firewall.bat")
        if not os.path.exists(bat):
            print(f"[WARN] 未找到 open_firewall.bat，无法自动提权放行。请手动以管理员运行 open_firewall.bat。")
            return
        # 先把实际端口写入 out/_serve_port.txt，供 open_firewall.bat 读取（端口漂移时仍准确）
        try:
            os.makedirs(os.path.join(BASE, "out"), exist_ok=True)
            with open(os.path.join(BASE, "out", "_serve_port.txt"), "w") as _f:
                _f.write(str(port))
        except Exception:
            pass
        # 用 powershell 以 RunAs 提权运行 open_firewall.bat
        ps = f'Start-Process -FilePath "{bat}" -Verb RunAs'
        subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(f"[提示] 已请求管理员放行防火墙（端口 {port}）。若弹出 UAC，请点「是」。")
        print(f"        放行后同网段同事即可访问；若仍打不开，请手动双击 open_firewall.bat（会自动请求管理员）。")
    except Exception as e:
        print(f"[WARN] 自动提权放行失败：{e}；请手动运行 open_firewall.bat（双击即可，会自动请求管理员）。")


def check_firewall_rule(port):
    """返回防火墙放行状态：True=已放行 / False=未放行 / None=无法判断（如非 Windows）。"""
    if not sys.platform.startswith("win"):
        return None
    try:
        r = subprocess.run(["netsh", "advfirewall", "firewall", "show", "rule", "name=lowfreq_local_in"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            return False
        out = r.stdout or ""
        return (f"localport={port}" in out) or (f"TCP {port}" in out) or (str(port) in out)
    except Exception:
        return None


# v10.28.55：看板 HTML 内存缓存。
# 背景：out/followup_dashboard.html 常达数十 MB，原先每个 HTTP 请求都完整 open().read() 一遍，
# 多人同时访问（同事 + 自己）时磁盘 IO 与内存分配叠加，页面长时间转圈。
# 现按「路径 + mtime」缓存原始 HTML，文件未变则直接复用；同步生成新 HTML 后 mtime 变化会自动失效。
_HTML_CACHE = {"path": None, "mtime": 0.0, "html": None}


def _read_dashboard_html(path):
    """带缓存读取看板 HTML（原始未注入版）。文件 mtime 未变则复用内存副本。"""
    try:
        mtime = os.path.getmtime(path)
    except Exception:
        mtime = 0.0
    if (_HTML_CACHE["path"] == path and _HTML_CACHE["mtime"] == mtime
            and _HTML_CACHE["html"] is not None):
        return _HTML_CACHE["html"]
    try:
        html = open(path, encoding="utf-8").read()
    except Exception:
        return None
    _HTML_CACHE["path"] = path
    _HTML_CACHE["mtime"] = mtime
    _HTML_CACHE["html"] = html
    return html


# v10.28.57：看板 HTML 的 gzip 结果缓存。
# 每请求压缩 2MB 文本约 200ms，多人访问时纯属浪费；按 (mtime + 长度 + 注入内容) 缓存。
_GZ_CACHE = {"key": None, "gz": None}


class Handler(BaseHTTPRequestHandler):
    # v10.28.55：大响应体（看板 HTML / JSON）超过该字节数才启用 gzip，
    # 小响应压缩反而浪费 CPU。16KB 是经验阈值。
    GZIP_MIN_BYTES = 16 * 1024

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        # v10.28.55：gzip 压缩 —— 看板 HTML 常达数十 MB，不压缩时内网同事
        # 通过 WiFi 加载会长时间转圈；压缩后体积通常降至 1/8 左右。
        ae = (self.headers.get("Accept-Encoding") or "") if hasattr(self, "headers") else ""
        if "gzip" in ae.lower() and len(body) >= self.GZIP_MIN_BYTES:
            try:
                import gzip as _gzip
                buf = io.BytesIO()
                with _gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=6,
                                    mtime=0) as gz:
                    gz.write(body)
                gz_body = buf.getvalue()
                if len(gz_body) < len(body):
                    self.send_response(code)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Encoding", "gzip")
                    self.send_header("Content-Length", str(len(gz_body)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(gz_body)
                    return
            except Exception:
                pass  # 压缩失败则退回原始发送
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        # v10.28.55：补 Content-Length，浏览器才能显示确定进度而不是一直转圈
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/dashboard"):
            self._serve_dashboard()
        elif path == "/sync_status":
            self._send(200, json.dumps(sync_state, ensure_ascii=False))
        elif path == "/sync":
            self._trigger_sync()
        elif path == "/api/assignments":
            self._api_get_assignments()
        elif path == "/api/tags":
            self._api_get_tags()
        elif path == "/api/rec_categories":
            self._api_get_rec_categories()
        elif path == "/api/no_followup":
            self._api_get_no_followup()
        elif path == "/api/staff":
            self._api_get_staff()
        elif path == "/api/auth":
            self._api_get_auth()
        elif path == "/api/history_dates":
            self._api_get_history_dates()
        elif path == "/api/history":
            self._api_get_history()
        elif path == "/api/lan_info":
            self._api_lan_info()
        elif path == "/api/me_token":
            self._api_me_token()
        elif path == "/api/list_backups":  # v10.28.55：列出 assignments.json 备份
            self._api_list_backups()
        elif path == "/api/battery_now":
            self._api_battery_now()
        elif path == "/api/version":
            self._send(200, json.dumps({"version": DATA_VERSION}, ensure_ascii=False))
        elif path == "/api/health":
            # v10.28.55：最小存活探测，供 start.py / troubleshoot.bat / 同事脚本判断"是不是我们的服务"
            self._send(200, json.dumps({"ok": True, "version": SERVE_VERSION,
                                        "port": LISTEN_PORT,
                                        "lan_ip": (get_lan_ips() or [""])[0]}, ensure_ascii=False))
        elif path == "/api/diag":
            # v10.28.55：同步前自检 + 端点存在性验证。
            # 如果当前 serve.py 没有 /sync 端点（如旧版本残留进程），返回 ok=False 让前端立即报错并提示重启服务。
            self._api_diag()
        elif path == "/api/force_run":
            self._api_force_run(body)

    def _mysql_conn(self):
        """复用 build_lists.py 的连库信息，返回 pymysql 连接（失败抛异常）。"""
        import pymysql
        conf_path = os.path.join(BASE, 'db_conf.json')
        if not os.path.exists(conf_path):
            raise RuntimeError('db_conf.json 缺失')
        conf = json.load(open(conf_path, encoding='utf-8'))
        host = os.environ.get('LF_DB_HOST', '').strip() or conf.get('intranet_host') or conf.get('host')
        if not host:
            raise RuntimeError('未配置 LF_DB_HOST / db_host')
        return pymysql.connect(
            host=host, port=conf.get('port', 3306), user=conf['user'],
            password=conf['password'], database=conf['database'],
            charset='utf8mb4', connect_timeout=conf.get('connect_timeout', 10),
            read_timeout=conf.get('read_timeout', 30),
            write_timeout=conf.get('write_timeout', 30),
            cursorclass=pymysql.cursors.DictCursor
        )

    def _api_battery_now(self):
        """按电池 SN 实时查最新电量（cb_battery_status 最新一条 power），前端用于覆盖快照值。
        支持一次查多个 sn（?sn=A,B,C），返回 dict[sn]={soc, online, soc_time, vol, cur, src}"""
        try:
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            sns = qs.get('sn', [])
            sns = [s.strip() for s in (','.join(sns)).split(',') if s and s.strip()]
            sns = list(dict.fromkeys(sns))[:30]  # 去重+限 30 条防止滥用
            if not sns:
                self._send(400, json.dumps({"ok": False, "msg": "缺少 sn 参数"}, ensure_ascii=False))
                return
            out = {}
            try:
                conn = self._mysql_conn()
            except Exception as e:
                # 连库失败时，返回错误但不让前端卡死（用快照值显示）
                self._send(200, json.dumps({"ok": False, "msg": "db unavailable: " + str(e), "items": out}, ensure_ascii=False))
                return
            try:
                ph = ','.join(['%s'] * len(sns))
                with conn.cursor() as cur:
                    cur.execute(f"SELECT id, device_sn, online_status FROM cb_battery WHERE device_sn IN ({ph})", sns)
                    bat_rows = cur.fetchall()
                    sn2bid = {(r['device_sn'] or '').strip(): r['id'] for r in bat_rows}
                    sn2onl = {(r['device_sn'] or '').strip(): (r.get('online_status') or '') for r in bat_rows}
                    if sn2bid:
                        ids = list(sn2bid.values())
                        ph2 = ','.join(['%s'] * len(ids))
                        # 取每个 battery_id 的最新一条 status
                        cur.execute(
                            f"SELECT s.id, s.battery_id, s.power, s.voltage_in, s.current_in, s.`using`, s.create_time "
                            f"FROM cb_battery_status s INNER JOIN (SELECT battery_id, MAX(id) AS max_id FROM cb_battery_status WHERE battery_id IN ({ph2}) GROUP BY battery_id) m "
                            f"ON s.id=m.max_id", ids)
                        for r in cur.fetchall():
                            bid = r['battery_id']
                            # 反查 SN
                            for sn, bid2 in sn2bid.items():
                                if bid2 == bid:
                                    out[sn] = {
                                        'soc': r.get('power') if r.get('power') is not None else '',
                                        'online': sn2onl.get(sn, '') or '',
                                        'vol': r.get('voltage_in') if r.get('voltage_in') is not None else '',
                                        'cur': r.get('current_in') if r.get('current_in') is not None else '',
                                        'using': (r.get('using') or ''),
                                        'soc_time': str(r.get('create_time')) if r.get('create_time') else '',
                                        'src': 'cb_battery_status'
                                    }
                                    break
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
            self._send(200, json.dumps({"ok": True, "items": out}, ensure_ascii=False))
        except Exception as e:
            self._send(500, json.dumps({"ok": False, "msg": "battery_now 异常: " + str(e)}, ensure_ascii=False))
        else:
            self._send(404, json.dumps({"ok": False, "msg": "not found"}, ensure_ascii=False))

    def _api_diag(self):
        """v10.28.55：服务自检 + 端点存在性核对。供看板「同步」按钮预检，
        也供用户浏览器手动访问 http://127.0.0.1:8173/api/diag 排查「同步失败」。
        """
        try:
            from urllib.parse import urlparse, parse_qs
            # 1) 端点存在性：当前 serve.py 是否声明了 /sync 与 /sync_status 路由
            endpoints = {
                "sync_GET":       "/sync" in self._route_table(do_GET=True),
                "sync_POST":      "/sync" in self._route_table(do_GET=False),
                "sync_status":    "/sync_status" in self._route_table(do_GET=True),
                "api_diag":       True,  # 必然存在（自身）
                "api_health":     "/api/health" in self._route_table(do_GET=True),
            }
            # 2) 同步状态
            sync_running = bool(sync_state.get("running"))
            sync_done    = bool(sync_state.get("done"))
            sync_error   = sync_state.get("error")
            # 3) 网络信息
            lan = get_lan_ips() or [""]
            # 4) build_lists 产物是否就绪
            rec = os.path.join(BASE, "out", "records.json")
            html = os.path.join(BASE, "out", "followup_dashboard.html")
            db_conf = os.path.join(BASE, "db_conf.json")
            info = {
                "ok":          all(endpoints.values()),
                "version":     SERVE_VERSION,
                "port":        LISTEN_PORT,
                "lan_ip":      lan[0] if lan else "",
                "all_lan_ips": lan,
                "endpoints":   endpoints,
                "sync": {
                    "running":     sync_running,
                    "done":        sync_done,
                    "error":       sync_error,
                    "step":        sync_state.get("step", 0),
                    "total":       sync_state.get("total", 0),
                    "finished_at": sync_state.get("finished_at"),
                },
                "artifacts": {
                    "db_conf_exists":       os.path.exists(db_conf),
                    "records_exists":       os.path.exists(rec),
                    "records_size_kb":      (os.path.getsize(rec) // 1024) if os.path.exists(rec) else 0,
                    "dashboard_exists":     os.path.exists(html),
                    "dashboard_size_kb":    (os.path.getsize(html) // 1024) if os.path.exists(html) else 0,
                },
                "hints": self._diag_hints(endpoints),
            }
            self._send(200, json.dumps(info, ensure_ascii=False))
        except Exception as e:
            self._send(500, json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))

    def _route_table(self, do_GET=True):
        """v10.28.55：返回当前 Handler 已声明的路径集合，用于 _api_diag 自检。
        do_GET=True 取 do_GET 的路径表，False 取 do_POST 的路径表。
        """
        if do_GET:
            return {
                "/", "/dashboard", "/sync_status", "/sync",
                "/api/assignments", "/api/tags", "/api/rec_categories", "/api/no_followup",
                "/api/staff", "/api/auth", "/api/history_dates", "/api/history",
                "/api/lan_info", "/api/me_token", "/api/list_backups",
                "/api/battery_now", "/api/version", "/api/health", "/api/diag",
                "/api/force_run",
            }
        return {
            "/sync",  # 非 /api/ 路径也走 do_POST 触发同步
            "/api/assign", "/api/staff", "/api/tags", "/api/redispatch",
            "/api/restore_assignments", "/api/reassign", "/api/clear_history",
            "/api/clear_assignments", "/api/mark_visit", "/api/replace_candidates",
            "/api/replace_assignment", "/api/cancel_solver", "/api/self_update",
            "/api/ai_classify", "/api/mark_no_followup", "/api/no_followup_add",
            "/api/no_followup_remove", "/api/login", "/api/reset_admin_default",
            "/api/export_analysis_xlsx",
        }

    def _diag_hints(self, endpoints):
        """根据端点缺失情况，给出可执行的提示。"""
        h = []
        if not endpoints.get("sync_GET") or not endpoints.get("sync_POST"):
            h.append("当前 serve.py 缺少 /sync 端点。常见原因：升级后未重启本地服务。请双击 start.bat（推荐）或 run_serve.bat 重启。")
        if not endpoints.get("sync_status"):
            h.append("缺少 /sync_status 端点，同步进度无法轮询。同样需要重启服务。")
        if not h:
            h.append("服务正常。如仍同步失败，请查看 out/sync_error.log 中的具体错误信息。")
        return h

    def do_POST(self):
        if self.path.startswith("/api/"):
            self._api_post()
        else:
            self._trigger_sync()

    def _read_body(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except Exception:
            length = 0
        raw = self.rfile.read(length) if length else b""
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _api_get_assignments(self):
        fp = os.path.join(BASE, "out", "assignments.json")
        if not os.path.exists(fp):
            self._send(200, json.dumps({"items": []}, ensure_ascii=False))
            return
        # 返回前自动推断最新回访状态（基于 records.json）
        auto_update_visit_status()
        obj = json.load(open(fp, encoding="utf-8"))
        self._send(200, json.dumps(obj, ensure_ascii=False))

    def _api_get_staff(self):
        # 旧 dispatch 排班配置（staff 名单 / quotas 等），仍走 out/staff.json
        cfg = load_config()
        self._send(200, json.dumps(cfg, ensure_ascii=False))

    def _api_get_auth(self):
        # v10.28.55：权限配置（前端权限弹窗用）；剔除密码哈希，避免泄露
        auth = load_auth()
        safe = {"admin_token": auth.get("admin_token", ""), "admin_username": (auth.get("admin") or {}).get("username", ""), "users": []}
        for u in auth.get("users", []):
            safe["users"].append({
                "username": u.get("username", ""),
                "name": u.get("name", ""),
                "role": u.get("role", ""),
                "token": u.get("token", ""),
                "modules": u.get("modules") or [],
                "can_sync": bool(u.get("can_sync")),
                "scope": u.get("scope", "全部"),
                "phone_allow": u.get("phone_allow", "全部"),
            })
        self._send(200, json.dumps(safe, ensure_ascii=False))

    def _api_login(self, body):
        # v10.28.55：账号密码登录。成功返回该用户的 token（前端据此访问看板）。
        # 注意：body 由 _api_post 统一读取后传入，勿在此重复 _read_body()（会阻塞）。
        username = (body.get("username") or "").strip()
        pw = body.get("password") or ""
        auth = load_auth()
        # 1) 管理员账号
        adm = auth.get("admin") or {}
        if username and adm.get("username") and username == adm["username"]:
            if verify_password(pw, adm.get("pw_salt", ""), adm.get("pw_hash", "")):
                self._send(200, json.dumps({
                    "ok": True, "token": auth.get("admin_token") or "admin",
                    "name": "管理员", "is_admin": True, "role": "管理员",
                    "modules": ["all"], "can_sync": True, "scope": "全部", "phone_allow": "全部",
                }, ensure_ascii=False))
                return
        # 2) 普通用户
        for u in auth.get("users", []):
            if u.get("username") and username == u["username"]:
                if verify_password(pw, u.get("pw_salt", ""), u.get("pw_hash", "")):
                    self._send(200, json.dumps({
                        "ok": True, "token": u.get("token"),
                        "name": u.get("name", username), "is_admin": False,
                        "role": u.get("role", ""), "modules": u.get("modules") or [],
                        "can_sync": bool(u.get("can_sync")),
                        "scope": u.get("scope", "全部"), "phone_allow": u.get("phone_allow", "全部"),
                    }, ensure_ascii=False))
                    return
        self._send(200, json.dumps({"ok": False, "msg": "账号或密码错误"}, ensure_ascii=False))

    def _api_reset_admin_default(self, body):
        # v10.28.55：登录页「找回默认密码」兜底。
        # 把管理员账号恢复成 staff_auth.seed.json 中的默认账号/密码（仅 admin 字段，普通用户不动）。
        # 安全考量：本服务绑定 127.0.0.1 / 内网，属本地工具；该接口仅恢复默认、不泄露明文，
        # 且每次调用都写日志，便于事后追溯。若需更高安全，可在部署时删除本接口或加二次校验。
        if not os.path.exists(AUTH_SEED):
            self._send(200, json.dumps({"ok": False, "msg": "未找到默认凭证种子，无法恢复"}, ensure_ascii=False))
            return
        try:
            seed = json.load(open(AUTH_SEED, encoding="utf-8"))
        except Exception as e:
            self._send(200, json.dumps({"ok": False, "msg": "读取种子失败：" + str(e)}, ensure_ascii=False))
            return
        auth = load_auth()
        # 恢复 admin 的 username + 密码哈希（来自 seed）
        seed_admin = seed.get("admin") or {}
        adm = auth.setdefault("admin", {})
        if seed_admin.get("username"):
            adm["username"] = seed_admin["username"]
        if seed_admin.get("pw_salt"):
            adm["pw_salt"] = seed_admin["pw_salt"]
        if seed_admin.get("pw_hash"):
            adm["pw_hash"] = seed_admin["pw_hash"]
        # 同时恢复 admin_token（默认 token），避免旧 token 失效
        if seed.get("admin_token"):
            auth["admin_token"] = seed["admin_token"]
        json.dump(auth, open(AUTH_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"[auth] 管理员已恢复为默认凭证（用户名={adm.get('username')}），请尽快在「人员权限」中改密。")
        self._send(200, json.dumps({
            "ok": True,
            "msg": "管理员已恢复为默认账号密码，请使用默认凭证登录后尽快修改。",
            "username": adm.get("username", ""),
        }, ensure_ascii=False))
        return

    def _api_export_analysis_xlsx(self, body):
        # v10.28.55：低频用户数据分析 → Excel 导出（服务端用 openpyxl 生成 .xlsx 返回）。
        # 前端把筛选后的 {head, rows, numericCols} 以 JSON POST 过来，避免在浏览器端引入第三方库。
        if not _HAS_OPENPYXL or Workbook is None:
            self._send(500, json.dumps(
                {"ok": False, "msg": "服务端未安装 openpyxl，无法导出 Excel。请运行：python -m pip install openpyxl"},
                ensure_ascii=False))
            return
        try:
            name = (body.get("name") or "低频用户数据分析")
            head = body.get("head") or []
            rows = body.get("rows") or []
            numeric = set(int(x) for x in (body.get("numericCols") or []) if str(x).isdigit())
            wb = Workbook()
            ws = wb.active
            ws.title = "低频用户数据分析"
            # 表头
            ws.append([str(h) for h in head])
            hdr_fill = PatternFill("solid", fgColor="1F4E78")
            hdr_font = Font(bold=True, color="FFFFFF")
            for c in range(1, len(head) + 1):
                cell = ws.cell(row=1, column=c)
                cell.fill = hdr_fill
                cell.font = hdr_font
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            # 数据行（numericCols 列尝试转数值，便于 Excel 统计）
            for r in rows:
                out = []
                for i, v in enumerate(r):
                    if i in numeric:
                        if v is None or v == "":
                            out.append(None)
                        else:
                            try:
                                out.append(float(v))
                            except (ValueError, TypeError):
                                out.append(v)
                    else:
                        out.append("" if v is None else v)
                ws.append(out)
            # 列宽自适应（限幅）
            sample = rows[:200]
            for i in range(1, len(head) + 1):
                maxlen = len(str(head[i - 1]))
                for r in sample:
                    if i - 1 < len(r) and r[i - 1] is not None:
                        maxlen = max(maxlen, len(str(r[i - 1])))
                ws.column_dimensions[get_column_letter(i)].width = min(max(maxlen + 2, 8), 40)
            ws.freeze_panes = "A2"
            buf = io.BytesIO()
            wb.save(buf)
            data = buf.getvalue()
            from urllib.parse import quote
            disp = "attachment; filename=\"export.xlsx\"; filename*=UTF-8''%s.xlsx" % quote(name)
            self.send_response(200)
            self.send_header("Content-Type",
                             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition", disp)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self._send(500, json.dumps({"ok": False, "msg": "导出 Excel 失败：" + str(e)},
                                       ensure_ascii=False))

    def _api_get_history_dates(self):
        fp = os.path.join(BASE, "out", "dispatch_history.json")
        if not os.path.exists(fp):
            self._send(200, json.dumps({"dates": []}, ensure_ascii=False))
            return
        obj = json.load(open(fp, encoding="utf-8"))
        dates = sorted(obj.keys(), reverse=True)
        self._send(200, json.dumps({"dates": dates}, ensure_ascii=False))

    def _api_get_history(self):
        qs = self.path.split("?", 1)[1] if "?" in self.path else ""
        date = ""
        for part in qs.split("&"):
            if part.startswith("date="):
                date = part[len("date="):]
                break
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            self._send(400, json.dumps({"ok": False, "msg": "date format error"}, ensure_ascii=False))
            return
        fp = os.path.join(BASE, "out", "dispatch_history.json")
        if not os.path.exists(fp):
            self._send(200, json.dumps({"ok": True, "date": date, "found": False}, ensure_ascii=False))
            return
        obj = json.load(open(fp, encoding="utf-8"))
        snap = obj.get(date)
        if not snap:
            self._send(200, json.dumps({"ok": True, "date": date, "found": False}, ensure_ascii=False))
            return
        # 实时分类统计：从当前 assignments.json 中 created_date==date 的任务聚合（反映最新回访分类）
        cat_stats = {}
        fp_a = os.path.join(BASE, "out", "assignments.json")
        if os.path.exists(fp_a):
            try:
                obj = json.load(open(fp_a, encoding="utf-8"))
                for it in obj.get("items", []):
                    if it.get("created_date") == date:
                        k = it.get("rec_category") or DEFAULT_CAT
                        cat_stats[k] = cat_stats.get(k, 0) + 1
            except Exception:
                pass
        realtime_items = []
        if os.path.exists(fp_a):
            try:
                obj = json.load(open(fp_a, encoding="utf-8"))
                realtime_items = [it for it in obj.get("items", []) if it.get("created_date") == date]
            except Exception:
                pass
        self._send(200, json.dumps({
            "ok": True,
            "date": date,
            "found": True,
            "created_at": snap.get("created_at", ""),
            "staff": snap.get("staff", []),
            "quotas": snap.get("quotas", {}),
            "assignments": snap.get("assignments", []),
            "cat_stats": cat_stats,
            "realtime_items": realtime_items,
        }, ensure_ascii=False))

    def _api_get_tags(self):
        fp = os.path.join(BASE, "out", "tags.json")
        if os.path.exists(fp):
            obj = json.load(open(fp, encoding="utf-8"))
        else:
            obj = DEFAULT_TAGS
        self._send(200, json.dumps(obj, ensure_ascii=False))

    def _api_lan_info(self):
        """返回本机内网访问地址，供「生成回访链接」使用。
        v10.28.55 增加 firewall_ok 自检；
        v10.28.55 增加 me_token（当前请求者的 token），让前端能给同事链接拼 &token=...，
        否则同事点开会落到登录页。"""
        me_token = ""
        try:
            from urllib.parse import urlparse, parse_qs
            _q = parse_qs(urlparse(self.path).query)
            _t = (_q.get("token") or [""])[0].strip()
            if _t and resolve_auth(_t):
                me_token = _t
        except Exception:
            pass
        try:
            self._send(200, json.dumps({
                "ip": get_lan_ip(), "ips": get_lan_ips(), "port": LISTEN_PORT,
                "firewall_ok": check_firewall_rule(LISTEN_PORT),
                "me_token": me_token,
            }, ensure_ascii=False))
        except Exception as e:
            self._send(500, json.dumps({"ok": False, "msg": str(e)}, ensure_ascii=False))

    def _api_me_token(self):
        """v10.28.55：返回当前请求者的 token，供「生成回访链接」拼接用。
        v10.28.55：兜底增加 Authorization header（Bearer / X-Auth-Token），
        防止部分浏览器/扩展把 query 参数吃掉的边界场景。"""
        try:
            _t = ""
            # 1) ?token=
            from urllib.parse import urlparse, parse_qs
            _q = parse_qs(urlparse(self.path).query)
            _t = (_q.get("token") or [""])[0].strip()
            # 2) Authorization: Bearer xxx
            if not _t:
                ah = self.headers.get("Authorization") or ""
                if ah.lower().startswith("bearer "):
                    _t = ah[7:].strip()
            # 3) X-Auth-Token
            if not _t:
                _t = (self.headers.get("X-Auth-Token") or "").strip()
            if _t and resolve_auth(_t):
                self._send(200, json.dumps({"ok": True, "token": _t}, ensure_ascii=False))
                return
            self._send(200, json.dumps({"ok": False, "msg": "未登录或 token 无效"}, ensure_ascii=False))
        except Exception as e:
            self._send(500, json.dumps({"ok": False, "msg": str(e)}, ensure_ascii=False))

    def _api_list_backups(self):
        """v10.28.55：列出 out/assignments.bak.*.json 备份，前端「恢复」按钮下拉用。"""
        try:
            out_dir = os.path.join(BASE, "out")
            baks = sorted([f for f in os.listdir(out_dir)
                           if f.startswith("assignments.bak.") and f.endswith(".json")],
                          reverse=True)  # 最新在前
            self._send(200, json.dumps({"ok": True, "backups": baks}, ensure_ascii=False))
        except Exception as e:
            self._send(500, json.dumps({"ok": False, "msg": str(e)}, ensure_ascii=False))

    def _api_post(self):
        body = self._read_body()
        if self.path == "/api/assign":
            self._save_assignment(body)
        elif self.path == "/api/staff":
            self._save_staff(body)
        elif self.path == "/api/tags":
            self._save_tags(body)
        elif self.path == "/api/redispatch":
            self._redispatch(body)
        elif self.path == "/api/restore_assignments":  # v10.28.55
            self._restore_assignments(body)
        elif self.path == "/api/reassign":
            self._reassign(body)
        elif self.path == "/api/clear_history":
            self._clear_history()
        elif self.path == "/api/clear_assignments":
            self._clear_assignments()
        elif self.path == "/api/mark_visit":
            self._mark_visit(body)
        elif self.path == "/api/replace_candidates":
            self._replace_candidates(body)
        elif self.path == "/api/replace_assignment":
            self._replace_assignment(body)
        elif self.path == "/api/cancel_solver":
            self._cancel_solver(body)
        elif self.path == "/api/self_update":
            self._self_update(body)
        elif self.path == "/api/ai_classify":
            self._ai_classify(body)
        elif self.path == "/api/mark_no_followup":
            self._mark_no_followup(body)
        elif self.path == "/api/no_followup_add":
            self._no_followup_add(body)
        elif self.path == "/api/no_followup_remove":
            self._no_followup_remove(body)
        elif self.path == "/api/login":
            self._api_login(body)
        elif self.path == "/api/reset_admin_default":
            self._api_reset_admin_default(body)
        elif self.path == "/api/export_analysis_xlsx":
            self._api_export_analysis_xlsx(body)
        else:
            self._send(404, json.dumps({"ok": False, "msg": "unknown api"}, ensure_ascii=False))

    def _save_assignment(self, body):
        aid = body.get("id")
        fp = os.path.join(BASE, "out", "assignments.json")
        obj = json.load(open(fp, encoding="utf-8")) if os.path.exists(fp) else {"items": []}
        items = obj.setdefault("items", [])
        target = next((x for x in items if x.get("id") == aid), None)
        if not target:
            self._send(404, json.dumps({"ok": False, "msg": "未找到该任务"}, ensure_ascii=False))
            return
        # 更新字段
        for k in ("assigned_solver", "planned_time", "status"):
            if k in body and body[k] is not None:
                target[k] = body[k]
        if "tags" in body and isinstance(body["tags"], dict):
            target["tags"] = {"L1": body["tags"].get("L1", []), "L2": body["tags"].get("L2", []),
                              "L3": body["tags"].get("L3", []), "outcomes": body["tags"].get("outcomes", [])}
        if "rec_category" in body and body.get("rec_category"):
            target["rec_category"] = body["rec_category"]
        target["tagged_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        target["tagged_by"] = body.get("tagged_by") or target.get("tagged_by")
        # 未接通类（旧 outcomes）或新回访分类(01~04 需再次回访) → 自动生成 +N 天再次回访
        outcomes = set(target.get("tags", {}).get("outcomes", []))
        need_recall = bool(outcomes & UNREACHABLE) or target.get("rec_category") in NEED_RECALL_CATS
        if need_recall and target.get("status") not in ("已关闭",):
            created = create_recall(target)
            if created:
                self._send(200, json.dumps({"ok": True, "recall_created": True,
                                            "recall_time": created["planned_time"]}, ensure_ascii=False))
                return
        json.dump(obj, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        bump_data_version()  # 排班/分配/回访结果保存后通知前端刷新
        self._send(200, json.dumps({"ok": True}, ensure_ascii=False))

    def _save_staff(self, body):
        # v10.28.55：账号体系统一存 staff_auth.json
        #   admin: {username, pw_salt, pw_hash}；users[]: {username, name, role, token, modules, can_sync, scope, phone_allow, pw_salt, pw_hash}
        auth = load_auth()
        # 保存管理员账号（username + 新密码时哈希）
        if isinstance(body.get("admin"), dict):
            a = body["admin"]
            un = (a.get("username") or "").strip()
            if un:
                adm = auth.setdefault("admin", {})
                adm["username"] = un
                pw = a.get("password") or ""
                if pw:
                    salt, h = hash_password(pw)
                    adm["pw_salt"] = salt
                    adm["pw_hash"] = h
                auth["admin"] = adm
        # 保存普通用户
        if "users" in body and isinstance(body["users"], list):
            existing = {u.get("username"): u for u in auth.get("users", []) if u.get("username")}
            cleaned = []
            for u in body["users"]:
                if not isinstance(u, dict):
                    continue
                un = (u.get("username") or "").strip()
                if not un:
                    continue
                token = (u.get("token") or "").strip() or gen_token()
                entry = {
                    "username": un,
                    "name": (u.get("name") or un).strip(),
                    "role": (u.get("role") or "").strip(),
                    "token": token,
                    "modules": [m for m in (u.get("modules") or []) if isinstance(m, str)],
                    "can_sync": bool(u.get("can_sync")),
                    "scope": _norm_scope(u.get("scope")),
                    "phone_allow": _norm_phone_allow(u.get("phone_allow")),
                }
                pw = u.get("password") or ""
                if pw:
                    # 提供新密码 → 重新哈希
                    salt, h = hash_password(pw)
                    entry["pw_salt"] = salt
                    entry["pw_hash"] = h
                elif un in existing:
                    # 未改密码 → 保留旧哈希
                    entry["pw_salt"] = existing[un].get("pw_salt", "")
                    entry["pw_hash"] = existing[un].get("pw_hash", "")
                cleaned.append(entry)
            auth["users"] = cleaned
        json.dump(auth, open(AUTH_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        # 兼容旧 dispatch 排班配置（写入 out/staff.json，不影响权限）
        cfg = load_config()
        if "staff" in body and isinstance(body["staff"], list):
            cfg["staff"] = [s for s in body["staff"] if s]
        if "today_staff" in body and isinstance(body["today_staff"], list):
            # 只保留在总名单中的名字
            valid = set(cfg.get("staff") or [])
            cfg["today_staff"] = [s for s in body["today_staff"] if s in valid]
        if "quotas" in body and isinstance(body["quotas"], dict):
            cleaned_q = {}
            for k, v in body["quotas"].items():
                try:
                    cleaned_q[k] = max(1, int(v))
                except Exception:
                    pass
            cfg["quotas"] = cleaned_q
        if "daily_quota" in body:
            try:
                cfg["daily_quota"] = max(1, int(body["daily_quota"]))
            except Exception:
                pass
        if "gen_filter" in body and isinstance(body["gen_filter"], dict):
            gf = {}
            for k in ("product", "agent", "city", "area", "street", "community", "agreement_type"):
                if body["gen_filter"].get(k):
                    gf[k] = body["gen_filter"][k]
            ut = body["gen_filter"].get("user_types")
            if isinstance(ut, list):
                gf["user_types"] = [x for x in ut if x in ("lf", "owe")]
            elif isinstance(ut, str):
                gf["user_types"] = [ut] if ut in ("lf", "owe") else []
            cfg["gen_filter"] = gf
        json.dump(cfg, open(os.path.join(BASE, "out", "staff.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        self._send(200, json.dumps({"ok": True}, ensure_ascii=False))

    def _save_tags(self, body):
        json.dump(body, open(os.path.join(BASE, "out", "tags.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        self._send(200, json.dumps({"ok": True}, ensure_ascii=False))

    def _redispatch(self, body):
        try:
            gen_date = (body or {}).get("gen_date") or None
            # v10.19/v10.20：mode 语义——force=清空重生成(保留已回访) / append=增量 / sync=仅重平衡待回访 / extra=追加排班
            mode = (body or {}).get("mode") or "force"
            if mode not in ('force', 'append', 'sync', 'extra'):
                mode = 'force'
            extra = (body or {}).get("extra_solvers") or None  # v10.20：{name: quota}
            if extra and not isinstance(extra, dict):
                extra = None
            # v10.28.55：force 模式清空前自动备份当前 assignments.json，便于用户误操作可回滚
            if mode == 'force':
                self._snapshot_assignments()
            # v10.28.55：强制 reload assign 模块，让磁盘上的最新 v10.28.55+ 代码立即生效
            # （之前磁盘换了新版但 serve.py 内存里仍是旧版，按钮一按还是出老结果）
            global run_assignment
            import importlib
            try:
                importlib.reload(assign)
                from assign import run_assignment as _ra
                run_assignment = _ra
                print('[v10.28.55] /api/redispatch: assign module reloaded')
            except Exception as _re:
                print('[WARN] reload assign 失败（继续用原模块）: %s' % _re)
            run_assignment(mode=mode, gen_date=gen_date, extra_solvers=extra)
            bump_data_version()
            self._send(200, json.dumps({"ok": True, "mode": mode, "extra_count": len(extra) if extra else 0}, ensure_ascii=False))
        except Exception as e:
            import traceback as _tb
            print('[FAIL] /api/redispatch: %s' % e)
            _tb.print_exc()
            self._send(500, json.dumps({"ok": False, "msg": str(e)}, ensure_ascii=False))

    # ===== v10.28.55：名单快照与恢复 =====
    def _snapshot_assignments(self):
        """备份当前 out/assignments.json → out/assignments.bak.<ts>.json，保留最近 5 份。
        在 force 清空前调用一次，让用户误操作后能一键恢复。"""
        import datetime as _dt
        import shutil
        fp = os.path.join(BASE, "out", "assignments.json")
        if not os.path.exists(fp):
            return
        try:
            ts_str = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            bak = os.path.join(BASE, "out", f"assignments.bak.{ts_str}.json")
            shutil.copy2(fp, bak)
            # 仅保留最近 5 份
            baks = sorted([f for f in os.listdir(os.path.join(BASE, "out"))
                           if f.startswith("assignments.bak.") and f.endswith(".json")])
            for old in baks[:-5]:
                try: os.remove(os.path.join(BASE, "out", old))
                except Exception: pass
            print(f"[v10.28.55] 已备份当前名单到 {os.path.basename(bak)}（保留最近 5 份）")
        except Exception as _e:
            print(f"[WARN] 备份 assignments.json 失败（继续执行）: {_e}")

    def _restore_assignments(self, body):
        """v10.28.55：把 out/assignments.json 还原到指定的备份文件名（默认最新一份）。"""
        try:
            bak_name = (body or {}).get("backup") or None
            out_dir = os.path.join(BASE, "out")
            baks = sorted([f for f in os.listdir(out_dir)
                           if f.startswith("assignments.bak.") and f.endswith(".json")],
                          reverse=True)  # 最新在前
            if not baks:
                self._send(200, json.dumps({"ok": False, "msg": "无可用备份"}, ensure_ascii=False))
                return
            if bak_name and bak_name in baks:
                target = bak_name
            else:
                target = baks[0]  # 最新一份
            src = os.path.join(out_dir, target)
            dst = os.path.join(out_dir, "assignments.json")
            import shutil
            shutil.copy2(src, dst)
            bump_data_version()
            self._send(200, json.dumps({"ok": True, "msg": f"已恢复 {target}",
                                        "backup": target,
                                        "available": baks}, ensure_ascii=False))
        except Exception as e:
            import traceback as _tb
            _tb.print_exc()
            self._send(500, json.dumps({"ok": False, "msg": str(e)}, ensure_ascii=False))

    def _api_force_run(self, body):
        """v10.28.55：一站式端点——重建 records.json + 生成今日回访名单 + 返回统计。
        前端 JS 可直接 fetch /api/force_run，body={} 或 {date, solvers}，立即拿到结果。
        不依赖任何子进程，纯 inline importlib.reload，最快最直接。"""
        import importlib
        import datetime as _dt
        try:
            gen_date = (body or {}).get('date') or _dt.date.today().strftime('%Y-%m-%d')
            print('[v10.28.55] /api/force_run  date=%s  开始...' % gen_date)

            # 1) reload 关键模块
            try:
                import build_lists
                importlib.reload(build_lists)
                print('[v10.28.55] reload build_lists OK')
            except Exception as _e1:
                self._send(500, json.dumps({"ok": False, "msg": "reload build_lists 失败: %s" % _e1}, ensure_ascii=False))
                return
            try:
                importlib.reload(assign)
                from assign import run_assignment as _ra
                global run_assignment; run_assignment = _ra
                print('[v10.28.55] reload assign OK')
            except Exception as _e2:
                self._send(500, json.dumps({"ok": False, "msg": "reload assign 失败: %s" % _e2}, ensure_ascii=False))
                return

            # 2) 抽数（直接调 build_lists.main，但 build_lists 是脚本不是函数，
            #    这里用 subprocess 跑一次，捕获输出，最长 5 分钟）
            import subprocess
            r = subprocess.run(
                [sys.executable, '-u', os.path.join(BASE, 'build_lists.py')],
                cwd=BASE, capture_output=True, text=True, encoding='utf-8', errors='replace',
                timeout=300)
            build_out = (r.stdout or '')[-2000:]
            build_err = (r.stderr or '')[-1000:]
            if r.returncode != 0:
                self._send(500, json.dumps({
                    "ok": False, "msg": "build_lists 失败 (rc=%d)" % r.returncode,
                    "stdout_tail": build_out, "stderr_tail": build_err
                }, ensure_ascii=False))
                return

            # 3) 生成今日名单
            n_today = 0
            run_err = None
            try:
                run_assignment(mode='force', gen_date=gen_date)
            except Exception as _e3:
                run_err = repr(_e3)
                import traceback as _tb2
                _tb2.print_exc()

            # 4) 读 assignments.json 拿今日任务数
            try:
                ap = os.path.join(BASE, 'out', 'assignments.json')
                if os.path.exists(ap):
                    d = json.load(open(ap, encoding='utf-8'))
                    n_today = sum(1 for x in d.get('items', [])
                                  if x.get('created_date') == gen_date)
            except Exception as _e4:
                pass

            # 5) 读 records.json 拿关键统计
            stats = {}
            try:
                rp = os.path.join(BASE, 'out', 'records.json')
                if os.path.exists(rp):
                    d = json.load(open(rp, encoding='utf-8'))
                    rows = d.get('rows') or []
                    stats['rows'] = len(rows)
                    stats['followable'] = sum(1 for r in rows if r.get('followable'))
                    stats['low_freq'] = sum(1 for r in rows if r.get('lf'))
                    stats['battery_sn_filled'] = sum(1 for r in rows if (r.get('battery_sn') or '').strip())
                    meta = (d.get('_meta') or {})
                    stats['effect_ready'] = bool(meta.get('effect_ready'))
                    stats['effect_ready_rows'] = meta.get('effect_ready_rows', 0)
            except Exception:
                pass

            # 6) v10.28.55 关键修复：重新生成看板 HTML（把 records.json 内嵌为 DATA），
            #    否则接待 / 效果 Tab 永远看到 force_run 之前的 DATA 快照。
            #    失败仅 warn，不阻断 bump_data_version（前端至少会收到 reload 信号）。
            try:
                rg = subprocess.run(
                    [sys.executable, '-u', os.path.join(BASE, 'gen_dashboard.py')],
                    cwd=BASE, capture_output=True, text=True, encoding='utf-8', errors='replace',
                    timeout=120)
                if rg.returncode != 0:
                    print('[v10.28.55] /api/force_run: gen_dashboard 退出码 %d, stderr=%s'
                          % (rg.returncode, (rg.stderr or '')[-500:]))
                else:
                    print('[v10.28.55] /api/force_run: 看板 HTML 已重新生成（DATA 内嵌最新）')
            except Exception as _gd:
                print('[v10.28.55] /api/force_run: gen_dashboard 调用失败（不影响 records.json / assignments）: %s' % _gd)

            bump_data_version()
            self._send(200, json.dumps({
                "ok": True, "date": gen_date, "today_tasks": n_today,
                "stats": stats, "run_error": run_err,
                "build_stdout_tail": build_out
            }, ensure_ascii=False))
        except Exception as e:
            import traceback as _tb
            print('[FAIL] /api/force_run: %s' % e)
            _tb.print_exc()
            self._send(500, json.dumps({"ok": False, "msg": str(e)}, ensure_ascii=False))

    def _reassign(self, body):
        """批量改派：将指定 task id 的【待回访】任务改派给 solver（已回访/已作废的保持原人，不误改）。"""
        ids = (body or {}).get("ids") or []
        solver = (body or {}).get("solver")
        only_pending = (body or {}).get("only_pending", True)  # 默认仅改派待回访
        if not ids or not solver:
            self._send(400, json.dumps({"ok": False, "msg": "缺少 ids 或 solver"}, ensure_ascii=False))
            return
        fp = os.path.join(BASE, "out", "assignments.json")
        if not os.path.exists(fp):
            self._send(404, json.dumps({"ok": False, "msg": "无分配数据"}, ensure_ascii=False))
            return
        obj = json.load(open(fp, encoding="utf-8"))
        idset = set(ids)
        n = 0
        skipped = 0
        for x in obj.get("items", []):
            if x.get("id") in idset:
                if only_pending and x.get("status") != "待回访":
                    skipped += 1
                    continue
                x["assigned_solver"] = solver
                n += 1
        json.dump(obj, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        bump_data_version()
        self._send(200, json.dumps({"ok": True, "updated": n, "skipped": skipped}, ensure_ascii=False))

    def _cancel_solver(self, body):
        """作废某人全部分配：移除其名下【待回访】任务，使这些协议回到待低频用户库（下次增量生成可被重新分配）。
        不写入 no_followup（那是永久不回访，如空号）；也不影响已回访/已作废的历史任务。"""
        solver = (body or {}).get("solver")
        if not solver:
            self._send(400, json.dumps({"ok": False, "msg": "缺少 solver"}, ensure_ascii=False))
            return
        fp = os.path.join(BASE, "out", "assignments.json")
        if not os.path.exists(fp):
            self._send(200, json.dumps({"ok": True, "removed": 0, "msg": "无分配数据"}, ensure_ascii=False))
            return
        obj = json.load(open(fp, encoding="utf-8"))
        items = obj.setdefault("items", [])
        before = len(items)
        removed = [x for x in items
                   if x.get("assigned_solver") == solver and x.get("status") == "待回访"]
        obj["items"] = [x for x in items
                        if not (x.get("assigned_solver") == solver and x.get("status") == "待回访")]
        after = len(obj["items"])
        json.dump(obj, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        bump_data_version()
        self._send(200, json.dumps({"ok": True, "removed": before - after,
                                    "msg": f"已作废「{solver}」的 {before - after} 条待回访任务，相关协议已释放回待分配池"}, ensure_ascii=False))

    def _trigger_sync(self):
        if sync_state["running"]:
            self._send(200, json.dumps({"ok": False, "msg": "同步进行中，请稍候"}, ensure_ascii=False))
            return
        threading.Thread(target=run_sync, daemon=True).start()
        self._send(200, json.dumps({"ok": True, "msg": "已开始同步"}, ensure_ascii=False))

    def _clear_history(self):
        """清空历史排班快照（dispatch_history.json），用于历史排班数据清空。"""
        try:
            fp = os.path.join(BASE, "out", "dispatch_history.json")
            json.dump({}, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            bump_data_version()
            self._send(200, json.dumps({"ok": True, "msg": "历史排班已清空"}, ensure_ascii=False))
        except Exception as e:
            self._send(500, json.dumps({"ok": False, "msg": str(e)}, ensure_ascii=False))

    def _clear_assignments(self):
        """清空回访任务（assignments.json）。

        - 不传 date：清空全部排班数据（今日待分配/回访调度/排班总览）。
        - 传 date（如 2026-08-17）：仅清空该日期的排班总览，保留其它日期与手动任务。
        """
        try:
            body = self._read_body()
            date = (body or {}).get("date") or None
            fp = os.path.join(BASE, "out", "assignments.json")
            if not os.path.exists(fp):
                self._send(200, json.dumps({"ok": True, "msg": "无排班数据"}, ensure_ascii=False))
                return
            obj = json.load(open(fp, encoding="utf-8"))
            if date:
                before = len(obj.get("items", []))
                obj["items"] = [x for x in obj.get("items", [])
                                if not (x.get("created_date") == date)]
                removed = before - len(obj["items"])
                json.dump(obj, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                bump_data_version()
                self._send(200, json.dumps({"ok": True, "msg": f"{date} 当日排班已清空，移除 {removed} 条", "removed": removed}, ensure_ascii=False))
            else:
                json.dump({"items": []}, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                bump_data_version()
                self._send(200, json.dumps({"ok": True, "msg": "当前全部排班已清空"}, ensure_ascii=False))
        except Exception as e:
            self._send(500, json.dumps({"ok": False, "msg": str(e)}, ensure_ascii=False))

    def _replace_candidates(self, body):
        """返回可替换候选用户列表（按被替换任务类型 + 当前生成筛选 + 未占用）。"""
        try:
            task_id = (body or {}).get("task_id")
            kw = (body or {}).get("kw", "")
            if not task_id:
                self._send(400, json.dumps({"ok": False, "msg": "缺少 task_id"}, ensure_ascii=False))
                return
            res = get_replace_candidates(task_id, kw)
            self._send(200, json.dumps(res, ensure_ascii=False))
        except Exception as e:
            self._send(500, json.dumps({"ok": False, "msg": str(e)}, ensure_ascii=False))

    def _replace_assignment(self, body):
        """执行替换：将某条回访任务替换为新用户。"""
        try:
            task_id = (body or {}).get("task_id")
            new_aid = (body or {}).get("new_agreement_id")
            if not task_id or new_aid is None:
                self._send(400, json.dumps({"ok": False, "msg": "缺少 task_id 或 new_agreement_id"}, ensure_ascii=False))
                return
            res = replace_assignment(task_id, new_aid)
            if res.get("ok"):
                self._send(200, json.dumps(res, ensure_ascii=False))
            else:
                self._send(400, json.dumps(res, ensure_ascii=False))
        except Exception as e:
            self._send(500, json.dumps({"ok": False, "msg": str(e)}, ensure_ascii=False))

    def _mark_visit(self, body):
        """手动标记任务已回访 / 未回访。"""
        aid = body.get("id")
        result = body.get("result")
        if result not in ("visited", "pending"):
            self._send(400, json.dumps({"ok": False, "msg": "result must be visited or pending"}, ensure_ascii=False))
            return
        fp = os.path.join(BASE, "out", "assignments.json")
        if not os.path.exists(fp):
            self._send(404, json.dumps({"ok": False, "msg": "无任务数据"}, ensure_ascii=False))
            return
        obj = json.load(open(fp, encoding="utf-8"))
        items = obj.setdefault("items", [])
        target = next((x for x in items if x.get("id") == aid), None)
        if not target:
            self._send(404, json.dumps({"ok": False, "msg": "未找到该任务"}, ensure_ascii=False))
            return
        target["visit_result"] = result
        target["visited_at"] = time.strftime("%Y-%m-%d %H:%M:%S") if result == "visited" else None
        json.dump(obj, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        self._send(200, json.dumps({"ok": True, "visit_result": result, "visited_at": target["visited_at"]}, ensure_ascii=False))

    def _api_get_rec_categories(self):
        cats = load_categories()
        self._send(200, json.dumps({"ok": True, "categories": cats,
                                    "need_recall": NEED_RECALL_CATS,
                                    "default": DEFAULT_CAT}, ensure_ascii=False))

    def _ai_classify(self, body):
        """批量对回访任务做接待内容智能分类，写回 rec_category。mode=all 全量，mode=auto 仅未分类。"""
        fp = os.path.join(BASE, "out", "assignments.json")
        if not os.path.exists(fp):
            self._send(404, json.dumps({"ok": False, "msg": "无任务数据"}, ensure_ascii=False))
            return
        obj = json.load(open(fp, encoding="utf-8"))
        items = obj.setdefault("items", [])
        mode = (body or {}).get("mode", "auto")
        use_llm = bool((body or {}).get("use_llm", True))
        updated = 0
        for it in items:
            cur = it.get("rec_category", "")
            if mode == "auto" and cur not in ("", None, DEFAULT_CAT):
                continue
            text = it.get("last_rec_detail", "") or ""
            rty = it.get("rty", "")
            new_cat = classify_recall(text, rty, use_llm=use_llm)
            if new_cat != cur:
                it["rec_category"] = new_cat
                updated += 1
        json.dump(obj, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        stats = {}
        for it in items:
            k = it.get("rec_category") or DEFAULT_CAT
            stats[k] = stats.get(k, 0) + 1
        self._send(200, json.dumps({"ok": True, "total": len(items), "updated": updated,
                                    "stats": stats}, ensure_ascii=False))

    def _api_get_no_followup(self):
        """返回无需回访名单及按原因统计。"""
        lst = load_no_followup_list()
        stats = {}
        for x in lst:
            r = x.get('reason') or '其他'
            stats[r] = stats.get(r, 0) + 1
        self._send(200, json.dumps({"ok": True, "items": lst, "count": len(lst), "stats": stats}, ensure_ascii=False))

    def _mark_no_followup(self, body):
        """将某条回访任务标记为无需回访，并写入 no_followup.json，任务状态置为已关闭。"""
        task_id = (body or {}).get("task_id")
        reason = (body or {}).get("reason") or '其他'
        note = (body or {}).get("note") or ''
        if not task_id:
            self._send(400, json.dumps({"ok": False, "msg": "缺少 task_id"}, ensure_ascii=False))
            return
        fp = os.path.join(BASE, "out", "assignments.json")
        if not os.path.exists(fp):
            self._send(404, json.dumps({"ok": False, "msg": "无任务数据"}, ensure_ascii=False))
            return
        obj = json.load(open(fp, encoding="utf-8"))
        items = obj.setdefault("items", [])
        target = next((x for x in items if x.get("id") == task_id), None)
        if not target:
            self._send(404, json.dumps({"ok": False, "msg": "未找到该任务"}, ensure_ascii=False))
            return
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        record = {
            "agreement_id": target.get("agreement_id"),
            "user_id": target.get("user_id"),
            "phone": target.get("phone", ""),
            "product": target.get("product", ""),
            "city": target.get("city", ""),
            "area": target.get("area", ""),
            "street": target.get("street", ""),
            "community": target.get("community", ""),
            "agreement_status": target.get("agreement_status", ""),
            "deposit_status": target.get("deposit_status", ""),
            "agreement_type": target.get("agreement_type", ""),
            "agreement_type_raw": target.get("agreement_type_raw", ""),
            "is_lf": bool(target.get("is_lf")),
            "is_owe": bool(target.get("is_owe")),
            "source_task_id": task_id,
            "assigned_solver": target.get("assigned_solver", ""),
            "reason": reason,
            "note": note,
            "marked_at": now,
            "marked_by": body.get("marked_by") or target.get("assigned_solver", ""),
        }
        lst = load_no_followup_list()
        # 去重：同一协议只保留最新一条
        lst = [x for x in lst if x.get("agreement_id") != record["agreement_id"]]
        lst.insert(0, record)
        save_no_followup_list(lst)
        target["status"] = "已关闭"
        target["visit_result"] = "visited"
        target["visited_at"] = now
        target["no_followup"] = True
        json.dump(obj, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        self._send(200, json.dumps({"ok": True, "record": record}, ensure_ascii=False))

    def _no_followup_add(self, body):
        """手动添加无需回访记录（不依赖现有任务）。"""
        record = body or {}
        required = ["agreement_id", "phone"]
        for k in required:
            if record.get(k) is None:
                self._send(400, json.dumps({"ok": False, "msg": f"缺少 {k}"}, ensure_ascii=False))
                return
        record.setdefault("reason", "其他")
        record.setdefault("marked_at", time.strftime("%Y-%m-%d %H:%M:%S"))
        lst = load_no_followup_list()
        lst = [x for x in lst if x.get("agreement_id") != record.get("agreement_id")]
        lst.insert(0, record)
        save_no_followup_list(lst)
        self._send(200, json.dumps({"ok": True, "record": record}, ensure_ascii=False))

    def _no_followup_remove(self, body):
        """删除无需回访记录（支持按 agreement_id 或 id/index）。"""
        aid = (body or {}).get("agreement_id")
        idx = (body or {}).get("index")
        lst = load_no_followup_list()
        before = len(lst)
        if aid is not None:
            lst = [x for x in lst if x.get("agreement_id") != aid]
        elif isinstance(idx, int) and 0 <= idx < len(lst):
            lst.pop(idx)
        else:
            self._send(400, json.dumps({"ok": False, "msg": "缺少 agreement_id 或有效 index"}, ensure_ascii=False))
            return
        save_no_followup_list(lst)
        self._send(200, json.dumps({"ok": True, "removed": before - len(lst)}, ensure_ascii=False))

    def _self_update(self, body):
        """看板内一键更新：下载更新包 zip → 解压合并（保留数据与配置）→ 重新同步数据库 → 热重启服务。"""
        url = (body or {}).get("url") or ""
        if not re.match(r'^https?://', url or ''):
            self._send(400, json.dumps({"ok": False, "msg": "请提供有效的 http(s) 更新链接"}, ensure_ascii=False))
            return
        tmp_zip = os.path.join(BASE, "out", "_self_update.zip")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "lowfreq-self-update"})
            with urllib.request.urlopen(req, timeout=180) as r:
                data = r.read()
            os.makedirs(os.path.join(BASE, "out"), exist_ok=True)
            with open(tmp_zip, "wb") as f:
                f.write(data)
        except Exception as e:
            self._send(500, json.dumps({"ok": False, "msg": "下载更新包失败：" + str(e)}, ensure_ascii=False))
            return
        try:
            # extract_and_merge 会备份旧版并覆盖代码，保留 out/、uploads_sms/、db_conf.json、staff.json、update_url.txt
            extract_and_merge(tmp_zip)
        except Exception as e:
            self._send(500, json.dumps({"ok": False, "msg": "解压/合并更新包失败：" + str(e)}, ensure_ascii=False))
            return
        # 校验新 serve.py 可编译，避免热重启后服务起不来
        new_serve = os.path.join(BASE, "serve.py")
        if os.path.exists(new_serve):
            try:
                compile(open(new_serve, encoding="utf-8").read(), new_serve, "exec")
            except Exception as e:
                self._send(500, json.dumps(
                    {"ok": False, "msg": "新版本 serve.py 语法错误，已中止更新以防服务中断：" + str(e)}, ensure_ascii=False))
                return
        # 合并后立即重启新进程（新进程启动时会自己跑一次 sync），不在旧进程里同步阻塞 fetch
        # 关键：必须先 send + flush，浏览器 fetch 拿到响应后才能放心 5s 后 reload，否则中间层超时断开会报 Failed to fetch
        self._send(200, json.dumps({"ok": True, "msg": "更新完成，正在重启服务并同步数据…", "restart": True}, ensure_ascii=False))
        try:
            self.wfile.flush()
        except Exception:
            pass
        def _delayed_restart():
            # 给主线程的响应留 0.8s 充分 flush 出去
            time.sleep(0.8)
            try:
                subprocess.Popen(
                    [sys.executable, os.path.abspath(__file__)],
                    cwd=BASE,
                    creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
                    close_fds=True,
                )
            except Exception:
                pass
            # 新进程需要 import 一堆模块 + resolve_db_host，1.5s 后再退出旧进程，确保新进程先 bind 端口
            time.sleep(1.5)
            os._exit(0)
        threading.Thread(target=_delayed_restart, daemon=True).start()

    def _serve_dashboard(self):
        # v10.28.55：账号密码登录 + token 鉴权（后端硬拦截）
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(self.path).query)
        token = (qs.get("token") or [""])[0].strip()
        # 旧版明文链接 ?user=boss 一律作废 → 403
        if qs.get("user"):
            self._send(403, FORBIDDEN_HTML, "text/html; charset=utf-8")
            return
        auth = resolve_auth(token)
        if auth is None:
            # 未携带有效 token → 展示登录页（而非直接拒绝），登录成功后再带 token 进入
            self._send(200, LOGIN_HTML, "text/html; charset=utf-8")
            return
        f = os.path.join(BASE, "out", "followup_dashboard.html")
        if not os.path.exists(f):
            # v10.28.55：离线兜底——本地已有 records.json 就先用它生成 HTML，无需连库，
            # 保证「以前同步过数据」时断网/换机也能直接打开（不再卡在「首次同步」轮询页）。
            # 仅当连 records.json 都没有、且连库同步也不可行时，才返回 FALLBACK 引导页。
            records_json = os.path.join(BASE, "out", "records.json")
            if os.path.exists(records_json) and not sync_state["running"]:
                try:
                    print("[INFO] 看板 HTML 缺失，使用本地 records.json 离线重建…")
                    subprocess.run(
                        [sys.executable, os.path.join(BASE, "gen_dashboard.py")],
                        cwd=BASE, capture_output=True, text=True, encoding="utf-8", errors="replace")
                except Exception as e:
                    print(f"[WARN] 离线生成看板失败：{e}")
            if os.path.exists(f):
                pass  # 已重建成功，下方正常返回
            else:
                if not sync_state["running"]:
                    threading.Thread(target=run_sync, daemon=True).start()
                self._send(200, FALLBACK_HTML, "text/html; charset=utf-8")
                return
        # v10.28.55：走缓存读取（文件未变则复用内存副本，避免每请求重读数十 MB）
        html = _read_dashboard_html(f)
        if html is None:
            self._send(500, "看板 HTML 读取失败", "text/plain; charset=utf-8")
            return
        # 注入 __AUTH__（模块权限 + 数据范围），前端据此隐藏 tab、过滤数据
        auth_js = '<script>window.__AUTH__=%s;</script>' % json.dumps(auth, ensure_ascii=False)
        html, n = re.subn(r'(?i)<head\b[^>]*>', lambda m: m.group(0) + auth_js, html, count=1)
        if n == 0:
            html = auth_js + html
        # 注入运行模式标记，前端据此启用/禁用同步按钮。
        # 必须注入到 <head> 中，确保在页面 JS 执行前 window.__SERVE__ 已定义。
        html, n = re.subn(r'(?i)<head\b[^>]*>', lambda m: m.group(0) + '<script>window.__SERVE__=true;</script>', html, count=1)
        if n == 0:
            # 兼容 fallback：如果 HTML 没有 head（不应发生），在 body 结尾注入
            html = html.replace("</body>", '<script>window.__SERVE__=true;</script></body>')
        # v10.28.55：dashboard 强制 no-cache——浏览器/CDN/反代层都不应缓存，避免新版本被
        # 旧 HTML 缓存命中导致 fmtSolver 等新函数 ReferenceError、数据不显示
        # v10.28.57：dashboard 也支持 gzip —— HTML 2MB 级，内网/WiFi 下不压缩仍会转圈。
        # 压缩结果走 _GZ_CACHE 内存缓存，避免每个请求重复压缩（约 200ms/次）。
        try:
            _ae = (self.headers.get("Accept-Encoding") or "")
        except Exception:
            _ae = ""
        _gz = None
        if "gzip" in _ae.lower():
            _ck = (str(_HTML_CACHE.get("mtime")), len(html), auth_js)
            try:
                if _GZ_CACHE.get("key") == _ck and _GZ_CACHE.get("gz"):
                    _gz = _GZ_CACHE["gz"]
                else:
                    import gzip as _gzip
                    _buf = io.BytesIO()
                    with _gzip.GzipFile(fileobj=_buf, mode="wb", compresslevel=6, mtime=0) as _g:
                        _g.write(html.encode("utf-8"))
                    if len(_buf.getvalue()) < len(html.encode("utf-8")):
                        _gz = _buf.getvalue()
                        _GZ_CACHE["key"] = _ck
                        _GZ_CACHE["gz"] = _gz
            except Exception:
                _gz = None
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("X-Build-Version", SERVE_VERSION)
        if _gz is not None:
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(_gz)))
            self.send_header("Vary", "Accept-Encoding")
            self.end_headers()
            self.wfile.write(_gz)
        else:
            self.send_header("Content-Length", str(len(html.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
        return

    def log_message(self, *args):
        pass


def _open_browser(url):
    """以平台原生方式打开浏览器，兼容 pythonw（run_silent.bat）无控制台场景。

    webbrowser.open 在 pythonw 进程下常静默失败（无窗口站/默认浏览器关联异常），
    所以优先使用 Windows 原生的 os.startfile，失败再回退 webbrowser，最后用系统默认程序兜底。
    """
    if sys.platform.startswith("win"):
        try:
            os.startfile(url)
            return True
        except Exception as e:
            print(f"[WARN] os.startfile 打开失败：{e}")
    try:
        if webbrowser.open(url, new=1, autoraise=True):
            return True
    except Exception as e:
        print(f"[WARN] webbrowser.open 打开失败：{e}")
    # 终极兜底：直接调起系统默认程序
    try:
        if sys.platform.startswith("win"):
            subprocess.Popen(["cmd", "/c", "start", "", url])
        elif sys.platform.startswith("darwin"):
            subprocess.Popen(["open", url])
        else:
            subprocess.Popen(["xdg-open", url])
        return True
    except Exception as e:
        print(f"[WARN] 兜底打开失败：{e}")
    return False


def main():
    global LISTEN_PORT
    os.chdir(BASE)

    # v10.28.55：启动时先确保登录凭证存在（缺失则从种子恢复，已存在则原样保留）
    try:
        ensure_auth_file()
    except Exception as e:
        print(f"[WARN]️ 凭证自检异常（不影响启动）：{e}")

    # 自动托管：检测 Python、安装依赖、选择数据库地址
    print("== 低频看板 · 本地服务启动 ==")
    if not env.ensure_python():
        print("[FAIL] Python 自检失败，无法启动服务。请安装 Python 3.8+ 并加入 PATH 后重试。")
        _write_serve_status(ok=False, port=0, error="python_unavailable")
        _pause_for_user(8)
        return
    if not env.ensure_deps():
        print("[WARN]️ 依赖未就绪，请手动运行：python -m pip install pymysql openpyxl")
        _write_serve_status(ok=False, port=0, error="deps_missing")
        _pause_for_user(8)
        return
    chosen_host = env.resolve_db_host()
    if chosen_host:
        print(f"[OK] 数据库连接测试通过：{chosen_host}")
    else:
        print("[WARN]️ 当前数据库无法连接，服务仍可启动，但同步可能失败。")
        print("   如需内网同步，请在 db_conf.json 中填入 intranet_host。")

    # 启动时若已有数据，先确保看板 UI 与数据是「最新结构」：
    #   - 数据为旧结构（records.json 缺 'nf' 字段，即升级前版本）-> 后台自动同步一次，
    #     连库重建 records.json（含 need_followup）+ 看板 HTML（含「是否需要回访」新列）；
    #   - 否则仅重新生成看板 HTML，确保同步按钮等 UI 是最新版。
    # v10.28.55：再加一层 mtime 兜底——records.json 比 followup_dashboard.html 新时强制重生，
    #   避免上一次 force_run 崩在中间状态导致 HTML 与 records.json 脱节；以及 build_lists_version
    #   与 SERVE_VERSION 不一致（如升级过 build_lists.py 但没跑 force_run）。
    records_json = os.path.join(BASE, "out", "records.json")
    dashboard_html = os.path.join(BASE, "out", "followup_dashboard.html")
    if os.path.exists(records_json):
        _stale = False
        _mt_stale = False
        _ver_stale = False
        try:
            import json as _json
            _old = _json.load(open(records_json, encoding="utf-8"))
            _rows = _old.get("rows") or []
            _stale = bool(_rows) and ("nf" not in _rows[0])
            # v10.28.55：build_lists 版本与当前 SERVE_VERSION 不一致也视为陈旧
            try:
                _blv = ((_old.get("_meta") or {}).get("build_lists_version") or "").strip()
                if _blv and _blv != SERVE_VERSION:
                    _ver_stale = True
            except Exception:
                pass
        except Exception:
            _stale = False
        # v10.28.55：records.json mtime 晚于 dashboard.html mtime → 强制重生 HTML
        try:
            if os.path.exists(dashboard_html):
                _rmt = os.path.getmtime(records_json)
                _hmt = os.path.getmtime(dashboard_html)
                if _rmt > _hmt + 0.5:  # 0.5s 容差，避免 fs 抖动
                    _mt_stale = True
        except Exception:
            pass

        need_rebuild = _stale or _mt_stale or _ver_stale
        if _stale:
            print("== 检测到旧版数据（缺 nf 字段），先重建最新看板 UI，再后台同步刷新数据… ==")
            subprocess.run(
                [sys.executable, os.path.join(BASE, "gen_dashboard.py")],
                cwd=BASE, capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            _trigger_sync()
        elif _mt_stale:
            print("[v10.28.55] records.json 比 dashboard.html 新（force_run 中断？），重建 HTML… ==")
            r = subprocess.run(
                [sys.executable, os.path.join(BASE, "gen_dashboard.py")],
                cwd=BASE, capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            print("[v10.28.55] 看板 HTML 已重建。" if r.returncode == 0
                  else f"[v10.28.55] 看板 HTML 重建失败：{(r.stderr or '')[-300:]}")
        elif _ver_stale:
            print(f"[v10.28.55] records.json 来自旧版 build_lists（{_blv}），重建 HTML… ==")
            r = subprocess.run(
                [sys.executable, os.path.join(BASE, "gen_dashboard.py")],
                cwd=BASE, capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            print("[v10.28.55] 看板 HTML 已重建。" if r.returncode == 0
                  else f"[v10.28.55] 看板 HTML 重建失败：{(r.stderr or '')[-300:]}")
        else:
            print("== 检测到已有数据，正在重新生成最新看板 UI… ==")
            r = subprocess.run(
                [sys.executable, os.path.join(BASE, "gen_dashboard.py")],
                cwd=BASE, capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            if r.returncode != 0:
                print("[WARN]️ 看板生成失败，将尝试服务已有文件。错误：", (r.stderr or "")[-500:])
            else:
                print("[OK] 看板 UI 已更新。")

    httpd = None
    port = PORT
    while port < PORT + 20:
        # 先在同一个端口上重试若干次（热重启时旧实例退出后自动接管，避免端口飘移）
        bound = False
        for _ in range(20):
            try:
                httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
                bound = True
                break
            except OSError:
                time.sleep(0.2)
        if bound:
            break
        port += 1
    if not httpd:
        print(f"[FAIL] 端口 {PORT} 被占用且无法分配，请关闭占用该端口的程序后重试。")
        _write_serve_status(ok=False, port=0, error="port_exhausted")
        _pause_for_user(8)
        return
    LISTEN_PORT = port  # 记录实际监听端口，供 /api/lan_info 使用
    _write_serve_status(ok=True, port=port)
    url = f"http://127.0.0.1:{port}/"
    lan_ips = get_lan_ips()
    print(f"== 低频看板服务已启动（本机）：{url} ==")
    for _ip in lan_ips:
        print(f"== 内网同事请访问：http://{_ip}:{port}/ ==")
    print(f"== 局域网链接（同事）：http://{(lan_ips or ['<unknown>'])[0]}:{port}/  (token 见看板顶部「同事访问」条) ==")
    ensure_firewall_rule(port)
    # v10.28.55：把同事可访问链接写入 out/同事访问链接.txt，用户双击文件即可复制发给同事
    try:
        _lines = ["低频用户回访看板 - 同事访问链接（同局域网 / 同网段）", ""]
        _lines.append(f"本机访问（你自己）：http://127.0.0.1:{port}/")
        if lan_ips:
            _lines.append("")
            _lines.append("把下面任一链接发给同网段同事 / 手机，打开即可查看（哪个能打开用哪个）：")
            for _ip in lan_ips:
                _lines.append(f"  http://{_ip}:{port}/")
        _lines.append("")
        _lines.append("注意：需本机服务窗口保持运行，且 Windows 防火墙已放行该端口（首次运行会弹 UAC 自动放行，之后长期保留）。")
        with open(os.path.join(BASE, "out", "同事访问链接.txt"), "w", encoding="utf-8") as _lf:
            _lf.write("\n".join(_lines))
        print(f"[OK] 已生成 out/同事访问链接.txt（可直接复制发给同事）")
    except Exception as e:
        print(f"[WARN] 生成访问链接文件失败：{e}")
    print("浏览器将自动打开本机地址。如未打开，请手动访问上面的地址；关闭本窗口即停止服务。")
    # 后台线程先启动 HTTP 服务，确保浏览器打开时端口已真正就绪（避免打开瞬间尚未 accept）
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    time.sleep(0.6)
    if not _open_browser(url):
        print(f"[提示] 浏览器未能自动打开，请手动访问：{url}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n已停止服务。")


if __name__ == "__main__":
    main()
