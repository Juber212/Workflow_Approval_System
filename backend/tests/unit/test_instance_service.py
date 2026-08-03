"""instance_service 单元测试 —— 发起/终止/换人核心验证路径

测试策略：create_instance 成功路径过于复杂（DB + 文件系统 + 工作日），留给集成测试。
单元测试聚焦 validation/guard 逻辑。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models.enums import InstanceStatus, InstanceNodeStatus
from app.services.instance_service import create_instance, terminate_instance, change_personnel

from tests.factories import make_instance, make_node, make_task
from tests.conftest import MockResult


# mock CurrentUser
class FakeUser:
    def __init__(self, id=1, role="manager", real_name="测试"):
        self.id = id
        self.role = role
        self.real_name = real_name


# ============================================================
# create_instance —— 发起实例
# ============================================================

class TestCreateInstance:
    """发起实例相关测试 —— 验证 guard 逻辑"""

    @pytest.mark.asyncio
    async def test_template_not_found(self, mock_db):
        """模板不存在 → 404"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=None),  # SELECT template → 不存在
        ]

        from app.schemas.instance import CreateInstanceRequest
        req = CreateInstanceRequest(template_id=999, name="测试项目")

        with pytest.raises(AppException) as exc:
            await create_instance(mock_db, req, FakeUser())
        assert exc.value.code == ErrorCode.NOT_FOUND

    @pytest.mark.asyncio
    async def test_template_no_nodes(self, mock_db):
        """模板没有节点 → validation error"""
        from app.models import FlowTemplate
        tpl = FlowTemplate(id=1, name="空模板", organization_id=1, type="project")

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=tpl),     # 0: SELECT template → 存在
            MockResult(scalars_all=[]),     # 1: SELECT template nodes → 空
            MockResult(scalars_all=[]),     # 2: SELECT template edges → 空
        ]

        from app.schemas.instance import CreateInstanceRequest
        req = CreateInstanceRequest(template_id=1, name="测试项目")

        with pytest.raises(AppException) as exc:
            await create_instance(mock_db, req, FakeUser())
        assert exc.value.code == ErrorCode.VALIDATION_ERROR


# ============================================================
# terminate_instance —— 终止实例
# ============================================================

class TestTerminateInstance:
    """终止实例相关测试"""

    @pytest.mark.asyncio
    async def test_not_initiator(self, mock_db):
        """非发起人终止 → 403"""
        inst = make_instance(id=1, initiator_id=2, status=InstanceStatus.RUNNING)

        # _get_type_label 在抛出 NOT_INITIATOR 前会再查一次 FlowTemplate
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=inst),     # 0: SELECT instance
            MockResult(scalar_one=None),     # 1: _get_type_label → SELECT template type
        ]

        with pytest.raises(AppException) as exc:
            await terminate_instance(mock_db, instance_id=1, reason="测试", current_user=FakeUser(id=1))
        assert exc.value.code == ErrorCode.NOT_INITIATOR

    @pytest.mark.asyncio
    async def test_already_terminated(self, mock_db):
        """已终止的实例不可重复终止 → 403"""
        inst = make_instance(id=1, initiator_id=1, status=InstanceStatus.TERMINATED)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=inst),  # SELECT instance
        ]

        with pytest.raises(AppException) as exc:
            await terminate_instance(mock_db, instance_id=1, reason="测试", current_user=FakeUser(id=1))
        assert exc.value.code == ErrorCode.INSTANCE_ALREADY_TERMINATED


# ============================================================
# change_personnel —— 紧急换人
# ============================================================

class TestChangePersonnel:
    """紧急换人相关测试"""

    @pytest.mark.asyncio
    async def test_not_initiator(self, mock_db):
        """非发起人换人 → 403"""
        inst = make_instance(id=1, initiator_id=2, status=InstanceStatus.RUNNING)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=inst),  # SELECT instance
        ]

        from app.schemas.instance import ChangePersonnelRequest
        body = ChangePersonnelRequest()

        with pytest.raises(AppException) as exc:
            await change_personnel(mock_db, instance_id=1, node_id=5, body=body, current_user=FakeUser(id=1))
        assert exc.value.code == ErrorCode.NOT_INITIATOR

    @pytest.mark.asyncio
    async def test_node_finished(self, mock_db):
        """已完成节点不可换人 → 403"""
        inst = make_instance(id=1, initiator_id=1, status=InstanceStatus.RUNNING)
        node = make_node(id=5, status=InstanceNodeStatus.FINISHED)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=inst),  # 0: SELECT instance
            MockResult(scalar_one=node),  # 1: SELECT node
        ]

        from app.schemas.instance import ChangePersonnelRequest
        body = ChangePersonnelRequest()

        with pytest.raises(AppException) as exc:
            await change_personnel(mock_db, instance_id=1, node_id=5, body=body, current_user=FakeUser(id=1))
        assert exc.value.code == ErrorCode.NOT_RUNNING

    @pytest.mark.asyncio
    async def test_change_assignee_rejected_when_waiting(self, mock_db):
        """负责人已提交（节点等待审批）→ 换负责人被拒绝"""
        inst = make_instance(id=1, initiator_id=1, status=InstanceStatus.RUNNING)
        node = make_node(id=5, instance_id=1, status=InstanceNodeStatus.WAITING_APPROVAL,
                         assignee_id=2)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=inst),     # SELECT instance
            MockResult(scalar_one=node),     # SELECT node
            MockResult(scalars_all=[]),      # SELECT User（id_name_map）
        ]

        from app.schemas.instance import ChangePersonnelRequest
        body = ChangePersonnelRequest(assignee_id=9)

        with pytest.raises(AppException) as exc:
            await change_personnel(mock_db, instance_id=1, node_id=5, body=body,
                                   current_user=FakeUser(id=1))
        assert exc.value.code == ErrorCode.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_change_assignee_in_processing(self, mock_db):
        """负责人处理中（节点 running）→ 换负责人成功，Task 更新条件覆盖非终结状态"""
        from app.models.enums import TaskStatus
        inst = make_instance(id=1, initiator_id=1, status=InstanceStatus.RUNNING)
        node = make_node(id=5, instance_id=1, status=InstanceNodeStatus.RUNNING,
                         assignee_id=2)
        task = make_task(id=7, node_id=5, instance_id=1, assignee_id=2,
                         status=TaskStatus.PROCESSING)

        captured = []

        async def _fake_execute(stmt, *args, **kwargs):
            captured.append(stmt)
            i = len(captured) - 1
            if i == 0:
                return MockResult(scalar_one=inst)      # SELECT instance
            if i == 1:
                return MockResult(scalar_one=node)      # SELECT node
            if i == 2:
                return MockResult(scalars_all=[])       # SELECT User（id_name_map）
            if i == 3:
                return None                              # update Task（换负责人）
            if i == 4:
                return None                              # clear_related delete
            if i == 5:
                return MockResult(scalars_all=[])       # 通知段：pending CheckRecord → 空
            if i == 6:
                return MockResult(scalars_all=[])       # 通知段：pending Approval → 空
            if i == 7:
                return MockResult(scalar_one=task)      # _get_active_task select
            return None

        mock_db.execute = _fake_execute

        from app.schemas.instance import ChangePersonnelRequest
        body = ChangePersonnelRequest(assignee_id=9)

        result = await change_personnel(mock_db, instance_id=1, node_id=5, body=body,
                                        current_user=FakeUser(id=1))

        # 负责人字段已更新
        assert node.assignee_id == 9
        # 被换掉的人员（旧负责人）返回，供 API 层推送实时刷新
        assert result["removed_users"] == [2]
        # Task 更新语句条件排除终结状态（含 notin_）
        from sqlalchemy.dialects import mysql
        update_stmt = captured[3]
        # literal_binds：NOT IN 列表默认参数化，这里把绑定的状态值渲染进 SQL 以便断言
        sql = str(update_stmt.compile(dialect=mysql.dialect(), compile_kwargs={"literal_binds": True}))
        assert "NOT IN" in sql
        assert "completed" in sql  # 终结状态被排除，活跃任务被覆盖
