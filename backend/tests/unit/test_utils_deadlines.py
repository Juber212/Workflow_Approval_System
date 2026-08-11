"""/utils/calculate-deadlines 接口单元测试 —— P1-39 锚点 + 链式口径

背景：前端发起模式级联截止日统一走后端该接口（此前 PropertyPanel 本地
countBusinessDays 含首尾导致 off-by-one、且不跳法定节假日）。本测试锁定：
- 链式：节点N 开始 = 上一节点截止日的下一工作日（与 create.py 6.5 兜底一致）
- 锚点：传入 deadline 的节点跳过计算直接采用，下游从该日期顺延
"""

import pytest

from app.api.utils import (
    calculate_deadlines,
    CalculateDeadlinesRequest,
    DeadlineCalcItem,
)
from app.core.exceptions import AppException


class FakeUser:
    """占位当前用户（接口仅做鉴权，不参与计算）"""
    id = 1
    role = "manager"
    real_name = "测试"


class TestCalculateDeadlines:
    """calculate-deadlines —— 链式 + 锚点"""

    @pytest.mark.asyncio
    async def test_chain_basic(self):
        """链式：节点2 从节点1 截止日的下一工作日起算（2026-07 无节假日）"""
        body = CalculateDeadlinesRequest(
            start_date="2026-07-06",  # 周一
            nodes=[
                DeadlineCalcItem(node_id=1, time_limit_days=2),
                DeadlineCalcItem(node_id=2, time_limit_days=2),
            ],
        )
        res = await calculate_deadlines(body, FakeUser())
        deadlines = {d["node_id"]: d for d in res.data["deadlines"]}
        # 自然日：节点1 7/6 起覆盖 2 天 → 7/7；节点2 衔接 7/8 起覆盖 2 天 → 7/9
        assert deadlines[1]["begin"] == "2026-07-06"
        assert deadlines[1]["deadline"] == "2026-07-07"
        assert deadlines[2]["begin"] == "2026-07-08"
        assert deadlines[2]["deadline"] == "2026-07-09"

    @pytest.mark.asyncio
    async def test_anchor_locks_deadline(self):
        """锚点：某节点已锁定 deadline，跳过计算且下游从该日期顺延"""
        body = CalculateDeadlinesRequest(
            start_date="2026-07-06",
            nodes=[
                DeadlineCalcItem(node_id=1, deadline="2026-07-10"),  # 周五，锚点
                DeadlineCalcItem(node_id=2, time_limit_days=2),
            ],
        )
        res = await calculate_deadlines(body, FakeUser())
        deadlines = {d["node_id"]: d for d in res.data["deadlines"]}
        # 锚点节点：直接采用给定截止日，begin 不返回
        assert deadlines[1]["begin"] is None
        assert deadlines[1]["deadline"] == "2026-07-10"
        # 下游：自然日从锚点截止次日 7/11 起覆盖 2 天 → 7/12
        assert deadlines[2]["begin"] == "2026-07-11"
        assert deadlines[2]["deadline"] == "2026-07-12"

    @pytest.mark.asyncio
    async def test_anchor_mid_chain(self):
        """锚点在中间：锚点前按链式，锚点后从锚点顺延"""
        body = CalculateDeadlinesRequest(
            start_date="2026-07-06",
            nodes=[
                DeadlineCalcItem(node_id=1, time_limit_days=1),      # → 7/7(周二)
                DeadlineCalcItem(node_id=2, deadline="2026-07-08"),  # 锚点：周三
                DeadlineCalcItem(node_id=3, time_limit_days=2),      # 从 7/9(周四) +2 → 7/13(周一)
            ],
        )
        res = await calculate_deadlines(body, FakeUser())
        deadlines = {d["node_id"]: d for d in res.data["deadlines"]}
        # 自然日：节点1 7/6 覆盖1天 → 7/6；节点3 从锚点次日 7/9 起覆盖 2 天 → 7/10
        assert deadlines[1]["deadline"] == "2026-07-06"
        assert deadlines[2]["deadline"] == "2026-07-08"
        assert deadlines[3]["begin"] == "2026-07-09"
        assert deadlines[3]["deadline"] == "2026-07-10"

    @pytest.mark.asyncio
    async def test_anchor_bad_format(self):
        """锚点格式错误 → 校验异常"""
        body = CalculateDeadlinesRequest(
            start_date="2026-07-06",
            nodes=[DeadlineCalcItem(node_id=1, deadline="not-a-date")],
        )
        with pytest.raises(AppException):
            await calculate_deadlines(body, FakeUser())

    @pytest.mark.asyncio
    async def test_zero_limit_skipped(self):
        """time_limit_days 为 0/None 的节点不计算，后续节点衔接前一个有效节点"""
        body = CalculateDeadlinesRequest(
            start_date="2026-07-06",
            nodes=[
                DeadlineCalcItem(node_id=1, time_limit_days=2),  # → 7/8(周三)
                DeadlineCalcItem(node_id=2, time_limit_days=0),  # 跳过
                DeadlineCalcItem(node_id=3, time_limit_days=1),  # 从 7/9(周四) +1 → 7/10(周五)
            ],
        )
        res = await calculate_deadlines(body, FakeUser())
        deadlines = {d["node_id"]: d for d in res.data["deadlines"]}
        # 自然日：节点1 7/6 覆盖2天 → 7/7；节点3 从节点1 截止次日 7/8 起覆盖 1 天 → 7/8
        assert deadlines[1]["deadline"] == "2026-07-07"
        assert deadlines[2]["begin"] is None and deadlines[2]["deadline"] is None
        assert deadlines[3]["begin"] == "2026-07-08"
        assert deadlines[3]["deadline"] == "2026-07-08"
