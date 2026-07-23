"""approval_service 单元测试 —— 审批通过/驳回/终审总驳回核心路径

测试策略：Mock AsyncSession + mocker.patch 隔离外部依赖（propagate_from_node、pdf_signature）
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models.enums import (
    ApprovalStatus, TaskStatus, InstanceNodeStatus, InstanceStatus,
    EndorsementStatus,
)
from app.services.approval_service import approve, reject

from tests.factories import make_approval, make_node, make_task, make_instance
from tests.conftest import MockResult


# ============================================================
# approve —— 审批通过
# ============================================================

class TestApprove:
    """审批通过相关测试"""

    @pytest.mark.asyncio
    async def test_all_approved_normal_node(self, mock_db, mocker):
        """全部审批通过 → 普通节点 finished → 传播到下游"""
        # mock 外部依赖
        mocker.patch("app.services.approval_service.propagate_from_node", new=AsyncMock())

        approval = make_approval(id=1, task_id=10, node_id=5, approver_id=4, status=ApprovalStatus.PENDING)
        node = make_node(id=5, is_end=False, require_approver_signature=False, endorser_id=None,
                         approvers=[{"user_id": 4, "name": "审批人A"}])
        inst = make_instance(id=1, difficulty="1")

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=approval),       # 0: SELECT approval FOR UPDATE
            MagicMock(),                            # 1: lock 其他 pending approvals
            MagicMock(),                            # 2: clear_related delete
            MockResult(scalars_all=[]),             # 3: check remaining pending → 无，全部通过
            MagicMock(),                            # 4: UPDATE task → completed（结果不读）
            MockResult(scalar_one=node),            # 5: SELECT node
            # require_approver_signature=False 跳过签名查询
            MockResult(scalar_one=inst),            # 6: SELECT FlowInstance
            MockResult(scalar_one=None),            # 7: SELECT FlowTemplate（project 类型非 proposal）
        ]

        result = await approve(mock_db, approval_id=1, current_user_id=4, opinion="同意")

        assert result["all_approved"] is True
        assert node.status == InstanceNodeStatus.FINISHED
        assert approval.status == ApprovalStatus.APPROVED

    @pytest.mark.asyncio
    async def test_not_all_approved_waits(self, mock_db):
        """还有审批人未通过 → 返回 all_approved=False"""
        approval = make_approval(id=1, task_id=10, node_id=5, approver_id=4, status=ApprovalStatus.PENDING)
        pending_approval2 = make_approval(id=2, task_id=10, node_id=5, approver_id=6, status=ApprovalStatus.PENDING)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=approval),           # 0: SELECT approval FOR UPDATE
            MagicMock(),                                # 1: lock other pending
            MagicMock(),                                # 2: clear_related delete
            MockResult(scalars_all=[pending_approval2]), # 3: 还有 pending
        ]

        result = await approve(mock_db, approval_id=1, current_user_id=4, opinion="同意")

        assert result["all_approved"] is False
        assert "等待" in result["message"]

    @pytest.mark.asyncio
    async def test_difficulty_4_creates_endorsement(self, mock_db, mocker):
        """难度4 + 有批准人 → 全部审批通过后进入 waiting_endorsement"""
        mocker.patch("app.services.approval_service.propagate_from_node", new=AsyncMock())

        approval = make_approval(id=1, task_id=10, node_id=5, approver_id=4, status=ApprovalStatus.PENDING)
        node = make_node(id=5, is_end=False, require_approver_signature=False,
                         endorser_id=5, approvers=[{"user_id": 4, "name": "A"}])
        inst = make_instance(id=1, difficulty="4")

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=approval),       # 0: SELECT approval FOR UPDATE
            MagicMock(),                            # 1: lock other pending
            MagicMock(),                            # 2: clear_related delete
            MockResult(scalars_all=[]),             # 3: check remaining → 空
            MagicMock(),                            # 4: UPDATE task → completed
            MockResult(scalar_one=node),            # 5: SELECT node
            MockResult(scalar_one=inst),            # 6: SELECT FlowInstance
            MockResult(scalar_one=None),            # 7: SELECT FlowTemplate（非 proposal）
            MagicMock(),                            # 8: UPDATE task → waiting_endorsement（难度4）
        ]

        result = await approve(mock_db, approval_id=1, current_user_id=4, opinion="同意")

        assert result["all_approved"] is True
        assert result.get("waiting_endorsement") is True
        assert node.status == InstanceNodeStatus.WAITING_ENDORSEMENT
        # 验证 Endorsement 记录被创建
        assert mock_db.add.call_count >= 2  # Endorsement + OperationLog

    @pytest.mark.asyncio
    async def test_end_node_completes_instance(self, mock_db):
        """结束节点审批通过 → 流程完成"""
        approval = make_approval(id=1, task_id=None, node_id=20, approver_id=1, status=ApprovalStatus.PENDING)
        node = make_node(id=20, is_end=True, require_approver_signature=False)
        inst = make_instance(id=1, status=InstanceStatus.RUNNING)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=approval),       # 0: SELECT approval FOR UPDATE
            MagicMock(),                            # 1: lock other pending
            MagicMock(),                            # 2: clear_related delete
            MockResult(scalars_all=[]),             # 3: check remaining → 空
            # task_id=None, 跳过 UPDATE task
            MockResult(scalar_one=node),            # 4: SELECT node（is_end=True）
            MockResult(scalar_one=inst),            # 5: SELECT FlowInstance
        ]

        result = await approve(mock_db, approval_id=1, current_user_id=1, opinion="终审通过")

        assert result.get("instance_completed") is True
        assert inst.status == InstanceStatus.COMPLETED
        assert node.status == InstanceNodeStatus.FINISHED

    @pytest.mark.asyncio
    async def test_wrong_approver_rejected(self, mock_db):
        """非审批人操作 → 403"""
        approval = make_approval(id=1, approver_id=4, status=ApprovalStatus.PENDING)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=approval),
        ]

        with pytest.raises(AppException) as exc:
            await approve(mock_db, approval_id=1, current_user_id=999, opinion=None)
        assert exc.value.code == ErrorCode.FORBIDDEN

    @pytest.mark.asyncio
    async def test_already_processed_rejected(self, mock_db):
        """已处理的审批记录 → 403"""
        approval = make_approval(id=1, approver_id=4, status=ApprovalStatus.APPROVED)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=approval),
        ]

        with pytest.raises(AppException) as exc:
            await approve(mock_db, approval_id=1, current_user_id=4, opinion=None)
        assert exc.value.code == ErrorCode.FORBIDDEN


# ============================================================
# reject —— 审批退回/驳回
# ============================================================

class TestReject:
    """审批驳回相关测试"""

    @pytest.mark.asyncio
    async def test_mid_node_reject(self, mock_db):
        """中间节点审批退回 → task processing，round+1"""
        approval = make_approval(id=1, task_id=10, node_id=5, approver_id=4, status=ApprovalStatus.PENDING)
        node = make_node(id=5, is_end=False, round=2)
        task = make_task(id=10, node_id=5, status=TaskStatus.WAITING_APPROVAL)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=approval),       # 0: SELECT approval FOR UPDATE
            MockResult(scalar_one=node),            # 1: SELECT node
            MagicMock(),                            # 2: clear_related delete
            MagicMock(),                            # 3: UPDATE other approvals → terminated
            MagicMock(),                            # 4: UPDATE pending checks → terminated
            MockResult(scalars_all=[]),             # 5: SELECT files（空）
            MockResult(scalar_one=task),            # 6: SELECT task
        ]

        result = await reject(mock_db, approval_id=1, current_user_id=4, opinion="数据不对")

        assert "已退回" in result["message"]
        assert approval.status == ApprovalStatus.REJECTED
        assert task.status == TaskStatus.PROCESSING
        assert node.round == 3  # round+1

    @pytest.mark.asyncio
    async def test_end_node_final_reject(self, mock_db):
        """结束节点终审总驳回 → 目标节点重新激活"""
        approval = make_approval(id=1, task_id=None, node_id=20, approver_id=1, status=ApprovalStatus.PENDING)
        end_node = make_node(id=20, is_end=True, sort_order=3, round=1)
        target_node = make_node(id=5, is_end=False, is_start=False, sort_order=2,
                                assignee_id=2, status=InstanceNodeStatus.FINISHED, round=1)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=approval),       # 0: SELECT approval FOR UPDATE
            MockResult(scalar_one=end_node),        # 1: SELECT node（is_end=True）
            MagicMock(),                            # 2: clear_related delete
            MockResult(scalar_one=target_node),     # 3: SELECT target_node
            MockResult(scalars_all=[]),             # 4: SELECT target files（空）
            MockResult(scalars_all=[]),             # 5: SELECT downstream nodes（空）
            MagicMock(),                            # 6: terminate other approvals
        ]

        result = await reject(mock_db, approval_id=1, current_user_id=1,
                              opinion="全部重做", target_node_id=5)

        assert "已驳回至" in result["message"]
        assert target_node.status == InstanceNodeStatus.RUNNING
        assert target_node.round == 2  # round+1

    @pytest.mark.asyncio
    async def test_reject_without_opinion_fails(self, mock_db):
        """驳回不填意见 → 400"""
        with pytest.raises(AppException) as exc:
            await reject(mock_db, approval_id=1, current_user_id=1, opinion="")
        assert exc.value.code == ErrorCode.BAD_REQUEST

    @pytest.mark.asyncio
    async def test_reject_wrong_approver(self, mock_db):
        """非审批人驳回 → 403"""
        approval = make_approval(id=1, approver_id=4, status=ApprovalStatus.PENDING)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=approval),
        ]

        with pytest.raises(AppException) as exc:
            await reject(mock_db, approval_id=1, current_user_id=999, opinion="不对")
        assert exc.value.code == ErrorCode.FORBIDDEN

    @pytest.mark.asyncio
    async def test_end_reject_without_target_fails(self, mock_db):
        """终审驳回不指定目标节点 → 400"""
        approval = make_approval(id=1, task_id=None, node_id=20, approver_id=1, status=ApprovalStatus.PENDING)
        end_node = make_node(id=20, is_end=True)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=approval),       # 0: SELECT approval FOR UPDATE
            MockResult(scalar_one=end_node),        # 1: SELECT node（is_end=True）
        ]

        with pytest.raises(AppException) as exc:
            await reject(mock_db, approval_id=1, current_user_id=1, opinion="重做", target_node_id=None)
        assert exc.value.code == ErrorCode.BAD_REQUEST
