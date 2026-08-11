"""排产服务单元测试 —— 自然日顺排 + 资源冲突避免"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, date

from app.models import InstanceNode, ScheduleItem
from app.services.schedule_service import schedule_instance
from tests.conftest import MockResult


def _make_node(id, sort_order, time_limit_days, assignee_id=1, checkers=None, approvers=None, endorser_id=None):
    """构造工作节点（is_start/is_end=False）"""
    return InstanceNode(
        id=id, instance_id=1, name=f"节点{id}", sort_order=sort_order,
        is_start=False, is_end=False, assignee_id=assignee_id,
        time_limit_days=time_limit_days,
        checkers=checkers, approvers=approvers, endorser_id=endorser_id,
    )


def _busy_item(assignee_id: int, plan_end: date) -> ScheduleItem:
    """构造一个已占用窗口的排产项（资源冲突模拟）"""
    return ScheduleItem(assignee_id=assignee_id, plan_end_date=plan_end)


@pytest.mark.asyncio
async def test_schedule_natural_days():
    """3 节点按 time_limit_days 自然日顺排，负责人取各自 assignee"""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    inst = MagicMock()
    inst.created_at = datetime(2026, 8, 11, 10, 0, 0)
    nodes = [
        _make_node(1, 1, 2, assignee_id=10),
        _make_node(2, 2, 3, assignee_id=20),
        _make_node(3, 3, 1, assignee_id=30),
    ]
    mock_db.execute.side_effect = [
        MockResult(scalars_all=nodes),   # 0: 工作节点
        MockResult(scalar_one=inst),     # 1: 实例（取发起日）
        MagicMock(),                     # 2: delete 旧排产
        MockResult(scalars_all=[]),      # 3: pick_available node1（无冲突）
        MockResult(scalars_all=[]),      # 4: pick_available node2
        MockResult(scalars_all=[]),      # 5: pick_available node3
    ]
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()

    await schedule_instance(mock_db, 1)

    adds = [c.args[0] for c in mock_db.add.call_args_list]
    assert len(adds) == 3
    # node1：8/11 开始，2 天 → 8/12 结束
    assert adds[0].assignee_id == 10
    assert adds[0].plan_start_date == date(2026, 8, 11)
    assert adds[0].plan_end_date == date(2026, 8, 12)
    assert adds[0].duration_days == 2
    # node2：8/13 开始，3 天 → 8/15
    assert adds[1].assignee_id == 20
    assert adds[1].plan_start_date == date(2026, 8, 13)
    assert adds[1].plan_end_date == date(2026, 8, 15)
    # node3：8/16 开始，1 天
    assert adds[2].assignee_id == 30
    assert adds[2].plan_start_date == date(2026, 8, 16)
    assert adds[2].plan_end_date == date(2026, 8, 16)


@pytest.mark.asyncio
async def test_schedule_resource_conflict_shift():
    """两节点同负责人 → 第二节点顺延到该负责人空闲窗口"""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    inst = MagicMock()
    inst.created_at = datetime(2026, 8, 11, 10, 0, 0)
    nodes = [
        _make_node(1, 1, 2, assignee_id=10),
        _make_node(2, 2, 1, assignee_id=10),  # 与 node1 同一负责人
    ]
    mock_db.execute.side_effect = [
        MockResult(scalars_all=nodes),       # 0: 工作节点
        MockResult(scalar_one=inst),         # 1: 实例
        MagicMock(),                         # 2: delete 旧排产
        MockResult(scalars_all=[]),          # 3: pick_available node1（空闲）
        # 4: pick_available node2 → 负责人 10 已占用（node1 到 8/12）
        MockResult(scalars_all=[_busy_item(10, date(2026, 8, 12))]),
        # 5: _pick_earliest_free node2 → 负责人 10 已有排产（8/12 结束）→ 最早空闲 8/13
        MockResult(scalars_all=[_busy_item(10, date(2026, 8, 12))]),
    ]
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()

    await schedule_instance(mock_db, 1)

    adds = [c.args[0] for c in mock_db.add.call_args_list]
    assert len(adds) == 2
    # node1：8/11~8/12
    assert adds[0].plan_start_date == date(2026, 8, 11)
    assert adds[0].plan_end_date == date(2026, 8, 12)
    # node2：负责人冲突 → 顺延到 8/13 开始
    assert adds[1].assignee_id == 10
    assert adds[1].plan_start_date == date(2026, 8, 13)
    assert adds[1].plan_end_date == date(2026, 8, 13)


@pytest.mark.asyncio
async def test_schedule_no_work_nodes():
    """无工作节点（只有开始/结束）→ 不生成排产"""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.execute.side_effect = [MockResult(scalars_all=[])]  # 无工作节点
    mock_db.add = MagicMock()

    await schedule_instance(mock_db, 1)

    assert mock_db.add.call_count == 0
