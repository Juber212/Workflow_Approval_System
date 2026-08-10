"""dashboard_service 单元测试 —— 各所概览 + 卡点追踪过滤 + 我的待办分组总数"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from types import SimpleNamespace

from app.models import Organization, FlowInstance, InstanceNode, User
from app.models.enums import InstanceStatus, InstanceNodeStatus
from app.services.dashboard_service import (
    _get_org_overview,
    _get_bottleneck_tracking,
    _get_my_pending_items,
    get_flow_trends,
)
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
            # 2: 完成数按粒度统计（今日0 本月2 本年3）
            MockResult(rows_all=[(1, 0, 2, 3)]),
        ]

        result = await _get_org_overview(mock_db, template_type="project")

        assert len(result) == 1
        assert result[0].org_id == 1
        assert result[0].running_count == 5
        assert result[0].completed_count == 2  # 本月已完成（兼容字段）
        assert result[0].total_count == 9  # 5+3+1
        assert result[0].day_completed_count == 0
        assert result[0].month_completed_count == 2
        assert result[0].year_completed_count == 3

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
            MockResult(rows_all=[(1, 1, 4, 5)]),  # 今日1 本月4 本年5
        ]

        result = await _get_org_overview(mock_db, template_type="proposal")

        assert len(result) == 1
        assert result[0].running_count == 2
        assert result[0].completed_count == 4  # 本月已完成（兼容字段）
        assert result[0].total_count == 6
        assert result[0].day_completed_count == 1
        assert result[0].month_completed_count == 4
        assert result[0].year_completed_count == 5

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
        """无运行中实例 → 空列表 + total=0"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_value=0),   # COUNT running instances（真实总数）
            MockResult(scalars_all=[]),   # SELECT running instances（前 N 条）
        ]

        now = datetime.now()
        items, total = await _get_bottleneck_tracking(mock_db, now)
        assert items == []
        assert total == 0

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
            # 0: COUNT running instances（真实总数）
            MockResult(scalar_value=1),
            # 1: SELECT running instances（前 N 条）
            MockResult(scalars_all=[inst]),
            # 2: SELECT nodes
            MockResult(scalars_all=[node]),
            # 3: SELECT org names
            MockResult(scalars_all=[Organization(id=1, name="测试所")]),
            # 4: SELECT all personnel names（使用 .all()）
            MockResult(rows_all=[(2, "张三")]),
        ]

        now = datetime.now()
        items, total = await _get_bottleneck_tracking(mock_db, now)

        assert total == 1
        assert len(items) == 1
        assert items[0].instance_id == 1
        assert items[0].instance_name == "测试项目"
        assert items[0].organization_name == "测试所"
        assert items[0].current_handlers == "张三"
        assert items[0].difficulty == "1"

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
            MockResult(scalar_value=1),   # COUNT running instances
            MockResult(scalars_all=[inst]),
            MockResult(scalars_all=[node]),
            MockResult(scalars_all=[Organization(id=1, name="测试所")]),
            MockResult(rows_all=[(2, "张三")]),
        ]

        now = datetime.now()
        # M15：用 template_type 快照口径（原 exclude_proposal_tpl_ids 语义 → "project"）
        items, total = await _get_bottleneck_tracking(mock_db, now, template_type="project")

        assert total == 1
        assert len(items) == 1  # 项目类型实例返回


# ============================================================
# 我的待办列表 —— 分组真实全量条数（P1-33）
# ============================================================

class TestMyPendingItems:
    """_get_my_pending_items 分组 + 真实全量条数统计（列表仅展示前 8 条，total 为完整计数）"""

    @staticmethod
    def _row(rid: int, template_type: str) -> SimpleNamespace:
        """构造待办行（对齐 _cols 列序：rid/node_name/deadline/instance_name/priority/template_type/instance_id）"""
        return SimpleNamespace(
            rid=rid, node_name="测试节点", deadline=None,
            instance_name=f"{'项目' if template_type == 'project' else '方案'}-{rid}",
            priority="normal", template_type=template_type, instance_id=100 + rid,
        )

    @pytest.mark.asyncio
    async def test_total_counts_with_overflow(self, mock_db):
        """项目待办超过 8 条 → project_total 为真实全量，列表截断为 8；方案 normal"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            # 0: tasks（9 项目 + 1 方案）
            MockResult(rows_all=[self._row(i, "project") for i in range(1, 10)] + [self._row(99, "proposal")]),
            # 1: checks
            MockResult(rows_all=[]),
            # 2: approvals
            MockResult(rows_all=[]),
        ]

        result = await _get_my_pending_items(mock_db, user_id=5)

        # P1-33 核心：真实全量条数不截断
        assert result["project_total"] == 9
        assert result["proposal_total"] == 1
        # 列表展示仍截断为 8 条（与前端「最多显示 8 条」标注呼应）
        assert len(result["project"]) == 8
        assert len(result["proposal"]) == 1
        assert all(it["type"] == "task" for it in result["project"])

    @pytest.mark.asyncio
    async def test_total_counts_no_overflow(self, mock_db):
        """三表合并且未超过 8 条 → total 与列表长度一致，方案为空"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(rows_all=[self._row(1, "project"), self._row(2, "project")]),  # 2 tasks
            MockResult(rows_all=[self._row(3, "project")]),                            # 1 check
            MockResult(rows_all=[]),                                                   # 0 approval
        ]

        result = await _get_my_pending_items(mock_db, user_id=5)

        assert result["project_total"] == 3
        assert result["proposal_total"] == 0
        assert len(result["project"]) == 3
        assert len(result["proposal"]) == 0


# ============================================================
# 发起/归档趋势 —— 月/年粒度 + 补零 + 项目/方案口径
# ============================================================

class TestFlowTrends:
    """get_flow_trends 聚合、补零与口径逻辑"""

    @pytest.mark.asyncio
    async def test_month_default_last_12(self, mock_db):
        """近 12 个月：连续 12 点，无数据补零，末点为当前月"""
        now = datetime.now()
        cur_key = f"{now.year:04d}-{now.month:02d}"
        # 当前月往前 1 个月（构造有数据的相邻月）
        pm_total = now.year * 12 + (now.month - 1) - 1
        pm_y, pm_m = pm_total // 12, pm_total % 12 + 1
        prev_key = f"{pm_y:04d}-{pm_m:02d}"

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(rows_all=[(cur_key, 5), (prev_key, 3)]),  # 发起量聚合
            MockResult(rows_all=[(cur_key, 2)]),                 # 归档量聚合
        ]

        result = await get_flow_trends(mock_db, "month", "project")

        assert result.granularity == "month"
        assert len(result.periods) == 12
        # 末点 = 当前月：发起 5 归档 2
        assert result.periods[-1].period == cur_key
        assert result.periods[-1].initiated == 5
        assert result.periods[-1].completed == 2
        # 前一个点：发起 3 归档 0（归档补零）
        assert result.periods[-2].initiated == 3
        assert result.periods[-2].completed == 0
        # 首点无数据全为 0；且 12 点连续（每点比前一点后移 1 个月）
        assert result.periods[0].initiated == 0
        assert result.periods[0].completed == 0
        for prev_p, cur_p in zip(result.periods, result.periods[1:]):
            py, pm = int(prev_p.period[:4]), int(prev_p.period[5:])
            expect_next = (py + 1, 1) if pm == 12 else (py, pm + 1)
            assert (int(cur_p.period[:4]), int(cur_p.period[5:])) == expect_next

    @pytest.mark.asyncio
    async def test_month_specific_year(self, mock_db):
        """指定年份：返回该年 12 个月，范围外数据（其他年份 key）不混入"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            # 发起量聚合（2024-12 属范围外，不应出现在 2025 结果中）
            MockResult(rows_all=[("2025-03", 4), ("2024-12", 9)]),
            MockResult(rows_all=[]),
        ]

        result = await get_flow_trends(mock_db, "month", "project", year=2025)

        assert len(result.periods) == 12
        assert result.periods[0].period == "2025-01"
        assert result.periods[-1].period == "2025-12"
        assert result.periods[2].period == "2025-03"
        assert result.periods[2].initiated == 4
        assert result.periods[2].completed == 0  # 该月无归档 → 补零
        # 2024-12 不进入 2025 结果
        assert all(p.period.startswith("2025") for p in result.periods)

    @pytest.mark.asyncio
    async def test_year_aggregate(self, mock_db):
        """年度：最早数据年份 → 当前年，各年补零"""
        now_year = datetime.now().year
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(rows_all=[("2025", 10), ("2024", 8)]),  # 发起量聚合
            MockResult(rows_all=[("2025", 6)]),                # 归档量聚合
        ]

        result = await get_flow_trends(mock_db, "year", "project")

        assert result.granularity == "year"
        # 2024 → 当前年
        assert len(result.periods) == now_year - 2024 + 1
        assert result.periods[0].period == "2024"
        assert result.periods[0].initiated == 8
        assert result.periods[0].completed == 0
        assert result.periods[1].period == "2025"
        assert result.periods[1].initiated == 10
        assert result.periods[1].completed == 6
        # 当前年暂无数据 → 补 0
        assert result.periods[-1].period == str(now_year)
        assert result.periods[-1].initiated == 0

    @pytest.mark.asyncio
    async def test_year_no_data(self, mock_db):
        """年度无任何数据 → 空 periods（不报错）"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(rows_all=[]),  # 发起量聚合
            MockResult(rows_all=[]),  # 归档量聚合
        ]

        result = await get_flow_trends(mock_db, "year", "project")

        assert result.periods == []

    @pytest.mark.asyncio
    async def test_proposal_filter_uses_template_type(self, mock_db):
        """方案口径：过滤条件为 template_type = 'proposal'（实例快照，M15）"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(rows_all=[]),  # 发起量聚合
            MockResult(rows_all=[]),  # 归档量聚合
        ]

        await get_flow_trends(mock_db, "month", "proposal")

        # 第一个 execute = 发起量聚合，编译后 SQL 应含 template_type 过滤（参数化渲染）
        initiated_stmt = mock_db.execute.call_args_list[0][0][0]
        assert "template_type =" in str(initiated_stmt)

    @pytest.mark.asyncio
    async def test_project_filter_uses_template_type(self, mock_db):
        """项目口径：过滤条件为 template_type = 'project'（实例快照，M15）"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(rows_all=[]),  # 发起量聚合
            MockResult(rows_all=[]),  # 归档量聚合
        ]

        await get_flow_trends(mock_db, "month", "project")

        initiated_stmt = mock_db.execute.call_args_list[0][0][0]
        assert "template_type =" in str(initiated_stmt)
