"""
should_follow_up
================

判断用户是否需要回访。

业务规则（来自"低频用户 · 欠租催收回访看板"接待明细数据）：
    给定用户的电池操作历史记录列表，根据特定规则判断该用户是否需要回访。
    输入为一条或多条操作记录（每条记录至少包含：操作类型、操作时间、电池SN），
    输出为一个布尔值（True 表示需要回访，False 表示不需要）。

判定核心：
    1) 取该用户的「最后一次操作」（按 操作时间 字段升序排序后的最后一条）；
       注意：必须按"操作时间"准确排序判定，不得依赖记录在列表中的原始顺序。
    2) 若最后一条同时满足以下**两条**，则判定为 **无需回访**（返回 False，
       应从回访名单中过滤）：
           a. 操作类型 == "柜内归还电池"
           b. 该条记录的 电池SN == "暂无电池"  （说明用户手中已无电池）
    3) 其余情况一律判定为 **需要回访**（返回 True）。

边界场景（按要求全覆盖）：
    - 列表为空                      -> True（视为需要回访）
    - 电池SN 字段缺失 / 为空值       -> 不视为"暂无电池"，按常规处理（命中 True）
    - 操作时间字段缺失 / 非法        -> 视为"最早"，按原始索引 i 兜底，排序不抛错
    - 多条记录操作时间相同           -> 使用 Python 稳定排序（TimSort），
                                        按输入顺序的"后者"视为"更晚"
    - 字段名中英文别名都能识别：
        操作时间/op_time/opTime，操作类型/op_type/opType，电池SN/battery_sn/sn
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# ============ 业务常量（与看板字段保持一致，可被外部覆盖） ============
NO_BATTERY_SN: str = "暂无电池"      # 电池SN 取该值即代表"用户手中已无电池"
RETURN_OP_TYPE: str = "柜内归还电池"  # 操作类型 取该值即代表"柜内归还电池"动作

# 字段名兼容：不同来源（看板、DB、API）的中英文键名都能识别
TIME_KEYS: Tuple[str, ...] = ("操作时间", "op_time", "opTime", "operation_time")
TYPE_KEYS: Tuple[str, ...] = ("操作类型", "op_type", "opType", "operation_type")
SN_KEYS:   Tuple[str, ...] = ("电池SN", "battery_sn", "sn", "batterySn")


# =========================== 内部工具函数 ===========================
def _get_field(rec: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[Any]:
    """按多个候选字段名取第一个存在且非 None 的值；都不存在返回 None。"""
    for k in keys:
        if k in rec:
            v = rec[k]
            if v is not None:
                return v
    return None


def _parse_time(t: Any) -> Optional[float]:
    """把操作时间规整为可比较的"秒级"时间戳；解析失败返回 None。

    支持：
      - datetime / pd.Timestamp 等带 .timestamp() 方法的对象
      - int / float 数字型时间戳（秒或毫秒都会自动归一）
      - 'YYYY-MM-DD HH:MM:SS' / 'YYYY-MM-DDTHH:MM:SS[.ffffff]' / 'YYYY/MM/DD HH:MM:SS'
      - 'YYYY-MM-DD' / 'YYYY/MM/DD'
      - 退回到 pandas 解析更复杂的时间字符串
    """
    if t is None or t == "":
        return None

    # 1) 带 .timestamp() 方法的对象（datetime / pd.Timestamp / 等等）
    try:
        ts = getattr(t, "timestamp", None)
        if callable(ts):
            v = float(ts())
            return v / 1000.0 if v > 1e12 else v   # 自动归一毫秒 -> 秒
    except Exception:
        pass

    # 2) 数字
    if isinstance(t, (int, float)):
        try:
            v = float(t)
            return v / 1000.0 if v > 1e12 else v   # 自动归一毫秒 -> 秒
        except Exception:
            return None

    s = str(t).strip()
    if not s:
        return None

    # 3) 数字字符串
    try:
        v = float(s)
        return v / 1000.0 if v > 1e12 else v
    except Exception:
        pass

    # 4) 常见字符串格式
    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y/%m/%d",
    )
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).timestamp()
        except ValueError:
            continue

    # 5) 最后退到 pandas（项目已有依赖）
    try:
        import pandas as pd  # type: ignore
        v = float(pd.Timestamp(s).timestamp())
        return v / 1000.0 if v > 1e12 else v
    except Exception:
        return None


def _last_record(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """从记录列表中挑选"最后一次操作"。

    排序策略（关键）：
      1) 解析成功的有效时间按时间戳升序；
      2) 解析失败的记录视为"最早"（用 -1e18 + i_i），仍按原顺序 i 兜底递增。
         ——这样保证：
            a) 排序不会抛错；
            b) 当所有记录都缺时间时，原始索引最大者成为"最后一条"（按记录顺序兜底）；
            c) 当只有部分记录缺时间时，有效时间最新者稳赢。
      3) 使用 Python 稳定排序（TimSort），
         主键=时间戳，副键=原索引 i：同时间戳下，"输入顺序在后的"胜出，视为"更晚"。
    """
    if not records:
        raise ValueError("records must be non-empty (caller should guard)")

    indexed = []
    for i, r in enumerate(records):
        ts = _parse_time(_get_field(r, TIME_KEYS))
        if ts is None:
            sort_key = -1e18 - i   # 缺失/非法 -> 视为最早，原始顺序越靠后 sort_key 越大
        else:
            sort_key = ts
        indexed.append((sort_key, i, r))
    indexed.sort(key=lambda x: (x[0], x[1]))
    return indexed[-1][2]


# =========================== 主函数 ===========================
def shouldFollowUp(records: List[Dict[str, Any]]) -> bool:
    """判断给定用户的电池操作历史是否需要回访。

    Args:
        records: 该用户的操作记录列表（与看板/数据库中"换电操作日志"的字段对应），
                 每条记录至少需要包含 操作类型、操作时间、电池SN 三个字段
                 （中英文键名均可）。

    Returns:
        True  - 需要回访
        False - 无需回访（最后一条操作是 "柜内归还电池" 且当时 SN="暂无电池"，
                 说明用户已主动结束换电生命周期）

    Examples:
        >>> shouldFollowUp([])
        True
        >>> shouldFollowUp([{"操作时间":"2025-09-15 21:57:51",
        ...                  "操作类型":"柜内归还电池","电池SN":"暂无电池"}])
        False
    """
    # 1) 边界：列表为空 -> 视为需要回访
    if not records:
        return True

    # 2) 取最后一次操作（按"操作时间"排序，含降级/兜底）
    last = _last_record(records)

    # 3) 取关键字段
    op_type = _get_field(last, TYPE_KEYS)
    sn      = _get_field(last, SN_KEYS)

    op_str = str(op_type).strip() if op_type is not None else ""
    sn_str = str(sn).strip()       if sn      is not None else ""

    # 4) SN 缺失或空 -> 不视为"暂无电池"，按常规处理（命中 True）
    if sn_str == "":
        return True

    # 5) 命中"无需回访"双条件才返回 False
    if op_str == RETURN_OP_TYPE and sn_str == NO_BATTERY_SN:
        return False
    return True


# =========================== 测试用例 ===========================
def _run_tests() -> None:
    """12 个用例，覆盖所有用户要求的边界 + 几个常见变种。"""
    cases: List[Dict[str, Any]] = [
        # ---- 用户明确列出的边界 ----
        # 1) 列表为空 -> True
        {"name": "空列表",
         "records": [],
         "expected": True},

        # 2) 最后一条是「柜内归还电池 + SN=暂无电池」 -> False
        #    时间更晚的「柜内借出电池」必须放在更早的时间，归还放在更晚的时间
        {"name": "最后一条是归还+暂无电池",
         "records": [
             {"操作时间": "2025-09-15 20:30:00",
              "操作类型": "柜内借出电池",
              "电池SN":   "DU01872508160167"},
             {"操作时间": "2025-09-15 21:57:51",
              "操作类型": "柜内归还电池",
              "电池SN":   "暂无电池"},
         ],
         "expected": False},

        # 3) 同样两条数据但时间顺序颠倒：
        #    此时"借出"时间更晚 -> 胜出 -> True
        {"name": "乱序输入（结尾是借出）",
         "records": [
             {"操作时间": "2025-09-15 21:57:51",
              "操作类型": "柜内归还电池",
              "电池SN":   "暂无电池"},
             {"操作时间": "2025-09-15 22:56:45",
              "操作类型": "柜内借出电池",
              "电池SN":   "DU01872508160167"},
         ],
         "expected": True},  # 此时"借出"时间更晚，胜出 -> True

        # 4) 最后一条 SN 不是 "暂无电池" -> True
        {"name": "最后一条是归还，SN 不是暂无电池",
         "records": [
             {"操作时间": "2025-09-15 22:56:45",
              "操作类型": "柜内借出电池",
              "电池SN":   "DU01872508160167"},
             {"操作时间": "2025-09-15 21:57:51",
              "操作类型": "柜内归还电池",
              "电池SN":   "DU011B2503260065"},
         ],
         "expected": True},

        # 5) 最后一条是借出（非归还） -> True
        {"name": "最后一条是柜内借出电池",
         "records": [
             {"操作时间": "2025-09-15 21:57:51",
              "操作类型": "柜内归还电池",
              "电池SN":   "暂无电池"},
             {"操作时间": "2025-09-15 22:56:45",
              "操作类型": "柜内借出电池",
              "电池SN":   "DU01872508160167"},
         ],
         "expected": True},

        # 6) 最后一条 SN 字段缺失 -> 视为非"暂无电池" -> True
        {"name": "最后一条 SN 字段缺失",
         "records": [
             {"操作时间": "2025-09-15 21:57:51",
              "操作类型": "柜内归还电池"},
         ],
         "expected": True},

        # 7) 最后一条 SN 为空字符串 -> True
        {"name": "最后一条 SN 为空字符串",
         "records": [
             {"操作时间": "2025-09-15 21:57:51",
              "操作类型": "柜内归还电池",
              "电池SN":   ""},
         ],
         "expected": True},

        # 8) 操作时间全部缺失 -> 按 i 兜底，最后一条为索引最大者
        {"name": "操作时间全部缺失，按输入顺序末尾兜底",
         "records": [
             {"操作类型": "柜内归还电池", "电池SN": "暂无电池"},   # idx 0
             {"操作类型": "柜内归还电池", "电池SN": "暂无电池"},   # idx 1 -> 视为最后
         ],
         "expected": False},

        # 9) 操作时间部分缺失：有效时间最新者胜出（不易被缺失时间污染）
        {"name": "部分时间缺失，取有效时间最晚者",
         "records": [
             {"操作时间": "这不是时间格式",
              "操作类型": "柜内归还电池",
              "电池SN":   "暂无电池"},
             {"操作时间": "2025-09-15 22:56:45",
              "操作类型": "柜内借出电池",
              "电池SN":   "DU01872508160167"},
         ],
         "expected": True},

        # 10) 相同时间多条：按"输入顺序在后"为"更新" -> False
        {"name": "同时间多条，最后输入者胜出（稳定排序）",
         "records": [
             {"操作时间": "2025-09-15 22:56:45",
              "操作类型": "柜内借出电池",
              "电池SN":   "DU01872508160167"},
             {"操作时间": "2025-09-15 22:56:45",
              "操作类型": "柜内归还电池",
              "电池SN":   "暂无电池"},
         ],
         "expected": False},

        # ---- 字段兼容性变种 ----
        # 11) 英文字段名也能识别
        {"name": "英文键名兼容",
         "records": [
             {"op_time": "2025-09-15 21:57:51",
              "op_type": "Cabinet Return",
              "sn":      "暂无电池"},   # 类型不命中，仅 SN 命中，仍 True
             {"op_time": "2025-09-15 22:56:45",
              "op_type": "Cabinet Lend",
              "sn":      "X"},
         ],
         "expected": True},

        # 12) datetime 对象也能识别
        {"name": "datetime 对象",
         "records": [
             {"操作时间": datetime(2025, 9, 15, 22, 56, 45),
              "操作类型": "柜内借出电池",
              "电池SN":   "DU01872508160167"},
         ],
         "expected": True},
    ]

    passed = 0
    failed: List[str] = []
    for c in cases:
        got = shouldFollowUp(c["records"])
        status = "PASS" if got == c["expected"] else "FAIL"
        if status == "PASS":
            passed += 1
            print(f"  PASS  {c['name']:<48s} -> {got}")
        else:
            failed.append(c["name"])
            print(f"  FAIL  {c['name']:<48s} expected={c['expected']} got={got}")

    total = len(cases)
    print(f"\n共 {passed}/{total} 通过")
    if failed:
        raise SystemExit("\n失败用例:\n  - " + "\n  - ".join(failed))


if __name__ == "__main__":
    _run_tests()
