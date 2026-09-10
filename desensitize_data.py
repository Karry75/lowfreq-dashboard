#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
desensitize_data.py —— 数据脱敏工具（隐私合规）
================================================
把真实的 out/*.json 处理成「可公开、不含消费者隐私」的版本：
  1. 手机号 (ph/cph/phone/cur_phone/mobile 等 11 位号码) -> 186****1001 掩码
  2. 员工/接待人姓名 (rs/solver/assigned_solver/by_solver[].name/staff 列表等)
     -> 员工#01 / 员工#02 ...  （同一真实姓名始终映射到同一匿名编号）
  3. 街道(st)/社区(co) 等细粒度地址 -> 清空（保留 省/市/区 用于聚合分析）
  4. 数据库账号、密码、token 等凭证：本仓库从不收录（见 .gitignore）

设计原则：
  - 确定性脱敏：同一真实值永远得到同一脱敏值，跨文件关联不断裂。
  - 只做「最小必要」遮蔽：业务标签(低频唤醒/催缴欠租)、省/市/区分布、
    设备SN、换电柜点位、促成漏斗等全部保留，确保看板「真实感」不丢失。
  - 不修改任何原始文件：仅对传入的 out/ 目录做就地脱敏（仓库内的副本）。

用法：
  python desensitize_data.py [out_dir]
默认 out_dir = 脚本同级的 out/
"""
import json, os, re, sys

PHONE_RE = re.compile(r'^1[3-9]\d{9}$')

def mask_phone(num):
    """11 位手机号 -> 186****1001（保留号段与后 4 位，隐藏中间）。"""
    s = ''.join(c for c in str(num) if c.isdigit())
    if len(s) != 11 or not PHONE_RE.match(s):
        return num
    return s[:3] + '****' + s[-4:]

# 业务标签白名单：这些中文词不是姓名，绝不替换
BIZ_WORDS = {
    '低频', '唤醒', '催缴', '欠租', '协议', '到期', '提醒', '退订', '挽留', '换电',
    '跟进', '回访', '咨询', '运营', '直营', '代理', '个人', '企业', '已回访', '待回访',
    '低频唤醒', '催缴欠租', '协议到期提醒', '退订挽留', '换电提醒', '咨询',
}


def collect_names(out_dir):
    """汇总所有出现的员工/接待人姓名，保证跨文件映射一致。"""
    names = set()
    # staff.json
    p = os.path.join(out_dir, 'staff.json')
    if os.path.exists(p):
        d = json.load(open(p, encoding='utf-8'))
        names.update(d.get('staff', []))
        names.update(d.get('today_staff', []))
        names.update(d.get('quotas', {}).keys())
    # dispatch_history.json
    p = os.path.join(out_dir, 'dispatch_history.json')
    if os.path.exists(p):
        d = json.load(open(p, encoding='utf-8'))
        if isinstance(d, dict):
            for info in d.values():
                if isinstance(info, dict):
                    names.update(info.get('staff', []))
                    names.update(info.get('quotas', {}).keys())
    # assignments.json
    p = os.path.join(out_dir, 'assignments.json')
    if os.path.exists(p):
        d = json.load(open(p, encoding='utf-8'))
        for it in d.get('items', []):
            if isinstance(it, dict) and it.get('assigned_solver'):
                names.update([it['assigned_solver']])
    # records.json
    p = os.path.join(out_dir, 'records.json')
    if os.path.exists(p):
        d = json.load(open(p, encoding='utf-8'))
        for r in d.get('rows', []):
            if r.get('rs'):
                names.add(r['rs'])
        for sol in d.get('reception', []):
            if isinstance(sol, dict) and sol.get('solver'):
                names.add(sol['solver'])
        for v in d.get('reception_detail', {}).values():
            if isinstance(v, dict) and v.get('solver'):
                names.add(v['solver'])
    # effect_summary.json -> by_solver[].name
    p = os.path.join(out_dir, 'effect_summary.json')
    if os.path.exists(p):
        d = json.load(open(p, encoding='utf-8'))
        for sol in d.get('by_solver', []):
            if isinstance(sol, dict) and sol.get('name'):
                names.add(sol['name'])
    names.discard('')
    return names


def build_name_map(names):
    return {n: f'员工#{i+1:02d}' for i, n in enumerate(sorted(names))}


def anonymize(obj, name_map):
    """递归脱敏：手机号掩码、姓名替换、街道/社区清空。"""
    if isinstance(obj, dict):
        new = {}
        for k, v in obj.items():
            nk = name_map.get(k, k)          # dict key 若是姓名则改名
            if k in ('st', 'co') and isinstance(v, str):
                v = ''                       # 街道/社区清空
            new[nk] = anonymize(v, name_map)
        return new
    if isinstance(obj, list):
        return [anonymize(x, name_map) for x in obj]
    if isinstance(obj, str):
        if PHONE_RE.match(obj):
            return mask_phone(obj)
        if obj in name_map:
            return name_map[obj]
        return obj
    return obj


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
    assert os.path.isdir(out_dir), f'out 目录不存在: {out_dir}'
    names = collect_names(out_dir)
    name_map = build_name_map(names)
    print(f'[脱敏] 识别到 {len(name_map)} 个员工/接待人姓名 -> 匿名编号')
    for real, anon in list(name_map.items())[:8]:
        print(f'        {real} -> {anon}')
    if len(name_map) > 8:
        print(f'        ... 共 {len(name_map)} 个')

    targets = ['records.json', 'summary.json', 'dispatch_history.json',
               'assignments.json', 'staff.json', 'effect_summary.json']
    for fn in targets:
        fp = os.path.join(out_dir, fn)
        if not os.path.exists(fp):
            continue
        d = json.load(open(fp, encoding='utf-8'))
        d2 = anonymize(d, name_map)
        # staff.json 的 staff 列表本身也要替换
        if fn == 'staff.json' and isinstance(d2, dict):
            d2['staff'] = [name_map.get(s, s) for s in d2.get('staff', [])]
            d2['today_staff'] = [name_map.get(s, s) for s in d2.get('today_staff', [])]
            if isinstance(d2.get('quotas'), dict):
                d2['quotas'] = {name_map.get(k, k): v for k, v in d2['quotas'].items()}
        json.dump(d2, open(fp, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        print(f'[脱敏] 已处理 {fn}')
    print('[脱敏] 完成。请运行 gen_dashboard.py 重新生成看板。')


if __name__ == '__main__':
    main()
