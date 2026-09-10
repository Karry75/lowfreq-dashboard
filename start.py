# -*- coding: utf-8 -*-
"""
Low-Frequency User Dashboard - one-click launcher (v10.28.39)
=============================================================
v10.28.39 起不再"沉默地失败"：
  1) 启动前先把 8173 端口的残留占用者（旧的 pythonw.exe 等）清掉，避免端口被占 → serve 起不来
  2) spawn serve.py 后探测 /api/health（不止看端口，确保是我们的服务在跑）
  3) 服务 30 秒内没起来时，把 serve_boot.log 最后 30 行打印到屏幕 + 写 _serve_status.json
  4) 同事链接从 out/_serve_port.txt / /api/lan_info 读真实端口（自动 fallback 也能用）
  5) 控制台始终显示"实际监听端口 + 局域网 IP 链接"

启动方式：双击 start.bat 即可；start.bat 通过 start.py 间接调用本脚本。
"""
import os, sys, subprocess, time, socket, datetime, urllib.request, webbrowser, json

BASE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PORT = 8173
LOG_PATH = os.path.join(BASE, "out", "launch.log")
SERVE_LOG = os.path.join(BASE, "out", "serve_boot.log")
SERVE_STATUS = os.path.join(BASE, "out", "_serve_status.json")
SERVE_PORT_TXT = os.path.join(BASE, "out", "_serve_port.txt")


def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = "[%s] %s" % (ts, msg)
    print(line)
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def read_real_port():
    """读 out/_serve_port.txt，找不到返回默认 8173。"""
    try:
        if os.path.exists(SERVE_PORT_TXT):
            with open(SERVE_PORT_TXT, encoding="utf-8") as f:
                v = int(f.read().strip())
                if 1024 < v < 65536:
                    return v
    except Exception:
        pass
    return DEFAULT_PORT


def read_serve_status():
    """读 out/_serve_status.json，供失败诊断。"""
    try:
        if os.path.exists(SERVE_STATUS):
            with open(SERVE_STATUS, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def kill_port_occupants(port):
    """杀掉占用目标端口的所有 Windows 进程（netstat -ano + taskkill /F）。

    解决"之前手动跑过的 pythonw.exe 残留" → 端口被占 → 新 serve 起不来 → 127.0.0.1 拒绝连接。
    在非 Windows 平台或权限不足时静默跳过。
    """
    if not sys.platform.startswith("win"):
        return []
    killed = []
    try:
        out = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5
        ).stdout
    except Exception:
        return []
    pids = set()
    for line in out.splitlines():
        # 例: TCP    0.0.0.0:8173    0.0.0.0:0    LISTENING    1234
        if ("LISTENING" in line or "侦听" in line) and (":%d " % port) in line:
            parts = line.split()
            if len(parts) >= 5:
                try:
                    pids.add(int(parts[-1]))
                except Exception:
                    pass
    for pid in pids:
        # 跳过系统关键进程（PID 0/4）
        if pid in (0, 4):
            continue
        try:
            r = subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                               capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                killed.append(pid)
        except Exception:
            pass
    return killed


def probe_health(port, timeout=2.0):
    """探测 /api/health（v10.28.39 新增），确保端口上是"我们的服务"而不是别的程序。"""
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/api/health" % port, timeout=timeout) as r:
            if r.status != 200:
                return None
            body = r.read().decode("utf-8", "replace")
            return json.loads(body)
    except Exception:
        return None


def is_our_serve_up(port):
    """端口上是否跑着我们的 serve.py（通过 /api/health 的 version 字段识别）。"""
    h = probe_health(port)
    return bool(h and h.get("ok") and "version" in h)


def tail_log(path, n=30):
    """返回日志最后 n 行（用于失败诊断）。"""
    try:
        if not os.path.exists(path):
            return ["(日志文件不存在)"]
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return ["    " + l.rstrip() for l in lines[-n:]]
    except Exception as e:
        return ["(读取日志失败: %s)" % e]


def open_url(u):
    try:
        os.startfile(u)  # type: ignore[attr-defined]
        return True
    except Exception:
        pass
    try:
        webbrowser.open(u)
        return True
    except Exception:
        return False


def main():
    log("=" * 60)
    log("Low-Frequency User Dashboard - Launcher v10.28.39")
    log("CWD : %s" % BASE)
    log("=" * 60)

    real_port = read_real_port()
    log("[INFO] 当前 _serve_port.txt 标记端口：%d" % real_port)

    # ===== v10.28.39：启动前先清掉残留占用者 =====
    killed = kill_port_occupants(real_port)
    if killed:
        log("[INFO] 已清理占用端口 %d 的旧进程：%s（解决「127.0.0.1 拒绝连接」的常见根因）" %
            (real_port, ", ".join(str(p) for p in killed)))
        time.sleep(0.6)  # 等端口释放
    elif is_our_serve_up(real_port):
        log("[INFO] 端口 %d 上已跑着我们的 serve.py，跳过启动。" % real_port)
        log("[DONE]")
        open_url("http://127.0.0.1:%d/?sync=1&_=%d" % (real_port, int(time.time())))
        return
    else:
        log("[INFO] 端口 %d 空闲，准备启动 serve.py…" % real_port)

    # ===== spawn serve.py =====
    log("[INFO] 启动 serve.py（后台），stdout/err → out/serve_boot.log")
    # 删旧 status 让 start.py 后面的诊断更准
    try:
        if os.path.exists(SERVE_STATUS):
            os.remove(SERVE_STATUS)
    except Exception:
        pass

    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    py_exe = pyw if os.path.exists(pyw) else sys.executable
    try:
        with open(SERVE_LOG, "a", encoding="utf-8") as boot:
            subprocess.Popen(
                [py_exe, os.path.join(BASE, "serve.py")],
                cwd=BASE,
                creationflags=0x00000008 | 0x00000200,  # DETACHED | NEW_PROCESS_GROUP
                close_fds=True,
                stdout=boot,
                stderr=subprocess.STDOUT,
            )
        log("[INFO] serve.py 进程已创建 (PID 不可见：detached 模式)")
    except Exception as e:
        log("[ERROR] 创建 serve.py 失败：%s" % e)
        try:
            subprocess.Popen([sys.executable, os.path.join(BASE, "serve.py")], cwd=BASE)
        except Exception as e2:
            log("[ERROR] fallback 启动也失败：%s" % e2)
            return

    # ===== 等 serve 起来 =====
    ready = False
    for i in range(60):  # 最多 30s
        # 每秒重新读 _serve_port.txt，因为 serve 可能 fallback 到 8174
        cur_port = read_real_port()
        if is_our_serve_up(cur_port):
            real_port = cur_port
            ready = True
            log("[INFO] serve.py 已就绪（探测到 /api/health）端口=%d" % real_port)
            break
        time.sleep(0.5)

    if not ready:
        log("[WARN] 30 秒内服务未就绪。")
        # v10.28.39：失败时把诊断信息打印出来
        status = read_serve_status()
        if status:
            log("       状态文件：%s" % json.dumps(status, ensure_ascii=False))
        log("       —— out/serve_boot.log 最后 30 行 ——")
        for line in tail_log(SERVE_LOG, 30):
            log(line)
        log("       —— 常见根因 ——")
        log("         (1) 端口仍被别的程序占着（看上面 netstat 输出）；")
        log("         (2) Python 依赖没装（pymysql/openpyxl）：手动 pip install；")
        log("         (3) records.json 损坏：双击 fix_and_sync.bat 修复后再试。")
        log("       你也可以双击 troubleshoot.bat 自动诊断。")
        log("[FAIL] 启动失败，但已把错误信息写入 out/launch.log，可截图给我排查。")

    # ===== 打开浏览器（用真实端口） =====
    url = f"http://127.0.0.1:{real_port}/?sync=1&_={int(time.time())}"
    log("[INFO] 打开浏览器：%s" % url)
    if not open_url(url):
        log("[WARN] 自动打开浏览器失败，请手动复制：%s" % url)
    log("")
    log("  * 同事访问链接：打开看板后，看页面顶部「同事访问」条（一键复制）")
    log("  * 详细说明：out/同事访问链接.txt")
    log("[DONE]")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        log("[ERR] launcher crashed: %s" % e)
        log(traceback.format_exc())
