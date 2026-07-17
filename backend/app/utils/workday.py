"""工作日计算工具 —— 基于 chinesecalendar 库，跳过中国法定节假日和周末

核心函数：
- add_workdays(start, n) —— 从起始日期加 N 个工作日，返回截止日期
- ensure_workday(date) —— 非工作日自动推到最近的下一个工作日

超出 chinesecalendar 支持年份（2004-2026）时，
退化为"仅跳过周末"并用 logging.warning 记录。
"""

import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

# chinesecalendar 内置国务院调休数据
try:
    from chinese_calendar import is_workday as _cn_is_workday
    _HAS_CN_CALENDAR = True
except ImportError:
    _HAS_CN_CALENDAR = False


def is_workday(d: date) -> bool:
    """判断是否为工作日（含调休上班的周末）

    优先用 chinesecalendar（含法定节假日+调休），
    超出年份范围时退化为"周一至周五为工作日"。
    """
    if _HAS_CN_CALENDAR:
        try:
            return _cn_is_workday(d)
        except NotImplementedError:
            logger.warning(
                "chinesecalendar 不支持 %d 年，退化为仅跳过周末", d.year
            )
    # 退化：周一到周五为工作日
    return d.weekday() < 5


def add_workdays(start: date, n: int) -> date:
    """从起始日期开始，跳过非工作日，加 N 个工作日，返回截止日期

    Args:
        start: 起始日期（发起日期）
        n: 工作日数量

    Returns:
        截止日期（第 N 个工作日当天）

    Examples:
        >>> add_workdays(date(2026, 7, 17), 1)  # 周五 +1 → 下周一(7/20)
        datetime.date(2026, 7, 20)
        >>> add_workdays(date(2026, 7, 17), 0)  # 0 个工作日 → 当天
        datetime.date(2026, 7, 17)
    """
    if n <= 0:
        return start

    current = start
    remaining = n

    # 起始日如果是非工作日，不计入（从最近的工作日开始累计）
    # 但按需求，发起日期始终是当天，所以从当天起算
    while remaining > 0:
        current += timedelta(days=1)
        if is_workday(current):
            remaining -= 1

    return current


def ensure_workday(d: date) -> date:
    """确保给定日期是工作日，否则自动推到最近的下一个工作日

    用于校验用户手动选择的截止日期。

    Args:
        d: 待校验的日期

    Returns:
        工作日日期（如果 d 已是工作日则原样返回，否则往后推）
    """
    while not is_workday(d):
        d += timedelta(days=1)
    return d


def next_workday(d: date) -> date:
    """返回给定日期之后的下一个工作日（不含当天）

    用于节点间的开始日期衔接：前节点截止日的下一个工作日 = 后节点开始日。

    Args:
        d: 参考日期（通常是上一节点的截止日）

    Returns:
        下一个工作日

    Examples:
        >>> next_workday(date(2026, 7, 17))  # 周五 → 下周一
        datetime.date(2026, 7, 20)
    """
    d += timedelta(days=1)
    return ensure_workday(d)
