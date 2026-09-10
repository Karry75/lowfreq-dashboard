# -*- coding: utf-8 -*-
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
"""
低频用户 · 欠租催收  ——  本地一键同步脚本（在你的电脑上运行）
============================================================
整条链路全部在本机执行，不经过任何云沙箱：

  1) build_lists.py          —— 连阿里云 ADB，抽最新数据 → out/records.json
  2) merge_sms_excel.py      —— 把 uploads_sms/ 下两份短信 Excel 按手机号并入 → out/records.json
  3) gen_dashboard.py        —— 读取 out/records.json，生成 out/followup_dashboard.html 看板
  4) export_special_lists.py —— 导出 out/特殊清单_空号停机.xlsx

前置条件：
  - 本机已安装 Python 3.8+（安装时勾选 "Add Python to PATH"）
  - 本机出口 IP 已在阿里云 ADB 白名单（你电脑 IP 已加白）
  - 依赖：pymysql、openpyxl（run_sync.bat 会自动安装）

运行方式：
  双击同目录的 run_sync.bat 即可（自动装依赖并启动本脚本）。

生成完成后，会自动用默认浏览器打开 out/followup_dashboard.html 看板。
如需重新同步，再次双击 run_sync.bat。
"""
import subprocess, sys, os, webbrowser

BASE = os.path.dirname(os.path.abspath(__file__))


def open_html(path):
    """用系统默认浏览器打开看板。三种方式连续尝试，确保弹窗。"""
    # 1) os.startfile（最原生）
    try:
        os.startfile(path)
        return True
    except Exception:
        pass
    # 2) cmd start（对含中文/空格路径也稳，非阻塞避免卡住）
    try:
        subprocess.Popen(f'start "" "{path}"', shell=True)
        return True
    except Exception:
        pass
    # 3) webbrowser 回退
    try:
        return bool(webbrowser.open(path))
    except Exception:
        return False


def step(n, total, name, script):
    print(f"\n{'='*60}\n[{n}/{total}] {name}\n{'='*60}")
    r = subprocess.run([sys.executable, os.path.join(BASE, script)], cwd=BASE)
    if r.returncode != 0:
        print(f"\n[FAIL] 第 {n} 步失败（{script} 返回码 {r.returncode}），已停止。请检查上方报错。")
        sys.exit(r.returncode)
    print(f"[OK] 第 {n} 步完成。")


def main():
    print("== 低频用户看板 · 本地同步开始 ==")
    print("运行目录:", BASE)
    step(1, 4, "连库抽数 → out/records.json", "build_lists.py")
    step(2, 4, "并入短信 Excel（按手机号）", "merge_sms_excel.py")
    step(3, 4, "生成看板 HTML", "gen_dashboard.py")
    step(4, 4, "导出空号/停机专项清单 Excel", "export_special_lists.py")
    # v10.12 起：回访名单改为手动生成（用户在「回访排班」Tab 选人员+配接待量+选电池产品后一键生成）

    out_html = os.path.join(BASE, 'out', 'followup_dashboard.html')
    if os.path.exists(out_html):
        size_mb = os.path.getsize(out_html) / 1024 / 1024
        print(f"\n[DONE] 全部完成！看板已生成：{out_html}  ({size_mb:.1f} MB)")
        if open_html(out_html):
            print("已自动用默认浏览器打开看板。")
        else:
            print("（未能自动打开，请手动双击 out/followup_dashboard.html）")
    else:
        print("\n[WARN] 未找到生成的看板文件，请检查第 3 步日志。")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n已取消。")
    except Exception as e:
        print("\n[FAIL] 运行出错:", repr(e))
        import traceback
        traceback.print_exc()
