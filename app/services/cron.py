from __future__ import annotations
"""轻量 cron 解析与匹配（5 段：分 时 日 月 周）。

支持语法：
- *         任意值
- */n       步长
- a-b       区间
- a,b,c     列表
- 周字段使用 isoweekday：1=周一 ... 7=周日

不支持：? L W # @（简化设计，够用且可控）。
"""
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

RANGES = {"minute": (0, 59), "hour": (0, 23), "dom": (1, 31), "month": (1, 12), "dow": (1, 7)}


def parse_field(field: str, lo: int, hi: int):  # -> Optional[set]
    """解析单个字段；返回允许值集合，'*' 返回 None 表示任意。"""
    field = field.strip()
    if not field or field == "*":
        return None
    values = set()
    for part in field.split(","):
        part = part.strip()
        if not part:
            continue
        step = 1
        base = part
        if "/" in part:
            base, _, step_s = part.partition("/")
            try:
                step = int(step_s)
            except ValueError:
                raise ValueError(f"Invalid cron step in '{part}'")
        if base == "*":
            values.update(range(lo, hi + 1, step))
        elif "-" in base:
            a, _, b = base.partition("-")
            try:
                a, b = int(a), int(b)
            except ValueError:
                raise ValueError(f"Invalid cron range in '{part}'")
            values.update(range(a, b + 1, step))
        else:
            try:
                values.add(int(base))
            except ValueError:
                raise ValueError(f"Invalid cron value '{part}'")
    return values or None


def parse_cron(cron: str) -> tuple:
    """解析 5 段 cron，返回 (minute, hour, dom, month, dow) 各字段集合。"""
    parts = cron.split()
    if len(parts) != 5:
        raise ValueError(f"Cron must have 5 fields (minute hour dom month dow), got {len(parts)}")
    fields = []
    for key, part in zip(("minute", "hour", "dom", "month", "dow"), parts):
        lo, hi = RANGES[key]
        fields.append(parse_field(part, lo, hi))
    return tuple(fields)


def matches(cron: str, dt: datetime) -> bool:
    """判断给定时间是否匹配 cron 表达式。"""
    minute, hour, dom, month, dow = parse_cron(cron)
    if minute is not None and dt.minute not in minute:
        return False
    if hour is not None and dt.hour not in hour:
        return False
    if dom is not None and dt.day not in dom:
        return False
    if month is not None and dt.month not in month:
        return False
    if dow is not None and dt.isoweekday() not in dow:
        return False
    return True


def next_run(cron: str, after: datetime) -> datetime | None:
    """计算 after 之后下一个匹配 cron 的时间；366 天内找不到返回 None。"""
    fields = parse_cron(cron)
    minute, hour, dom, month, dow = fields
    dt = (after + timedelta(minutes=1)).replace(second=0, microsecond=0)
    limit = dt + timedelta(days=366)
    while dt <= limit:
        if matches(cron, dt):
            return dt
        dt = _step(dt, minute)
    return None


def _step(dt: datetime, minute_set: set | None) -> datetime:
    """快速推进：优先跳到下一个允许分钟；否则进位到下一小时/天。"""
    if minute_set is not None:
        for m in range(dt.minute + 1, 60):
            if m in minute_set:
                return dt.replace(minute=m)
        m0 = min(minute_set)
        if dt.hour < 23:
            return dt.replace(hour=dt.hour + 1, minute=m0)
        return dt.replace(day=dt.day + 1, hour=0, minute=m0)
    return dt + timedelta(minutes=1)
