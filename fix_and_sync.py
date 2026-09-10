# -*- coding: utf-8 -*-
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
"""
低频看板 · 一键诊断修复 + 同步
==============================
用户双击 fix_and_sync.bat 后，本脚本自动：
1. 检查 Python 版本
2. 检查并安装缺失依赖（pymysql / openpyxl）
3. 检查 db_conf.json 配置
4. 探测数据库连接（内网优先，公网 fallback）
5. 若连接成功：执行完整同步链路
6. 若连接失败：给出明确原因和修复建议，并打开日志文件
7. 启动本地服务并打开浏览器

此脚本不依赖 GUI，全部通过命令行 + 记事本/浏览器反馈。
"""
import os
import sys
import json
import subprocess
import time
import webbrowser
import traceback

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, 'out')
os.makedirs(OUT, exist_ok=True)
LOG_FILE = os.path.join(OUT, 'fix_and_sync.log')

# --------------- 日志输出 ---------------
log_lines = []

def log(msg):
    ts = time.strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line)
    log_lines.append(line)
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass

def open_log():
    """尝试用记事本打开日志"""
    try:
        subprocess.Popen(['notepad.exe', LOG_FILE], shell=False)
    except Exception:
        pass

def pause():
    if sys.platform == 'win32':
        os.system('pause')

# --------------- Python 版本 ---------------
log('='*60)
log('低频看板 · 一键诊断修复')
log('='*60)

if sys.version_info < (3, 8):
    log('[FAIL] Python 版本过低，需要 3.8 及以上。当前版本：' + sys.version)
    open_log()
    pause()
    sys.exit(1)

log(f'[OK] Python 版本：{sys.version.split()[0]}')

# --------------- 依赖安装 ---------------
REQUIRED = ['pymysql', 'openpyxl']

def ensure_package(name):
    try:
        __import__(name)
        log(f'[OK] 依赖已安装：{name}')
        return True
    except ImportError:
        log(f'[WARN]️ 缺少依赖：{name}，正在自动安装...')
        r = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', name, '--quiet'],
            capture_output=True, text=True, encoding='utf-8', errors='replace'
        )
        if r.returncode != 0:
            log(f'[FAIL] {name} 安装失败：')
            log((r.stderr or r.stdout or '')[-500:])
            return False
        try:
            __import__(name)
            log(f'[OK] {name} 安装成功')
            return True
        except Exception as e:
            log(f'[FAIL] {name} 安装后仍无法导入：{e}')
            return False

missing = []
for pkg in REQUIRED:
    if not ensure_package(pkg):
        missing.append(pkg)

if missing:
    log('\n[FAIL] 以下依赖自动安装失败，请手动执行：')
    log(f'   {sys.executable} -m pip install {" ".join(missing)}')
    log('如果因公司网络限制无法下载，可换国内源：')
    log(f'   {sys.executable} -m pip install {" ".join(missing)} -i https://pypi.tuna.tsinghua.edu.cn/simple')
    open_log()
    pause()
    sys.exit(1)

# --------------- db_conf.json 检查 ---------------
conf_path = os.path.join(BASE, 'db_conf.json')
if not os.path.exists(conf_path):
    log('[FAIL] 未找到数据库配置文件：db_conf.json')
    log('请从同事处获取正确配置，或参考 README.txt 填写。')
    open_log()
    pause()
    sys.exit(1)

try:
    with open(conf_path, encoding='utf-8') as f:
        conf = json.load(f)
except Exception as e:
    log(f'[FAIL] db_conf.json 格式错误，无法解析：{e}')
    open_log()
    pause()
    sys.exit(1)

required_keys = ['host', 'port', 'user', 'password', 'database']
empty_keys = [k for k in required_keys if not str(conf.get(k, '')).strip()]
if empty_keys:
    log(f'[FAIL] db_conf.json 中以下字段为空：{", ".join(empty_keys)}')
    log('请填写完整数据库连接信息后再试。')
    open_log()
    pause()
    sys.exit(1)

log('[OK] db_conf.json 配置格式正确')

# v10.28.5：检测占位符（REPLACE_ME_* 或 REMAKE_ME）—— 即便格式对也不应真连，
# 给出明确提示并降级渲染示例看板，保证浏览器照常打开、布局照常显示。
PLACEHOLDERS = ('REPLACE_ME', 'REMAKE_ME', 'CHANGE_ME', '<', 'YOUR_')
def _is_placeholder(v):
    s = str(v or '').strip()
    return not s or any(tok in s.upper() for tok in PLACEHOLDERS)
placeholder_keys = [k for k in required_keys if _is_placeholder(conf.get(k))]

# --------------- 数据库连接探测 ---------------
import pymysql

def try_connect(host):
    try:
        log(f'[{host}] 尝试连接 {host}:{conf.get("port", 3306)} ...')
        conn = pymysql.connect(
            host=host,
            port=int(conf.get('port', 3306)),
            user=conf['user'],
            password=conf['password'],
            database=conf['database'],
            charset='utf8mb4',
            connect_timeout=15,
            cursorclass=pymysql.cursors.DictCursor
        )
        conn.close()
        log(f'[OK] [{host}] 连接成功')
        return True
    except Exception as e:
        log(f'[WARN]️ [{host}] 连接失败：{e}')
        return False

# 候选地址：环境变量 > 内网地址 > 公网地址（占位符模式下不连接，跳过）
placeholder_mode = bool(placeholder_keys)
if placeholder_mode:
    log(f'\n[占位符] db_conf.json 中以下字段仍是脱敏占位符：{", ".join(placeholder_keys)}')
    log('这是 ZIP 包自带的占位值（host/user/password/database），必须改回您内网真实值才能连库。')
    log('【将跳过连库步骤、降级渲染示例看板】，让浏览器照常打开、布局照常显示，不会卡住。')
    log('修改 db_conf.json 的真实值后，再次双击本 bat 即可拉真实数据。\n')
    # 写一段 marker，便于看板顶部提示
    try:
        marker = {
            "now": time.strftime('%Y-%m-%d %H:%M:%S'),
            "sync_start": time.strftime('%Y-%m-%d %H:%M:%S'),
            "sync_cost": 0,
            "total": 0,
            "rows": [], "reception": [], "reception_detail": [],
            "diagnostic": {"__demo_placeholder__": True, "missing_keys": placeholder_keys,
                           "hint": "请把 db_conf.json 的 host/user/password/database 改为内网真实值"},
        }
        rec_p = os.path.join(OUT, 'records.json')
        # 若已有则不覆盖，避免清掉用户已经填对但本次 placeholder 模式打开的 records.json
        if not os.path.exists(rec_p):
            with open(rec_p, 'w', encoding='utf-8') as f:
                json.dump(marker, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    connected_host = None
else:
    candidates = []
    env_host = os.environ.get('LF_DB_HOST', '').strip()
    if env_host:
        candidates.append(env_host)
    intranet = conf.get('intranet_host', '').strip()
    if intranet and intranet not in candidates:
        candidates.append(intranet)
    public = conf.get('host', '').strip()
    if public and public not in candidates:
        candidates.append(public)

    connected_host = None
    for h in candidates:
        if try_connect(h):
            connected_host = h
            break

    if not connected_host:
        log('\n[FAIL] 所有数据库地址均无法连接。')
        log('可能原因及修复方法：')
        log('1) 本机未连接公司内网 / VPN，请连接后重试。')
        log('2) 阿里云 ADB 白名单未包含本机公网 IP，请联系 DBA 添加。')
        log('3) db_conf.json 中 host/user/password 填写错误。')
        log('4) 若公司使用内网 ADB 地址，请填到 db_conf.json 的 intranet_host 字段。')
        log('\n已将错误日志写入：')
        log(LOG_FILE)
        open_log()
        pause()
        sys.exit(1)

# 把能连上的地址写到环境变量，供后续脚本使用（占位符模式下无 host）
if connected_host:
    os.environ['LF_DB_HOST'] = connected_host
    log(f'\n[TARGET] 将使用可用数据库地址：{connected_host}')

# --------------- 执行完整同步链路 ---------------
STEPS = [
    ('连库抽数', 'build_lists.py'),
    ('并入短信 Excel', 'merge_sms_excel.py'),
    ('生成看板 HTML', 'gen_dashboard.py'),
    ('导出空号/停机清单', 'export_special_lists.py'),
    # v10.12 起：回访名单改为手动生成（用户在「回访排班」Tab 选人员+配接待量+选电池产品后一键生成）
    # assign.py 仍保留并可手动触发（serve.py 提供 /api/redispatch），不再随同步自动执行。
]

if placeholder_mode:
    log('[跳过] 因 db_conf.json 含占位符，跳过连库步骤，仅渲染示例看板。')
    all_ok = True
else:
    log('\n开始执行同步链路...')
    all_ok = True
    for i, (name, script) in enumerate(STEPS, 1):
        log(f'[{i}/{len(STEPS)}] {name} ...')
        r = subprocess.run(
            [sys.executable, os.path.join(BASE, script)],
            cwd=BASE, capture_output=True, text=True, encoding='utf-8', errors='replace'
        )
        if r.stdout:
            log(r.stdout[-800:])
        if r.returncode != 0:
            log(f'[FAIL] 第 {i} 步失败（{script} 返回码 {r.returncode}）')
            if r.stderr:
                log('----- 详细错误 -----')
                log(r.stderr[-2000:])
            all_ok = False
            break
        log(f'[OK] 第 {i} 步完成')

SYNC_FAILED = (not all_ok)

if SYNC_FAILED:
    log('\n[WARN] 同步未完成，看板仍会启动，但可能显示旧数据或空数据。')
    log('常见原因：')
    log('- 数据库有权限但某些表不存在/字段变更（联系 DBA）')
    log('- 磁盘空间不足')
    log('- 网络波动导致查询超时')
    log('- 数据库地址无法连接（请检查 db_conf.json 的 host / intranet_host 与内网/VPN）')
    log(f'\n完整日志：{LOG_FILE}')
    # 同步失败不再直接退出，继续启动本地服务，保证看板一定打得开
else:
    log('\n[OK] 同步全部完成！')

if placeholder_mode:
    # 占位符模式下，把"如何填回真值"明确打印出来
    log('\n' + '='*60)
    log('【如何填回 db_conf.json 真实值】')
    log('='*60)
    log('用记事本打开 db_conf.json，把以下字段改回您内网 MySQL 真实值：')
    log('  "host":     "您的内网域名或 IP（如 rm-xxx.aliyuncs.com 或 192.168.x.x）"')
    log('  "user":     "数据库用户名"')
    log('  "password": "数据库密码"')
    log('  "database": "目标库名"')
    log('  "intranet_host": "内网地址（如果有）"')
    log('常见备份位置：C:\\Users\\您的用户名\\AppData\\Local\\Local\\  或过往同事手中 zip')
    log('保存后再次双击 fix_and_sync.bat 即可拉真实数据。\n')

# --------------- 始终用现有数据重新生成看板（保证布局/功能为最新） ---------------
# 即便本次连库抽数失败，只要本地曾有 records.json，就重新生成 HTML，
# 让看板始终呈现最新版式与功能（数据可能是上一次成功的，页面顶部会提示）。
try:
    if os.path.exists(os.path.join(OUT, 'records.json')):
        log('\n[HTML] 用现有 records.json 重新生成看板页面...')
        r2 = subprocess.run(
            [sys.executable, os.path.join(BASE, 'gen_dashboard.py')],
            cwd=BASE, capture_output=True, text=True, encoding='utf-8', errors='replace'
        )
        if r2.returncode == 0:
            log('[OK] 看板页面已刷新为最新版式')
        else:
            log('[WARN] 看板页面生成失败，可能显示旧版式：' + (r2.stderr or '')[-300:])
    else:
        log('\n[WARN] 未找到 records.json，跳过页面生成（首次运行需先成功连库）。')
except Exception as e:
    log('[WARN] 重新生成看板页面时出错：' + str(e))

# --------------- 启动本地服务 ---------------
log('启动本地服务（http://127.0.0.1:8173）...')
# 启动 serve.py，不阻塞
subprocess.Popen(
    [sys.executable, os.path.join(BASE, 'serve.py')],
    cwd=BASE,
    creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
)

# 等待服务启动
time.sleep(3)

# 打开浏览器
url = 'http://127.0.0.1:8173'
try:
    webbrowser.open(url)
    log(f'已尝试打开浏览器：{url}')
except Exception as e:
    log(f'打开浏览器失败，请手动访问：{url}')

if SYNC_FAILED:
    log('\n[提醒] 本次同步未完成，看板已启动但数据可能非最新。')
    log('请查看上方错误并修复（多为数据库连接/网络问题），')
    log('修复后点击看板右上角「🔄 同步数据库」按钮即可刷新，无需重启。')
    if sys.platform == 'win32':
        open_log()

log('\n[DONE] 全部完成！如果浏览器没有自动打开，请手动访问 http://127.0.0.1:8173')
log('需要关闭服务时，关闭黑色命令行窗口即可。')
time.sleep(2)
