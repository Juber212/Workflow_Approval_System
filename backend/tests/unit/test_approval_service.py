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
from app.services.approval_service import approve, reject, _preserved_upstream_count

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
            MockResult(scalar_one=node),            # 3: SELECT node（审批策略判断）
            MockResult(scalars_all=[]),             # 4: check remaining pending → 无，全部通过
            MagicMock(),                            # 5: UPDATE task → completed（结果不读）
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
        node = make_node(id=5, is_end=False, approvers=[{"user_id":4},{"user_id":6}])

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=approval),           # 0: SELECT approval FOR UPDATE
            MagicMock(),                                # 1: lock other pending
            MagicMock(),                                # 2: clear_related delete
            MockResult(scalar_one=node),               # 3: SELECT node（审批策略判断）
            MockResult(scalars_all=[pending_approval2]), # 4: 还有 pending
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
            MockResult(scalar_one=node),            # 3: SELECT node（审批策略判断）
            MockResult(scalars_all=[]),             # 4: check remaining → 空
            MagicMock(),                            # 5: UPDATE task → completed
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
            MockResult(scalar_one=node),            # 3: SELECT node（is_end=True）
            MockResult(scalars_all=[]),             # 4: check remaining → 空
            # task_id=None, 跳过 UPDATE task
            # is_end=True, 跳过签名查询
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

    @pytest.mark.asyncio
    async def test_all_approve_aggregation_limited_by_task_id(self, mock_db, mocker):
        """P1-11：all_approve 聚合只统计当前 task 的 pending，跨 task 残留不阻塞

        模拟"当前 task 已无 pending"（跨 task 的残留 pending 被 SQL 排除），
        流程应判定全部通过推进，而非卡在等待其他审批人。
        """
        mocker.patch("app.services.approval_service.propagate_from_node", new=AsyncMock())

        approval = make_approval(id=1, task_id=10, node_id=5, approver_id=4, status=ApprovalStatus.PENDING)
        node = make_node(id=5, is_end=False, require_approver_signature=False, endorser_id=None)
        inst = make_instance(id=1, difficulty="1")

        captured: list = []

        async def _fake_execute(stmt, *args, **kwargs):
            captured.append(stmt)
            i = len(captured) - 1
            if i == 0:
                return MockResult(scalar_one=approval)   # SELECT approval FOR UPDATE
            if i == 1:
                return MagicMock()                        # lock other pending
            if i == 2:
                return MagicMock()                        # clear_related delete
            if i == 3:
                return MockResult(scalar_one=node)        # SELECT node（审批策略判断）
            if i == 4:
                return MockResult(scalars_all=[])         # remaining pending → 当前 task 无 pending
            if i == 5:
                return MagicMock()                        # UPDATE task → completed
            if i == 6:
                return MockResult(scalar_one=inst)        # SELECT FlowInstance
            if i == 7:
                return MockResult(scalar_one=None)        # SELECT FlowTemplate（非 proposal）
            return None

        mock_db.execute = _fake_execute

        result = await approve(mock_db, approval_id=1, current_user_id=4, opinion="同意")

        assert result["all_approved"] is True
        # 聚合查询（captured[4]）必须限定 task_id == 10（当前任务），与 single_approve 对齐
        from sqlalchemy.dialects import mysql
        sql = str(captured[4].compile(dialect=mysql.dialect(), compile_kwargs={"literal_binds": True}))
        assert "task_id = 10" in sql

    @pytest.mark.asyncio
    async def test_signature_applied_update_limited_by_task_id(self, mock_db, mocker):
        """P1-11：signature_applied 批量更新只标当前 task 的 APPROVED 审批，不误标历史轮次"""
        mocker.patch("app.services.approval_service.propagate_from_node", new=AsyncMock())

        approval = make_approval(id=1, task_id=10, node_id=5, approver_id=4, status=ApprovalStatus.PENDING)
        node = make_node(id=5, is_end=False, require_approver_signature=True, endorser_id=None)
        inst = make_instance(id=1, difficulty="1")
        pending_sig = MagicMock()
        pending_sig.id = 99

        captured: list = []

        async def _fake_execute(stmt, *args, **kwargs):
            captured.append(stmt)
            i = len(captured) - 1
            if i == 0:
                return MockResult(scalar_one=approval)       # SELECT approval FOR UPDATE
            if i == 1:
                return MagicMock()                            # lock other pending
            if i == 2:
                return MagicMock()                            # clear_related delete
            if i == 3:
                return MockResult(scalar_one=node)            # SELECT node
            if i == 4:
                return MockResult(scalars_all=[])             # remaining pending → 空
            if i == 5:
                return MagicMock()                            # UPDATE task → completed
            if i == 6:
                return MockResult(scalars_all=[pending_sig])  # SELECT Signature pending
            if i == 7:
                return MagicMock()                            # UPDATE Approval signature_applied
            if i == 8:
                return MockResult(scalar_one=inst)            # SELECT FlowInstance
            if i == 9:
                return MockResult(scalar_one=None)            # SELECT FlowTemplate（非 proposal）
            return None

        mock_db.execute = _fake_execute

        result = await approve(mock_db, approval_id=1, current_user_id=4, opinion="同意")

        assert result["all_approved"] is True
        # 签名状态更新语句（captured[7]）必须限定 task_id == 10，只标当前任务轮次
        from sqlalchemy.dialects import mysql
        sql = str(captured[7].compile(dialect=mysql.dialect(), compile_kwargs={"literal_binds": True}))
        assert "task_id = 10" in sql
        assert "signature_applied" in sql


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
            MockResult(scalars_all=[]),             # 3: SELECT terminated approvers（P1-12，空）
            MagicMock(),                            # 4: UPDATE other approvals → terminated
            MockResult(scalars_all=[]),             # 5: SELECT terminated checkers（P1-12，空）
            MagicMock(),                            # 6: UPDATE pending checks → terminated
            MockResult(scalars_all=[]),             # 7: SELECT terminated endorsers（P1-12，空）
            MagicMock(),                            # 8: UPDATE pending endorsements → terminated（难度4场景）
            MockResult(scalars_all=[]),             # 9: SELECT files（空）
            MockResult(scalar_one=task),            # 10: SELECT task
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
            MockResult(scalars_all=[]),             # 5: SELECT edges from target_node（边遍历）
            MockResult(scalars_all=[]),             # 6: SELECT downstream nodes（空）
            MockResult(scalars_all=[]),             # 7: SELECT terminated approvers（P1-12，空）
            MagicMock(),                            # 8: terminate other approvals
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
    async def test_reject_clears_notification_for_terminated_approver(self, mock_db, mocker):
        """P1-12：驳回终止其他待审批记录时，清除被终止审批人的待办通知"""
        # patch notification_service.clear_related —— clear_related_for_users 内部调用的名字
        mock_clear = mocker.patch("app.services.notification_service.clear_related", new=AsyncMock())

        approval = make_approval(id=1, task_id=10, node_id=5, approver_id=4, status=ApprovalStatus.PENDING)
        node = make_node(id=5, is_end=False, round=2)
        task = make_task(id=10, node_id=5, status=TaskStatus.WAITING_APPROVAL)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=approval),       # 0: SELECT approval FOR UPDATE
            MockResult(scalar_one=node),            # 1: SELECT node
            MagicMock(),                            # 2: clear_related（reject 开头，真调用）
            MockResult(scalars_all=[9]),            # 3: SELECT terminated approvers（被终止审批人 id=9）
            MagicMock(),                            # 4: UPDATE approvals → terminated
            MockResult(scalars_all=[]),             # 5: SELECT terminated checkers（空）
            MagicMock(),                            # 6: UPDATE checks → terminated
            MockResult(scalars_all=[]),             # 7: SELECT terminated endorsers（空）
            MagicMock(),                            # 8: UPDATE endorsements → terminated
            MockResult(scalars_all=[]),             # 9: SELECT files（空）
            MockResult(scalar_one=task),            # 10: SELECT task
        ]

        result = await reject(mock_db, approval_id=1, current_user_id=4, opinion="数据不对")

        assert "已退回" in result["message"]
        # 被终止审批人 id=9 的待办通知被清除（clear_related_for_users 内部调用）
        mock_clear.assert_any_call(
            mock_db, user_id=9, types=["approval_assigned"], instance_id=1
        )

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


# ============================================================
# _preserved_upstream_count —— 驳回后汇合点保留兄弟分支计数（P0-5）
# ============================================================

class TestPreservedUpstreamCount:
    """P0-5 修复：fork/join 驳回到分支内节点时，汇合点保留已完成兄弟分支的到达计数"""

    @pytest.mark.asyncio
    async def test_non_join_returns_zero(self, mock_db):
        """非汇合点（incoming_count <= 1）→ 返回 0，不触发查询"""
        dn = make_node(id=5)
        dn.incoming_count = 1
        assert await _preserved_upstream_count(mock_db, 1, dn, {1}) == 0
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_join_preserves_finished_sibling(self, mock_db):
        """汇合点：非重做且已 FINISHED 的兄弟分支计数保留，重做路径节点不计入"""
        dn = make_node(id=9)
        dn.incoming_count = 2
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalars_all=[7, 8]),  # 直接上游：7（兄弟分支）、8（重做分支）
            MockResult(rows_all=[(7, "finished"), (8, "running")]),  # 上游状态
        ]
        # redo_ids={8}：节点 8 在重做路径，不计入；节点 7 为已完成的兄弟分支，保留
        count = await _preserved_upstream_count(mock_db, 1, dn, {8})
        assert count == 1

    @pytest.mark.asyncio
    async def test_join_no_finished_sibling_returns_zero(self, mock_db):
        """汇合点：无已完成的兄弟分支（全部重做）→ 返回 0"""
        dn = make_node(id=9)
        dn.incoming_count = 2
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalars_all=[7, 8]),  # 直接上游
            MockResult(rows_all=[(7, "waiting"), (8, "waiting")]),  # 都在重做/等待
        ]
        count = await _preserved_upstream_count(mock_db, 1, dn, {7, 8})
        assert count == 0
