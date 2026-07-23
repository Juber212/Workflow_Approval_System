"""task_service 单元测试 —— 任务提交/草稿保存/详情查询核心路径

测试策略：Mock AsyncSession + mocker.patch 隔离文件 I/O 和 PDF 转换。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models.enums import TaskStatus, InstanceNodeStatus, CheckStatus, ApprovalStatus
from app.services.task_service import submit_task, save_draft

from tests.factories import make_task, make_node
from tests.conftest import MockResult


# ============================================================
# submit_task —— 提交任务
# ============================================================

class TestSubmitTask:
    """任务提交相关测试"""

    @pytest.mark.asyncio
    async def test_submit_with_checkers(self, mock_db, mocker):
        """有校验人 → task → waiting_check，生成 CheckRecord"""
        # mock 文件校验和 PDF 转换（避免文件 I/O）
        mocker.patch("app.services.task_service._validate_file_submission", new=AsyncMock())
        mocker.patch("app.services.task_service._convert_files_to_pdf", new=AsyncMock())

        task = make_task(id=1, node_id=5, assignee_id=2, status=TaskStatus.PROCESSING)
        node = make_node(id=5, checkers=[{"user_id": 3, "name": "校验人A"}],
                         approvers=[{"user_id": 4}])

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=task),   # 0: SELECT task
            MockResult(scalar_one=node),   # 1: SELECT node
        ]

        # 模拟 submit data
        from app.schemas.task import TaskSubmit
        data = TaskSubmit(assignee_note="已完成设计")

        result = await submit_task(mock_db, task_id=1, current_user_id=2, data=data)

        assert "等待校验" in result["message"]
        assert task.status == TaskStatus.WAITING_CHECK
        assert node.status == InstanceNodeStatus.WAITING_CHECK

        # 验证 CheckRecord 被创建
        add_calls = [c for c in mock_db.add.call_args_list if hasattr(c[0][0], 'checker_id')]
        assert len(add_calls) == 1

    @pytest.mark.asyncio
    async def test_submit_without_checkers(self, mock_db, mocker):
        """无校验人 → 直接进入 waiting_approval，生成 Approval"""
        mocker.patch("app.services.task_service._validate_file_submission", new=AsyncMock())
        mocker.patch("app.services.task_service._convert_files_to_pdf", new=AsyncMock())

        task = make_task(id=1, node_id=5, assignee_id=2, status=TaskStatus.PROCESSING)
        node = make_node(id=5, checkers=[], approvers=[{"user_id": 4, "name": "审批人A"}])

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=task),   # 0: SELECT task
            MockResult(scalar_one=node),   # 1: SELECT node
        ]

        from app.schemas.task import TaskSubmit
        data = TaskSubmit(assignee_note="直接提交审批")

        result = await submit_task(mock_db, task_id=1, current_user_id=2, data=data)

        assert "等待审批" in result["message"]
        assert task.status == TaskStatus.WAITING_APPROVAL
        assert node.status == InstanceNodeStatus.WAITING_APPROVAL

        # 验证 Approval 被创建
        add_calls = [c for c in mock_db.add.call_args_list if hasattr(c[0][0], 'approver_id')]
        assert len(add_calls) == 1

    @pytest.mark.asyncio
    async def test_submit_wrong_assignee(self, mock_db):
        """非负责人提交 → 403"""
        task = make_task(id=1, assignee_id=2, status=TaskStatus.PROCESSING)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=task),
        ]

        from app.schemas.task import TaskSubmit
        data = TaskSubmit()

        with pytest.raises(AppException) as exc:
            await submit_task(mock_db, task_id=1, current_user_id=999, data=data)
        assert exc.value.code == ErrorCode.FORBIDDEN

    @pytest.mark.asyncio
    async def test_submit_wrong_status(self, mock_db):
        """已完成的任务不可提交 → 403"""
        task = make_task(id=1, assignee_id=2, status=TaskStatus.COMPLETED)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=task),
        ]

        from app.schemas.task import TaskSubmit
        data = TaskSubmit()

        with pytest.raises(AppException) as exc:
            await submit_task(mock_db, task_id=1, current_user_id=2, data=data)
        assert exc.value.code == ErrorCode.FORBIDDEN


# ============================================================
# save_draft —— 保存草稿
# ============================================================

class TestSaveDraft:
    """草稿保存相关测试"""

    @pytest.mark.asyncio
    async def test_save_draft_success(self, mock_db):
        """正常保存备注 → 更新 assignee_note"""
        task = make_task(id=1, assignee_id=2, status=TaskStatus.PROCESSING, assignee_note=None)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=task),
        ]

        await save_draft(mock_db, task_id=1, current_user_id=2, note="草稿备注")

        assert task.assignee_note == "草稿备注"
        mock_db.flush.assert_awaited()

    @pytest.mark.asyncio
    async def test_save_draft_wrong_user(self, mock_db):
        """非负责人保存 → 403"""
        task = make_task(id=1, assignee_id=2)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=task),
        ]

        with pytest.raises(AppException) as exc:
            await save_draft(mock_db, task_id=1, current_user_id=999, note="test")
        assert exc.value.code == ErrorCode.FORBIDDEN

    @pytest.mark.asyncio
    async def test_save_draft_wrong_status(self, mock_db):
        """已完成的任务不可保存 → 403"""
        task = make_task(id=1, assignee_id=2, status=TaskStatus.COMPLETED)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=task),
        ]

        with pytest.raises(AppException) as exc:
            await save_draft(mock_db, task_id=1, current_user_id=2, note="test")
        assert exc.value.code == ErrorCode.FORBIDDEN
