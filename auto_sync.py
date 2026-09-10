# -*- coding: utf-8 -*-
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
"""
低频用户看板 · 全自动化托管同步（本地运行，无需手动处理压缩包）
============================================================
本脚本在你的电脑上直接运行，不经过云沙箱：
  1) 自动检测 Python 环境
  2) 自动安装/升级依赖（pymysql、openpyxl）
  3) 自动判断公网/内网数据库，连上能用的那一条
  4) 自动执行完整同步链路
  5) 生成完成后自动打开看板

运行方式：
  · 双击 auto_sync.bat（推荐，有黑色窗口看进度）
  · 双击 run_silent.bat（静默，无窗口，适合定时任务）
  · 直接 python auto_sync.py
"""
import subprocess
import sys
import os
import webbrowser
import time

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, 'out')

# 导入本地环境工具
sys.path.insert(0, BASE)
import env


def log(msg):
    print(msg)
    sys.stdout.flush()


def open_html(path):
    """用系统默认浏览器打开看板。"""
    try:
        os.startfile(path)
        return True
    except Exception:
        pass
    try:
        subprocess.Popen(f'start "" "{path}"', shell=True)
        return True
    except Exception:
        pass
    try:
        return bool(webbrowser.open(path))
    except Exception:
        return False


def step(n, total, name, script):
    log(f"\n{'='*60}\n[{n}/{total}] {name}\n{'='*60}")
    r = subprocess.run([sys.executable, os.path.join(BASE, script)], cwd=BASE)
    if r.returncode != 0:
        log(f"\n[FAIL] 第 {n} 步失败（{script} 返回码 {r.returncode}），已停止。请检查上方报错。")
        return False
    log(f"[OK] 第 {n} 步完成。")
    return True


def run_sync_chain():
    """执行完整同步链路。"""
    steps = [
        ("连库抽数 → out/records.json", "build_lists.py"),
        ("并入短信 Excel（按手机号）", "merge_sms_excel.py"),
        ("生成看板 HTML", "gen_dashboard.py"),
        ("导出空号/停机专项清单 Excel", "export_special_lists.py"),
        # v10.12 起：回访名单改为手动生成（用户在「回访排班」Tab 选人员+配接待量+选电池产品后一键生成）
    ]
    for i, (name, script) in enumerate(steps, 1):
        if not step(i, len(steps), name, script):
            return False
    return True


def main():
    log("== 低频用户看板 · 全自动化托管同步 ==")
    log(f"运行目录：{BASE}")

    if not env.ensure_python():
        log("[FAIL] Python 版本不满足要求（需 3.8+）。")
        input("按回车退出…")
        return 1

    log(f"[OK] Python 环境已就绪：{sys.executable} ({sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro})")

    if not env.ensure_deps():
        log("[FAIL] 依赖安装失败。请尝试手动运行：python -m pip install pymysql openpyxl")
        input("按回车退出…")
        return 1
    log("[OK] 所有依赖均已就绪。")

    chosen_host = env.resolve_db_host()
    if not chosen_host:
        log("\n[FAIL] 数据库无法连接。")
        log("请检查：1) 是否已连公司内网/VPN；2) 阿里云 ADB 白名单是否包含本机 IP；3) db_conf.json 是否正确。")
        log("\n如需使用内网同步，请在 db_conf.json 中填入 intranet_host 并保存。")
        input("按回车退出…")
        return 1
    log(f"[OK] 将使用数据库地址：{chosen_host}")

    start = time.time()
    ok = run_sync_chain()
    elapsed = time.time() - start

    if ok:
        out_html = os.path.join(OUT, 'followup_dashboard.html')
        if os.path.exists(out_html):
            size_mb = os.path.getsize(out_html) / 1024 / 1024
            log(f"\n[DONE] 同步完成！耗时 {elapsed:.1f} 秒。看板大小 {size_mb:.1f} MB。")
            log("正在启动本地服务并自动打开看板（同步按钮将变为可用）…")
            try:
                # 拉起本地服务（提供 http://127.0.0.1:8173，并确保 window.__SERVE__ 注入）
                import serve
                serve.main()
                return 0
            except Exception as e:
                log(f"[WARN]️ 启动本地服务失败：{e}，已回退为直接打开文件（此时同步按钮为灰色）。")
                open_html(out_html)
        else:
            log("\n[WARN]️ 未找到生成的看板文件，请检查第 3 步日志。")
    else:
        log(f"\n[FAIL] 同步失败，耗时 {elapsed:.1f} 秒。")
        input("按回车退出…")
        return 1

    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("\n已取消。")
    except Exception as e:
        log(f"\n[FAIL] 运行出错：{repr(e)}")
        import traceback
        traceback.print_exc()
        input("按回车退出…")
