"""flow_engine 单元测试 —— 节点激活、传播、汇合逻辑

覆盖：开始节点激活、正常传播、汇合等待、结束节点创建审批
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from app.engine.flow_engine import activate_start_node, propagate_from_node
from app.models.enums import InstanceNodeStatus

from tests.factories import make_node, make_start_node, make_end_node
from tests.conftest import MockResult


# ============================================================
# activate_start_node —— 开始节点激活
# ============================================================

class TestActivateStartNode:
    """开始节点激活测试"""

    @pytest.mark.asyncio
    async def test_activate_success(self, mock_db, mocker):
        """开始节点存在且状态为 waiting → 标记 finished"""
        mocker.patch("app.engine.flow_engine.create_notification", new=AsyncMock())
        start_node = make_start_node(status=InstanceNodeStatus.WAITING)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=start_node),  # 0: SELECT start node
            MagicMock(),                         # 1: UPDATE start node
            MagicMock(),                         # 2: UPDATE instance
            MockResult(scalars_all=[]),          # 3: SELECT downstream edges
        ]

        await activate_start_node(mock_db, instance_id=1)

        assert start_node.status == InstanceNodeStatus.FINISHED

    @pytest.mark.asyncio
    async def test_activate_already_finished(self, mock_db, mocker):
        """开始节点已是 finished → 不重复处理"""
        mocker.patch("app.engine.flow_engine.create_notification", new=AsyncMock())
        start_node = make_start_node(status=InstanceNodeStatus.FINISHED)

        mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=start_node))

        await activate_start_node(mock_db, instance_id=1)

        # 应直接返回，不调用后续查询
        assert mock_db.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_activate_no_start_node(self, mock_db):
        """实例无开始节点 → 安静返回，不抛异常"""
        mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=None))

        await activate_start_node(mock_db, instance_id=1)


# ============================================================
# propagate_from_node —— 节点传播
# ============================================================

class TestPropagateFromNode:
    """节点传播测试"""

    @pytest.mark.asyncio
    async def test_no_downstream_edges(self, mock_db):
        """无下游边 → 返回空列表"""
        mock_db.execute = AsyncMock(return_value=MockResult(scalars_all=[]))

        result = await propagate_from_node(mock_db, instance_id=1, finished_node_id=5)

        assert result == []

    @pytest.mark.asyncio
    async def test_work_node_activated(self, mock_db, mocker):
        """下游普通节点 arriving_count 满足 → 激活为 running + 创建 Task"""
        mocker.patch("app.engine.flow_engine.create_notification", new=AsyncMock())
        from app.models import InstanceEdge
        edge = InstanceEdge(id=1, instance_id=1, source_node_id=5, target_node_id=6)
        target = make_node(id=6, is_end=False, incoming_count=1, arrived_count=0,
                          status=InstanceNodeStatus.WAITING)

        # 模拟原子 UPDATE SET arrived_count=arrived_count+1 后的重取结果
        target.arrived_count = 1

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalars_all=[edge]),     # 0: SELECT downstream edges
            MagicMock(),                         # 1: SELECT ... FOR UPDATE（行锁）
            MagicMock(),                         # 2: UPDATE arrived_count（原子递增）
            MockResult(scalar_one=target),      # 3: SELECT target（重取）
            MagicMock(),                         # 4: UPDATE node → running
            MagicMock(),                         # 5: add Task
            MagicMock(),                         # 6: flush
        ]

        result = await propagate_from_node(mock_db, instance_id=1, finished_node_id=5)

        assert target.id in result
        assert target.status == InstanceNodeStatus.RUNNING

    @pytest.mark.asyncio
    async def test_fork_join_waiting(self, mock_db):
        """fork-join 汇合：arrived < incoming → 等待不激活"""
        from app.models import InstanceEdge
        edge = InstanceEdge(id=1, instance_id=1, source_node_id=5, target_node_id=7)
        target = make_node(id=7, is_end=False, incoming_count=2, arrived_count=0,
                          status=InstanceNodeStatus.WAITING)

        # 模拟 UPDATE 后 arrived_count=1，但 incoming_count=2，仍需等待
        target.arrived_count = 1

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalars_all=[edge]),     # 0: SELECT downstream edges
            MagicMock(),                         # 1: SELECT ... FOR UPDATE（行锁）
            MagicMock(),                         # 2: UPDATE arrived_count（原子递增）
            MockResult(scalar_one=target),      # 3: SELECT target（重取）
        ]

        result = await propagate_from_node(mock_db, instance_id=1, finished_node_id=5)

        assert target.arrived_count == 1
        assert target.id not in result

    @pytest.mark.asyncio
    async def test_end_node_activated(self, mock_db, mocker):
        """下游是结束节点 → waiting_approval + 创建审批"""
        mocker.patch("app.engine.flow_engine.create_notification", new=AsyncMock())
        from app.models import InstanceEdge
        edge = InstanceEdge(id=1, instance_id=1, source_node_id=5, target_node_id=20)
        end_node = make_end_node(incoming_count=1, arrived_count=0,
                                status=InstanceNodeStatus.WAITING)

        # 模拟 UPDATE 后 arrived_count=1，满足 incoming_count
        end_node.arrived_count = 1

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalars_all=[edge]),     # 0: SELECT downstream edges
            MagicMock(),                         # 1: SELECT ... FOR UPDATE（行锁）
            MagicMock(),                         # 2: UPDATE arrived_count（原子递增）
            MockResult(scalar_one=end_node),    # 3: SELECT target（重取）
            MagicMock(),                         # 4: add Approval
            MagicMock(),                         # 5: flush
        ]

        result = await propagate_from_node(mock_db, instance_id=1, finished_node_id=5)

        assert end_node.id in result
        assert end_node.status == InstanceNodeStatus.WAITING_APPROVAL
