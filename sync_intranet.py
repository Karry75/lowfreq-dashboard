# -*- coding: utf-8 -*-
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
"""
低频看板 · 内网专用同步入口
============================
在公司内网/VPN 环境下，优先使用 db_conf.json 中的 intranet_host 同步数据库。
运行方式：
  python sync_intranet.py
  或双击 run_silent.bat（已自动选择内网优先）
"""
import os
import sys
import json

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import env
import auto_sync


def main():
    print("== 低频看板 · 内网同步模式 ==")
    conf_path = os.path.join(BASE, 'db_conf.json')
    if not os.path.exists(conf_path):
        print("[FAIL] 未找到 db_conf.json")
        return 1
    conf = json.load(open(conf_path, encoding='utf-8'))
    intranet = conf.get('intranet_host', '').strip()
    if not intranet:
        print("[WARN]️ db_conf.json 中 intranet_host 为空，将使用公网 host。")
    else:
        # 强制优先使用内网地址
        os.environ['LF_DB_HOST'] = intranet
        print(f"[OK] 已强制使用内网地址：{intranet}")

    return auto_sync.main()


if __name__ == '__main__':
    sys.exit(main())
