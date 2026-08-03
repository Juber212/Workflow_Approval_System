"""deadline 逾期语义单元测试 —— P1-17 自然日口径

背景：实例节点 deadline 存的是当日 00:00:00，旧口径用 `deadline - now` 算天数，
导致截止日当天 00:01 起 delta.days 即变 -1，误报「已逾期 1 天」。
修复后统一按自然日判断：截止日当天（00:00~23:59）不逾期，次日 00:00 起才算。
"""

from datetime import datetime, timedelta

from app.services.instance._helpers import compute_deadline_info, is_deadline_overdue


def _today_midnight() -> datetime:
    """今天 00:00:00（deadline 的实际存储形态）"""
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)


class TestComputeDeadlineInfo:
    """compute_deadline_info —— 自然日口径"""

    def test_none(self):
        """无截止时间 → 不逾期、剩余 None"""
        assert compute_deadline_info(None) == (False, None)

    def test_deadline_is_today_midnight(self):
        """P1-17 关键回归：截止日当天 00:00:00（存储形态）不算逾期，剩余 0 天"""
        # 旧口径：now(当天任意时刻) - 当天00:00 → days=-1，误报 (True, -1)
        assert compute_deadline_info(_today_midnight()) == (False, 0)

    def test_deadline_is_today_late(self):
        """截止日当天 23:59:59 仍不算逾期，剩余 0 天"""
        assert compute_deadline_info(_today_midnight() + timedelta(hours=23, minutes=59, seconds=59)) == (False, 0)

    def test_deadline_is_yesterday(self):
        """昨天截止 → 已逾期 1 天"""
        assert compute_deadline_info(_today_midnight() - timedelta(days=1)) == (True, -1)

    def test_deadline_is_tomorrow(self):
        """明天截止 → 未逾期，剩余 1 天"""
        assert compute_deadline_info(_today_midnight() + timedelta(days=1)) == (False, 1)

    def test_deadline_is_tomorrow_late(self):
        """明天 23:59 截止仍算剩余 1 天（忽略时分，语义为天粒度）"""
        assert compute_deadline_info(_today_midnight() + timedelta(days=1, hours=23)) == (False, 1)


class TestIsDeadlineOverdue:
    """is_deadline_overdue —— 供待办/通知/仪表盘直比复用，口径与 compute_deadline_info 一致"""

    def test_none(self):
        assert is_deadline_overdue(None) is False

    def test_today_not_overdue(self):
        """截止日当天（存储 00:00:00）不算逾期"""
        assert is_deadline_overdue(_today_midnight()) is False

    def test_yesterday_overdue(self):
        """昨天截止 → 已逾期"""
        assert is_deadline_overdue(_today_midnight() - timedelta(days=1)) is True

    def test_tomorrow_not_overdue(self):
        """明天截止 → 未逾期"""
        assert is_deadline_overdue(_today_midnight() + timedelta(days=1)) is False
