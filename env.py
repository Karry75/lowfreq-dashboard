# -*- coding: utf-8 -*-
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
"""
低频看板 · 环境托管工具
======================
被 auto_sync.py 与 serve.py 共同导入：
  - 自动检测 Python 版本
  - 自动安装/升级依赖
  - 自动判断公网/内网数据库地址

所有逻辑在本机执行，不依赖任何云沙箱或压缩包。
"""
import sys
import os
import json
import subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
DB_CONF = os.path.join(BASE, 'db_conf.json')

REQUIRED_DEPS = [
    ("pymysql", "pymysql"),
    ("openpyxl", "openpyxl"),
]


def log(msg):
    print(msg)
    sys.stdout.flush()


def ensure_python():
    """确认当前解释器为 Python 3.8+。"""
    v = sys.version_info
    if v.major != 3 or v.minor < 8:
        log(f"[FAIL] 当前 Python 版本为 {v.major}.{v.minor}，需要 Python 3.8+。")
        return False
    return True


def ensure_deps(silent=False):
    """自动安装缺失依赖。返回是否成功。"""
    missing = []
    for pkg, import_name in REQUIRED_DEPS:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg)

    if not missing:
        return True

    if not silent:
        log(f"[ZIP] 自动安装依赖：{', '.join(missing)} ...")

    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "--quiet"] + missing
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        if not silent:
            log(f"[FAIL] 依赖安装失败：{r.stderr or r.stdout}")
        return False

    # 验证
    for pkg, import_name in REQUIRED_DEPS:
        try:
            __import__(import_name)
        except ImportError:
            if not silent:
                log(f"[FAIL] 安装后仍无法导入 {pkg}")
            return False
    return True


def test_db_connection(host, conf):
    """测试单个数据库地址是否可连，返回 (ok, err_msg)。"""
    try:
        import pymysql
        conn = pymysql.connect(
            host=host, port=conf.get('port', 3306), user=conf['user'],
            password=conf['password'], database=conf['database'],
            charset='utf8mb4', connect_timeout=conf.get('connect_timeout', 10),
            read_timeout=conf.get('read_timeout', 30),
            write_timeout=conf.get('write_timeout', 30),
            cursorclass=pymysql.cursors.DictCursor
        )
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
        conn.close()
        return True, None
    except Exception as e:
        return False, str(e)


def resolve_db_host():
    """
    自动判断使用公网 host 还是内网 intranet_host。
    把选中的地址写入环境变量 LF_DB_HOST，供 build_lists.py 读取。
    """
    if not os.path.exists(DB_CONF):
        return None

    conf = json.load(open(DB_CONF, encoding='utf-8'))
    env_host = os.environ.get('LF_DB_HOST', '').strip()
    intranet = conf.get('intranet_host', '').strip()
    public = conf.get('host', '').strip()

    candidates = []
    if env_host:
        candidates.append(('环境变量', env_host))
    if intranet and intranet not in [h for _, h in candidates]:
        candidates.append(('内网', intranet))
    if public and public not in [h for _, h in candidates]:
        candidates.append(('公网', public))

    for label, host in candidates:
        ok, _ = test_db_connection(host, conf)
        if ok:
            os.environ['LF_DB_HOST'] = host
            return host
    return None
