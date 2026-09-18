# Python 3.8 compatible
"""基础数据与单据的自动编号。

编号规则在本文件固定（如需调整前缀/位数，改这里的 RULES 常量）：
    物料    WL + 4位流水                     例：WL0001
    设备    SB + 4位流水                     例：SB0001
    人员    GH + 4位流水                     例：GH0001
    采购单  CG + YYYYMMDD + - + 3位流水      例：CG20240917-001
    领料单  LL + YYYYMMDD + - + 3位流水      例：LL20240917-001

流水号取自"同前缀已有编号的最大流水 + 1"，不额外维护计数器，
避免计数器与实际数据脱节（原采购单/领料单的取号方式保持不变）。
"""
from datetime import datetime

RULES = {
    "material":    {"prefix": "WL", "width": 4, "date_fmt": "",         "separator": ""},
    "equipment":   {"prefix": "SB", "width": 4, "date_fmt": "",         "separator": ""},
    "personnel":   {"prefix": "GH", "width": 4, "date_fmt": "",         "separator": ""},
    "purchase":    {"prefix": "CG", "width": 3, "date_fmt": "%Y%m%d",   "separator": "-"},
    "requisition": {"prefix": "LL", "width": 3, "date_fmt": "%Y%m%d",   "separator": "-"},
}


def build_prefix(module, now=None):
    """返回不含流水的编号前缀，例如 WL / CG20240917-。"""
    rule = RULES[module]
    prefix = rule["prefix"]
    if rule["date_fmt"]:
        prefix += (now or datetime.now()).strftime(rule["date_fmt"])
    return prefix + rule["separator"]


def _max_sequence(db, column, prefix):
    """扫描同前缀的已有编号，取最大流水值（兼容历史上未补零的编号）。"""
    max_seq = 0
    for row in db.query(column).filter(column.like(prefix + "%")).all():
        value = row[0]
        if not value:
            continue
        tail = value[len(prefix):]
        if tail.isdigit():
            seq = int(tail)
            if seq > max_seq:
                max_seq = seq
    return max_seq


def next_code(db, module, column, now=None):
    """生成下一个可用编号（不写入数据库，仅计算）。

    module: RULES 中的模块名；column: 模型上的编号字段，如 Material.code。
    """
    prefix = build_prefix(module, now)
    seq = _max_sequence(db, column, prefix) + 1
    return "{}{:0{width}d}".format(prefix, seq, width=RULES[module]["width"])


def rule_hint(module):
    """给页面显示编号规则提示，例如：WL0001（前缀 WL + 4位流水）。"""
    rule = RULES[module]
    sample = rule["prefix"]
    if rule["date_fmt"]:
        sample += datetime.now().strftime(rule["date_fmt"])
    sample += rule["separator"] + "1".zfill(rule["width"])
    return sample
