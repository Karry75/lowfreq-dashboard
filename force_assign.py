# -*- coding: utf-8 -*-
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
"""
强制重新分配所有低频协议（清空自动分配/再次回访任务后按当前 records.json 重新分配）。
用于排查「回访排班」没有名单时一键修复，或名单与当前低频用户不一致时重置。
"""
import sys
from assign import run_assignment

if __name__ == '__main__':
    print("== 强制重新分配低频协议 ==")
    print("提示：这会清空之前自动分配和再次回访任务，保留手动添加的任务。")
    run_assignment(force_all=True)
