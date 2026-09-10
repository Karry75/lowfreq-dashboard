# -*- coding: utf-8 -*-
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
"""
低频看板 · 一键自动更新器（无需手动处理压缩包）
================================================
双击 update.bat 即可：读取更新公告页 / update_url.txt -> 拿到最新 zip ->
自动下载 -> 备份旧版 -> 自动解压覆盖（保留 out/ 和 uploads_sms/）-> 完成。

若项目是 git 仓库，会优先使用 git pull 更新，真正做到无压缩包。

全程无需手动下载、解压、粘贴链接。
若提示"更新链接过期"，请在会话里告诉我一声，我刷新后你再双击一次即可。
"""
import os
import sys
import json
import zipfile
import shutil
import urllib.request
import re
import time
import subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, 'out')
UPLOADS = os.path.join(BASE, 'uploads_sms')

# 固定"更新公告页"（由开发者维护；若平台支持长期公开链接可填此处，地址不变）
ANNOUNCE_URL = ""
# 内置最新下载地址（开发者每次打包时写入，用户无需手动粘贴；受平台签名时效限制，约60分钟，过期后请让我刷新）
# 当前最新下载短链由助手在会话中提供，也可写入 update_url.txt 后双击 update.bat 自动更新。
BUILTIN_URL = ""
LOCAL_VER = os.path.join(OUT, 'update_version.json')
URL_FILE = os.path.join(BASE, 'update_url.txt')


def log(msg):
    print(msg)
    sys.stdout.flush()


def read_local_version():
    try:
        return json.load(open(LOCAL_VER, encoding='utf-8'))
    except Exception:
        return {'version': '0'}


def fetch_announce():
    """读取公告页，提取 version 与 download_url。失败返回 None。"""
    try:
        req = urllib.request.Request(ANNOUNCE_URL, headers={'User-Agent': 'lowfreq-updater'})
        html = urllib.request.urlopen(req, timeout=20).read().decode('utf-8', 'ignore')
    except Exception as e:
        log(f"[WARN] 读取更新公告页失败：{e}")
        return None
    html = html.replace('&amp;', '&')
    ver = None
    idx = html.find('lowfreq_update_version')
    if idx >= 0:
        m = re.search(r'lowfreq_update_version:\s*([\w\.\-]+)', html[idx:idx + 200])
        if m:
            ver = m.group(1)
    url = None
    idx = html.find('lowfreq_update_url')
    if idx >= 0:
        m = re.search(r'https?://[^\s"<>]+', html[idx:idx + 4000])
        if m:
            url = m.group(0)
    if not url:
        return None
    return {'version': ver or 'unknown', 'url': url}


def download(url, dest):
    log(f"↓ 下载更新包：{url[:80]}...")
    req = urllib.request.Request(url, headers={'User-Agent': 'lowfreq-updater'})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    with open(dest, 'wb') as f:
        f.write(data)
    return len(data)


def extract(zip_path):
    log("[ZIP] 解压并更新文件...")
    tmp = os.path.join(BASE, '_upd_tmp')
    if os.path.exists(tmp):
        shutil.rmtree(tmp)
    os.makedirs(tmp, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(tmp)
    src = None
    for name in os.listdir(tmp):
        p = os.path.join(tmp, name)
        if os.path.isdir(p) and os.path.exists(os.path.join(p, 'serve.py')):
            src = p
            break
    if not src:
        if os.path.exists(os.path.join(tmp, 'serve.py')):
            src = tmp
    if not src:
        raise RuntimeError("压缩包内未找到 lowfreq_local 程序目录")
    bak = os.path.join(BASE, '_backup_' + time.strftime('%Y%m%d_%H%M%S'))
    shutil.copytree(BASE, bak, ignore=shutil.ignore_patterns('_upd_tmp', os.path.basename(bak)))
    log(f"[FOLDER] 已备份旧版到：{bak}")
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(BASE, item)
        if item in ('out', 'uploads_sms'):
            continue
        if os.path.isdir(s):
            if os.path.exists(d):
                shutil.rmtree(d)
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)
    shutil.rmtree(tmp)
    log("[OK] 文件已覆盖更新。")


def resolve_url():
    """按优先级获取最新下载地址：内置 > 公告页 > 本地文件 > 交互输入。"""
    if BUILTIN_URL:
        return BUILTIN_URL, 'builtin'
    if ANNOUNCE_URL:
        ann = fetch_announce()
        if ann and ann.get('url'):
            return ann['url'], 'announce'
    if os.path.exists(URL_FILE):
        try:
            u = open(URL_FILE, encoding='utf-8').read().strip()
            if u:
                return u, 'file'
        except Exception:
            pass
    log("请输入最新下载链接（由开发者在会话里提供，可粘贴到本目录 update_url.txt 后免输入）：")
    return input("链接> ").strip(), 'input'


def try_git_pull():
    """若 BASE 是 git 仓库，优先 git pull 更新（真正无压缩包）。"""
    git_dir = os.path.join(BASE, '.git')
    if not os.path.isdir(git_dir):
        return False
    log("[BRANCH] 检测到 git 仓库，优先尝试 git pull 更新...")
    r = subprocess.run(['git', 'pull'], cwd=BASE, capture_output=True, text=True)
    if r.returncode == 0:
        log("[OK] git pull 成功：")
        log(r.stdout or '(无输出)')
        return True
    else:
        log(f"[WARN] git pull 失败：{r.stderr or r.stdout}")
        log("将回退到 zip 下载更新。")
        return False


def main():
    log("== 低频看板 · 一键自动更新 ==")

    # 优先 git 无压缩包更新
    if try_git_pull():
        json.dump({'version': 'git-latest', 'updated_at': time.strftime('%Y-%m-%d %H:%M:%S')},
                  open(LOCAL_VER, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        log("[DONE] 更新完成！已使用 git 拉取最新代码。")
        log("如需立即同步数据，请双击 auto_sync.bat 或 run_sync.bat。")
        input("按回车退出…")
        return

    url, src = resolve_url()
    if not url:
        log("[FAIL] 没有可用的下载地址。请在会话里向我索取最新链接，或写入 update_url.txt。")
        input("按回车退出…")
        return
    log(f"来源：{src} | 地址：{url[:80]}...")
    local = read_local_version()
    try:
        zip_path = os.path.join(BASE, '_update_latest.zip')
        download(url, zip_path)
        extract(zip_path)
        os.remove(zip_path)
        os.makedirs(OUT, exist_ok=True)
        json.dump({'version': 'latest', 'updated_at': time.strftime('%Y-%m-%d %H:%M:%S')},
                  open(LOCAL_VER, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        log("[DONE] 更新完成！已自动下载、解压并覆盖旧文件，你的 out/ 和 uploads_sms/ 数据已保留。")
        log("请重新双击 run_sync.bat 启动（若已在运行，请先关闭黑色服务窗口再重开）。")
    except Exception as e:
        log(f"[FAIL] 更新失败：{e}")
        log("若提示签名/过期类错误，说明链接已失效，请在会话里告诉我，我刷新链接后你再双击一次本程序。")
    input("按回车退出…")


if __name__ == '__main__':
    main()
