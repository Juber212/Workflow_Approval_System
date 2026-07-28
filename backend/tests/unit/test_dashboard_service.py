"""dashboard_service 单元测试 —— 各所概览 + 卡点追踪过滤"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from app.models import Organization, FlowInstance, InstanceNode, User
from app.models.enums import InstanceStatus, InstanceNodeStatus
from app.services.dashboard_service import _get_org_overview, _get_bottleneck_tracking
from tests.conftest import MockResult


# ============================================================
# 各所流程概览 —— 项目/方案分离
# ============================================================

class TestOrgOverview:
    """_get_org_overview 过滤测试"""

    @pytest.mark.asyncio
    async def test_exclude_proposals(self, mock_db):
        """排除方案模板 → 只统计项目"""
        org = Organization(id=1, name="测试所", is_active=True)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            # 0: SELECT orgs
            MockResult(scalars_all=[org]),
            # 1: 实例状态分组统计（使用 .all()）
            MockResult(rows_all=[
                (1, InstanceStatus.RUNNING, 5),
                (1, InstanceStatus.COMPLETED, 3),
                (1, InstanceStatus.TERMINATED, 1),
            ]),
        ]

        result = await _get_org_overview(mock_db, exclude_proposal_tpl_ids={10, 20})

        assert len(result) == 1
        assert result[0].org_id == 1
        assert result[0].running_count == 5
        assert result[0].completed_count == 3
        assert result[0].total_count == 9  # 5+3+1

    @pytest.mark.asyncio
    async def test_proposal_only(self, mock_db):
        """仅方案模板 → 只统计方案"""
        org = Organization(id=1, name="测试所", is_active=True)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalars_all=[org]),
            MockResult(rows_all=[
                (1, InstanceStatus.RUNNING, 2),
                (1, InstanceStatus.COMPLETED, 4),
            ]),
        ]

        result = await _get_org_overview(mock_db, proposal_only_tpl_ids={30})

        assert len(result) == 1
        assert result[0].running_count == 2
        assert result[0].completed_count == 4
        assert result[0].total_count == 6

    @pytest.mark.asyncio
    async def test_no_active_orgs(self, mock_db):
        """无活跃组织 → 空列表"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalars_all=[]),
        ]

        result = await _get_org_overview(mock_db)
        assert result == []


# ============================================================
# 流程卡点追踪 —— 项目/方案分离
# ============================================================

class TestBottleneckTracking:
    """_get_bottleneck_tracking 过滤测试"""

    @pytest.mark.asyncio
    async def test_no_running_instances(self, mock_db):
        """无运行中实例 → 空列表"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalars_all=[]),  # SELECT running instances
        ]

        now = datetime.now()
        result = await _get_bottleneck_tracking(mock_db, now)
        assert result == []

    @pytest.mark.asyncio
    async def test_running_instance_with_nodes(self, mock_db):
        """运行中实例有节点 → 返回卡点追踪数据"""
        inst = FlowInstance(
            id=1, name="测试项目", organization_id=1,
            status=InstanceStatus.RUNNING, priority="normal",
            difficulty="1", initiator_id=1, template_id=1,
            template_type="project", template_name="测试模板",
            initiated_at=datetime.now(),
        )
        node = InstanceNode(
            id=10, instance_id=1, name="设计阶段",
            is_start=False, is_end=False,
            assignee_id=2, status=InstanceNodeStatus.RUNNING,
            sort_order=2, checkers=[], approvers=[], incoming_count=1,
            arrived_count=1, round=1,
        )

        mock_db.execute = AsyncMock()
        # 需要按顺序提供返回值
        mock_db.execute.side_effect = [
            # 0: SELECT running instances
            MockResult(scalars_all=[inst]),
            # 1: SELECT nodes
            MockResult(scalars_all=[node]),
            # 2: SELECT org names
            MockResult(scalars_all=[Organization(id=1, name="测试所")]),
            # 3: SELECT all personnel names（使用 .all()）
            MockResult(rows_all=[(2, "张三")]),
        ]

        now = datetime.now()
        result = await _get_bottleneck_tracking(mock_db, now)

        assert len(result) == 1
        assert result[0].instance_id == 1
        assert result[0].instance_name == "测试项目"
        assert result[0].organization_name == "测试所"
        assert result[0].current_handlers == "张三"
        assert result[0].difficulty == "1"

    @pytest.mark.asyncio
    async def test_filters_proposals(self, mock_db):
        """排除方案模板 → 不返回方案实例"""
        inst = FlowInstance(
            id=1, name="测试项目", organization_id=1,
            status=InstanceStatus.RUNNING, priority="normal",
            difficulty="1", initiator_id=1, template_id=5,
            template_type="project", template_name="测试模板",
            initiated_at=datetime.now(),
        )
        node = InstanceNode(
            id=10, instance_id=1, name="设计阶段",
            is_start=False, is_end=False,
            assignee_id=2, status=InstanceNodeStatus.RUNNING,
            sort_order=2, checkers=[], approvers=[], incoming_count=1,
            arrived_count=1, round=1,
        )

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalars_all=[inst]),
            MockResult(scalars_all=[node]),
            MockResult(scalars_all=[Organization(id=1, name="测试所")]),
            MockResult(rows_all=[(2, "张三")]),
        ]

        now = datetime.now()
        # 用 exclude_proposal_tpl_ids 排除方案
        result = await _get_bottleneck_tracking(
            mock_db, now, exclude_proposal_tpl_ids={10, 20, 30}
        )

        assert len(result) == 1  # template_id=5 不在排除列表中
