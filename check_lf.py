# -*- coding: utf-8 -*-
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
"""
快速诊断：检查 out/records.json 里有多少低频用户、字段是否正常。
双击或在命令行运行：python check_lf.py
"""
import json, os
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, 'out')

rec_path = os.path.join(OUT, 'records.json')
if not os.path.exists(rec_path):
    print("[FAIL] 未找到 out/records.json，请先同步数据库。")
    input("按回车退出…")
    exit(1)

try:
    data = json.load(open(rec_path, encoding='utf-8'))
except Exception as e:
    print(f"[FAIL] 读取 records.json 失败：{e}")
    input("按回车退出…")
    exit(1)

rows = data.get('rows', [])
lf_rows = [r for r in rows if r.get('lf')]
print(f"[OK] records.json 读取成功")
print(f"   总记录数: {len(rows)}")
print(f"   低频协议数 (lf=1): {len(lf_rows)}")
if lf_rows:
    print(f"   示例低频协议ID: {lf_rows[0].get('id')}")
    print(f"   示例低频档位: {lf_rows[0].get('lv')} / {lf_rows[0].get('ln')}")
    print(f"   示例手机号: {lf_rows[0].get('ph')}")

asg_path = os.path.join(OUT, 'assignments.json')
if os.path.exists(asg_path):
    try:
        asg = json.load(open(asg_path, encoding='utf-8'))
        items = asg.get('items', [])
        print(f"   assignments.json 任务数: {len(items)}")
    except Exception as e:
        print(f"   assignments.json 读取失败：{e}")
else:
    print("   assignments.json 不存在")

input("\n按回车退出…")
