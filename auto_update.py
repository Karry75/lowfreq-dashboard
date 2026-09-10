# -*- coding: utf-8 -*-
import sys, os, json, zipfile, shutil, glob, subprocess, time, urllib.request
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
"""
低频看板 · 一键更新并启动（全自动）
===================================
双击 auto_update_sync.bat 即可：
  ① 优先从 update_url.txt 里的稳定下载链接拉取最新包（真正免手动下载）；
  ② 若没有配置链接，则自动查找本目录 / updates/ / 下载目录里最新的
     lowfreq_local_*.zip；
  ③ 自动解压并覆盖代码文件，保留 out/、uploads_sms/、db_conf.json、
     staff.json、update_url.txt（你的数据与配置不丢）；
  ④ 解压后自动执行数据同步（连库抽数→生成看板→分配回访）并启动本地服务。

全程无需手动解压、无需手动点 fix_and_sync.bat。
"""
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, 'out')
# v10.28.35：保留列表已含 staff_auth.seed.json（首次安装解压、之后保留，不再被升级覆盖）
UPLOADS = os.path.join(BASE, 'uploads_sms')

# 更新时绝不覆盖的目录与文件（你的数据与配置）
# v10.28.15：把 staff_auth.json 加入保留列表（之前漏掉导致"升级后账号被清空"）。
#   staff_auth.json 是 serve.py 的真实登录凭证（admin/boss/wang/li 等账号 + sha256 加盐密码），
#   一旦被新包里的同名文件覆盖，管理员手工添加的账号就会全丢。包内仅作 seed 用途，真实凭证永远保留本地版。
# v10.28.35：把 staff_auth.seed.json 也加入保留列表——首次运行（本地不存在）会从包内解压出来，
#   之后升级不再覆盖（避免把用户改过的默认密码模板刷回出厂值）。
PRESERVE_DIRS = {'out', 'uploads_sms', '__pycache__'}
PRESERVE_FILES = {
    'db_conf.json',
    'staff.json',
    'staff_auth.json',   # v10.28.15：登录账号与加盐密码（关键）
    'staff_auth.seed.json',  # v10.28.35：默认凭证种子（首次安装解压，之后保留）
    'update_url.txt',
    'battery_calibration.json',  # 若用户单独把电量校准常量提取到此文件
}


def log(m):
    print(m)
    sys.stdout.flush()


def find_local_zip():
    candidates = []
    for pat in [os.path.join(BASE, 'lowfreq_local_*.zip'),
                os.path.join(BASE, 'updates', 'lowfreq_local_*.zip')]:
        candidates += glob.glob(pat)
    dl = os.path.join(os.path.expanduser('~'), 'Downloads')
    if os.path.isdir(dl):
        candidates += glob.glob(os.path.join(dl, 'lowfreq_local_*.zip'))
    if not candidates:
        return None
    candidates.sort(key=os.path.getmtime, reverse=True)
    return candidates[0]


def download(url, dest):
    log(f"↓ 下载最新包：{url[:80]}...")
    req = urllib.request.Request(url, headers={'User-Agent': 'lowfreq-updater'})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    with open(dest, 'wb') as f:
        f.write(data)
    return len(data)


def extract_and_merge(zip_path):
    tmp = os.path.join(BASE, '_upd_tmp')
    if os.path.exists(tmp):
        shutil.rmtree(tmp)
    os.makedirs(tmp, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(tmp)
    # 定位压缩包内的程序目录（含 serve.py）
    src = None
    for name in os.listdir(tmp):
        p = os.path.join(tmp, name)
        if os.path.isdir(p) and os.path.exists(os.path.join(p, 'serve.py')):
            src = p
            break
    if not src and os.path.exists(os.path.join(tmp, 'serve.py')):
        src = tmp
    if not src:
        raise RuntimeError('压缩包内未找到 lowfreq_local 程序目录')

    # 备份旧版（放到 BASE 之外，避免递归备份）
    parent = os.path.dirname(BASE)
    bak_name = os.path.basename(BASE) + '_backup_' + time.strftime('%Y%m%d_%H%M%S')
    bak = os.path.join(parent, bak_name)
    shutil.copytree(BASE, bak, ignore=shutil.ignore_patterns(
        '_upd_tmp', '_backup_*', '__pycache__'))
    log(f'[备份] 旧版已备份到 {bak}')

    # 覆盖代码文件，跳过需保留的数据/配置
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(BASE, item)
        if item in PRESERVE_DIRS:
            continue
        if item in PRESERVE_FILES and os.path.exists(d):
            continue
        if os.path.isdir(s):
            if os.path.exists(d):
                shutil.rmtree(d)
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)
    shutil.rmtree(tmp)
    log('[完成] 代码已更新（已保留 out/、uploads_sms/、db_conf.json、staff.json、update_url.txt）')


def run_sync():
    sync_script = os.path.join(BASE, 'fix_and_sync.py')
    if not os.path.exists(sync_script):
        log('[错误] 未找到 fix_and_sync.py，无法启动同步。')
        input('Press ENTER to exit...')
        return
    log('[同步] 开始执行数据同步并启动服务…')
    cmd = [sys.executable, sync_script]
    log(f'[命令] {" ".join(cmd)}')
    subprocess.Popen(
        cmd,
        cwd=BASE,
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
    )
    log('[完成] 已启动同步与服务，请稍候浏览器自动打开 http://127.0.0.1:8173')


def main():
    log('== 低频看板 · 一键更新并启动 ==')
    url = ''
    url_file = os.path.join(BASE, 'update_url.txt')
    if os.path.exists(url_file):
        try:
            u = open(url_file, encoding='utf-8').read().strip()
            if u and u.lower().startswith('http'):
                url = u
        except Exception:
            pass

    zip_path = None
    if url:
        log('[网络] 检测到 update_url.txt 中的下载链接，自动拉取最新包…')
        zip_path = os.path.join(BASE, '_update_latest.zip')
        try:
            download(url, zip_path)
            log('[下载] 完成')
        except Exception as e:
            log(f'[警告] 网络下载失败：{e}，改成本地压缩包模式。')
            if os.path.exists(zip_path):
                os.remove(zip_path)
            zip_path = None

    if not zip_path:
        zip_path = find_local_zip()
        if not zip_path:
            log('[提示] 未找到下载链接，也未在本地找到更新包，将直接用当前代码启动看板。')
            log('（如需升级，请把稳定下载链接写入 update_url.txt，或把新版压缩包放到本文件夹 / updates/ / 下载目录）')
            run_sync()
            return

    log(f'[来源] {os.path.basename(zip_path)}')
    try:
        extract_and_merge(zip_path)
    except Exception as e:
        log(f'[失败] 更新出错：{e}')
        input('Press ENTER to exit...')
        return

    # 仅删除“我们下载的”临时包；用户手动放的 zip 保留
    if url and os.path.exists(zip_path):
        try:
            os.remove(zip_path)
        except Exception:
            pass

    run_sync()


if __name__ == '__main__':
    main()
