"""check_service 单元测试 —— 校验通过/退回核心路径

测试策略：Mock AsyncSession，验证业务逻辑分支，不依赖真实数据库。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, call

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models.enums import CheckStatus, TaskStatus, InstanceNodeStatus, ApprovalStatus
from app.services.check_service import pass_check, return_check

from tests.factories import make_check, make_node, make_task, make_instance
from tests.conftest import MockResult


# ============================================================
# pass_check —— 校验通过
# ============================================================

class TestPassCheck:
    """校验通过相关测试"""

    @pytest.mark.asyncio
    async def test_all_passed_creates_approvals(self, mock_db):
        """全部校验通过 → task 进入 waiting_approval，生成 Approval 记录"""
        check = make_check(id=1, task_id=10, node_id=5, checker_id=3, status=CheckStatus.PENDING)
        node = make_node(id=5, round=1, checkers=[{"user_id": 3, "name": "A"}],
                         approvers=[{"user_id": 4, "name": "审批人A"}],
                         require_checker_signature=False)
        task = make_task(id=10, node_id=5)

        inst = make_instance(id=1, difficulty="1")
        # ABBA 修复后 execute 序：无锁读 check → 锁实例 → 锁节点 → 锁 check 重新校验 → 锁其他 pending
        # → has_pending → task → clear_related
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=check),          # 0: get check（无锁，拿 node_id/instance_id）
            MockResult(scalar_one=inst),            # 1: lock FlowInstance（ABBA 修复：先锁实例）
            MockResult(scalar_one=node),            # 2: lock InstanceNode
            MockResult(scalar_one=check),            # 3: lock check FOR UPDATE（重新校验状态）
            MagicMock(),                            # 4: lock other pending checks (结果不读取)
            MockResult(scalars_all=[]),             # 5: check all pending → 无 pending，全部通过
            MockResult(scalar_one=task),            # 6: get task
            MagicMock(),                            # 7: clear_related delete
        ]

        result = await pass_check(mock_db, check_id=1, current_user_id=3, opinion="通过")

        # 验证返回值
        assert result["all_passed"] is True
        assert "校验通过" in result["message"]

        # 验证 task 状态更新
        assert task.status == TaskStatus.WAITING_APPROVAL
        assert node.status == InstanceNodeStatus.WAITING_APPROVAL

        # 验证 mock_db.add 被调用（Approval 记录 + OperationLog）
        assert mock_db.add.call_count >= 2  # 至少 1 条 Approval + 1 条日志

    @pytest.mark.asyncio
    async def test_not_all_passed_waits(self, mock_db):
        """仅部分校验通过 → 返回 all_passed=False，不生成 Approval"""
        check = make_check(id=1, task_id=10, node_id=5, checker_id=3, status=CheckStatus.PENDING)
        pending_check2 = make_check(id=2, task_id=10, node_id=5, checker_id=6, status=CheckStatus.PENDING)
        node = make_node(id=5)
        inst = make_instance(id=1, difficulty="1")

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=check),              # 0: get check（无锁）
            MockResult(scalar_one=inst),                # 1: lock FlowInstance（ABBA 修复：先锁实例）
            MockResult(scalar_one=node),                # 2: lock InstanceNode
            MockResult(scalar_one=check),               # 3: lock check FOR UPDATE（重新校验）
            MagicMock(),                                # 4: lock other pending
            MockResult(scalars_all=[pending_check2]),   # 5: still has pending → 不触发推进
        ]

        result = await pass_check(mock_db, check_id=1, current_user_id=3, opinion="通过")

        assert result["all_passed"] is False
        assert "等待" in result["message"]

    @pytest.mark.asyncio
    async def test_wrong_checker_rejected(self, mock_db):
        """非校验人操作 → 403"""
        check = make_check(id=1, checker_id=3, status=CheckStatus.PENDING)
        inst = make_instance(id=1, difficulty="1")
        node = make_node(id=5)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=check),   # 0: get check（无锁）
            MockResult(scalar_one=inst),     # 1: lock FlowInstance
            MockResult(scalar_one=node),     # 2: lock InstanceNode
            MockResult(scalar_one=check),   # 3: lock check FOR UPDATE → 校验 checker_id 失败 403
        ]

        with pytest.raises(AppException) as exc:
            await pass_check(mock_db, check_id=1, current_user_id=999, opinion=None)
        assert exc.value.code == ErrorCode.FORBIDDEN

    @pytest.mark.asyncio
    async def test_already_processed_rejected(self, mock_db):
        """已处理的校验记录不可再次操作 → 403"""
        check = make_check(id=1, checker_id=3, status=CheckStatus.PASSED)
        inst = make_instance(id=1, difficulty="1")
        node = make_node(id=5)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=check),   # 0: get check（无锁）
            MockResult(scalar_one=inst),     # 1: lock FlowInstance
            MockResult(scalar_one=node),     # 2: lock InstanceNode
            MockResult(scalar_one=check),   # 3: lock check FOR UPDATE → 状态非 PENDING 拒绝 403
        ]

        with pytest.raises(AppException) as exc:
            await pass_check(mock_db, check_id=1, current_user_id=3, opinion=None)
        assert exc.value.code == ErrorCode.FORBIDDEN

    @pytest.mark.asyncio
    async def test_diff4_no_approver_no_endorser_rejected(self, mock_db):
        """难度4 节点无审批人且无批准人 → 终态校验拦截（批准环节不可跳过）

        场景：实例难度在运行中被提升为 4，但节点未配置批准人（历史实例/异常数据），
        原逻辑会静默跳过批准直接完成节点，使「难度4 需批准人签阅」形同虚设。
        """
        check = make_check(id=1, task_id=10, node_id=5, checker_id=3, status=CheckStatus.PENDING)
        node = make_node(id=5, round=1, approvers=[], require_checker_signature=False)  # 无审批人
        task = make_task(id=10, node_id=5)
        inst = make_instance(id=1, difficulty="4")  # 难度4，节点无批准人

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=check),   # 0: get check（无锁，拿 node_id/instance_id）
            MockResult(scalar_one=inst),     # 1: lock FlowInstance
            MockResult(scalar_one=node),     # 2: lock InstanceNode
            MockResult(scalar_one=check),    # 3: lock check FOR UPDATE（重新校验状态）
            MagicMock(),                     # 4: lock other pending checks
            MockResult(scalars_all=[]),      # 5: check all pending → 无 pending，全部通过
            MockResult(scalar_one=task),     # 6: get task
        ]

        with pytest.raises(AppException) as exc:
            await pass_check(mock_db, check_id=1, current_user_id=3, opinion="通过")
        assert exc.value.code == ErrorCode.VALIDATION_ERROR
        assert "批准人" in str(exc.value)


# ============================================================
# return_check —— 校验退回
# ============================================================

class TestReturnCheck:
    """校验退回相关测试"""

    @pytest.mark.asyncio
    async def test_return_success(self, mock_db):
        """正常退回 → check returned，task processing，round+1，删除文件"""
        check = make_check(id=1, task_id=10, node_id=5, checker_id=3, status=CheckStatus.PENDING)
        node = make_node(id=5, round=1)
        task = make_task(id=10, node_id=5, status=TaskStatus.WAITING_CHECK)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=check),     # 0: get check FOR UPDATE
            MockResult(scalars_all=[]),        # 1: SELECT terminated checkers（P1-12，空）
            MagicMock(),                       # 2: update other pending checks → terminated
            MockResult(scalars_all=[]),        # 3: SELECT terminated endorsers（P1-12，空）
            MagicMock(),                       # 4: update pending endorsements → terminated（难度4场景）
            MockResult(scalar_one=node),       # 5: get node
            MockResult(scalars_all=[]),        # 6: get files (empty)
            MockResult(scalar_one=task),       # 7: get task
        ]

        result = await return_check(mock_db, check_id=1, current_user_id=3, opinion="文件格式错误，请重传")

        assert "已退回" in result["message"]
        assert check.status == CheckStatus.RETURNED
        assert task.status == TaskStatus.PROCESSING
        assert node.round == 2

    @pytest.mark.asyncio
    async def test_return_without_opinion_fails(self, mock_db):
        """退回不填意见 → 400"""
        with pytest.raises(AppException) as exc:
            await return_check(mock_db, check_id=1, current_user_id=3, opinion="")
        assert exc.value.code == ErrorCode.BAD_REQUEST

    @pytest.mark.asyncio
    async def test_return_wrong_checker_rejected(self, mock_db):
        """非校验人退回 → 403"""
        check = make_check(id=1, checker_id=3, status=CheckStatus.PENDING)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=check),
        ]

        with pytest.raises(AppException) as exc:
            await return_check(mock_db, check_id=1, current_user_id=999, opinion="不对")
        assert exc.value.code == ErrorCode.FORBIDDEN
