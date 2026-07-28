"""notification_service 单元测试 —— 列表/未读/已读/清除/汇总"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from app.models import Notification, FlowInstance, Task, CheckRecord, Approval, Endorsement
from app.services.notification_service import (
    list_notifications, get_unread_count, mark_read, mark_all_read,
    clear_related, get_summary,
)
from tests.conftest import MockResult


# ============================================================
# 通知列表
# ============================================================

class TestListNotifications:
    """list_notifications —— 分页倒序列表"""

    @pytest.mark.asyncio
    async def test_returns_paginated(self, mock_db):
        """有通知 → 返回分页列表"""
        notif = Notification(
            id=1, user_id=1, type="task", title="新任务",
            content="你有新的任务", link="/flows/instances/1", is_read=False,
            created_at=datetime.now(),
        )

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_value=1),            # 0: count
            MockResult(scalars_all=[notif]),        # 1: list
        ]

        result = await list_notifications(mock_db, user_id=1, page=1, page_size=20)
        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].id == 1
        assert result.items[0].type == "task"

    @pytest.mark.asyncio
    async def test_empty_list(self, mock_db):
        """无通知 → 空列表"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_value=0),       # 0: count → 0
            MockResult(scalars_all=[]),       # 1: list → 空
        ]

        result = await list_notifications(mock_db, user_id=1)
        assert result.total == 0
        assert result.items == []


# ============================================================
# 未读计数
# ============================================================

class TestGetUnreadCount:
    """get_unread_count —— 未读通知数量"""

    @pytest.mark.asyncio
    async def test_positive(self, mock_db):
        """有未读 → 返回计数"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_value=5),  # 0: count query
        ]

        result = await get_unread_count(mock_db, user_id=1)
        assert result.count == 5

    @pytest.mark.asyncio
    async def test_zero(self, mock_db):
        """无未读 → 返回 0"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_value=0),  # 0: count query
        ]

        result = await get_unread_count(mock_db, user_id=1)
        assert result.count == 0


# ============================================================
# 标记已读
# ============================================================

class TestMarkRead:
    """mark_read —— 单条已读"""

    @pytest.mark.asyncio
    async def test_success(self, mock_db):
        """正常标记 → 不抛异常"""
        mock_db.execute = AsyncMock()
        mock_db.execute.return_value = MockResult()  # update 不关心返回值
        mock_db.flush = AsyncMock()

        # 不应抛异常
        await mark_read(mock_db, notification_id=1, user_id=1)
        mock_db.execute.assert_called_once()
        mock_db.flush.assert_called_once()


class TestMarkAllRead:
    """mark_all_read —— 全部已读"""

    @pytest.mark.asyncio
    async def test_success(self, mock_db):
        """正常标记全部 → 不抛异常"""
        mock_db.execute = AsyncMock()
        mock_db.execute.return_value = MockResult()
        mock_db.flush = AsyncMock()

        await mark_all_read(mock_db, user_id=1)
        mock_db.execute.assert_called_once()
        mock_db.flush.assert_called_once()


# ============================================================
# 清除关联通知
# ============================================================

class TestClearRelated:
    """clear_related —— 操作完成后删除相关通知"""

    @pytest.mark.asyncio
    async def test_success(self, mock_db):
        """正常删除 → 不抛异常"""
        mock_db.execute = AsyncMock()
        mock_db.execute.return_value = MockResult()
        mock_db.flush = AsyncMock()

        await clear_related(mock_db, user_id=1, types=["task", "check"])
        mock_db.execute.assert_called_once()
        mock_db.flush.assert_called_once()


# ============================================================
# 通知汇总（红点数据）
# ============================================================

class TestGetSummary:
    """get_summary —— 待办/校验/审批/批准汇总计数"""

    @pytest.mark.asyncio
    async def test_all_empty(self, mock_db):
        """无任何待处理 → 各项均为 0"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(rows_all=[]),          # 0: task counts
            MockResult(scalar_value=0),       # 1: check count
            MockResult(rows_all=[]),          # 2: approval counts
            MockResult(rows_all=[]),          # 3: endorsement counts
        ]

        result = await get_summary(mock_db, user_id=1)
        assert result["task_count"] == 0
        assert result["check_count"] == 0
        assert result["approval_count"] == 0
        assert result["endorsement_count"] == 0
        assert result["project_pending"] == 0
        assert result["proposal_pending"] == 0

    @pytest.mark.asyncio
    async def test_with_data(self, mock_db):
        """有待处理项 → 返回正确汇总"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            # 0: task counts — [(template_type, count), ...]
            MockResult(rows_all=[("project", 3), ("proposal", 2)]),
            # 1: check count
            MockResult(scalar_value=1),
            # 2: approval counts
            MockResult(rows_all=[("project", 2), ("proposal", 1)]),
            # 3: endorsement counts
            MockResult(rows_all=[("project", 1)]),
        ]

        result = await get_summary(mock_db, user_id=1)
        assert result["task_count"] == 5  # 3 + 2
        assert result["check_count"] == 1
        assert result["approval_count"] == 3  # 2 + 1
        assert result["endorsement_count"] == 1
        # 项目 pending = 3(task) + 1(check) + 2(approval) + 1(endorsement) = 7
        assert result["project_pending"] == 7
        # 方案 pending = 2(task) + 1(approval) = 3
        assert result["proposal_pending"] == 3
        # 分类 breakdown
        assert result["project_task_count"] == 3
        assert result["project_check_count"] == 1
        assert result["project_approval_count"] == 2
        assert result["project_endorsement_count"] == 1
        assert result["proposal_task_count"] == 2
        assert result["proposal_approval_count"] == 1
        assert result["proposal_endorsement_count"] == 0
