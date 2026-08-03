"""集成测试 —— 通知 API（端到端）

使用 FastAPI TestClient + mock 依赖注入：
- get_db → mock AsyncSession
- get_current_active_user → mock CurrentUser
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_active_user, get_db
from app.models import Notification
from tests.conftest import MockResult


# ============================================================
# 测试夹具
# ============================================================

@pytest.fixture
def client_with_mocks():
    """TestClient + mock get_db + mock get_current_active_user"""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.delete = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    _nested_ctx = MagicMock()
    _nested_ctx.__aenter__ = AsyncMock()
    _nested_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_db.begin_nested = MagicMock(return_value=_nested_ctx)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    client.mock_db = mock_db
    yield client
    app.dependency_overrides.clear()


def _user_result(user_id=1, role="manager", org_id=1):
    """创建用户查询的 MockResult"""
    from app.models import User
    user = User(
        id=user_id, username=f"user{user_id}",
        real_name=f"用户{user_id}", password_hash="x",
        organization_id=org_id, is_active=True,
    )
    return MockResult(scalar_one=user)


def _make_token(user_id=1, role="manager", org_id=1):
    """生成 JWT token"""
    from app.core.security import create_access_token
    return create_access_token({
        "sub": str(user_id),
        "username": f"user{user_id}",
        "roles": [role],
        "org_id": org_id,
    })


# ============================================================
# 通知列表
# ============================================================

class TestListNotificationsAPI:
    """GET /api/v1/notifications"""

    def test_list_empty(self, client_with_mocks):
        """无通知 → 200 + 空列表"""
        client = client_with_mocks
        db = client.mock_db

        token = _make_token()

        db.execute = AsyncMock()
        db.execute.side_effect = [
            _user_result(),                   # 0: get_current_active_user
            MockResult(scalars_all=[]),  # 1: 角色查询（P0-9，空则不覆盖 JWT 快照）
            MockResult(scalar_value=0),       # 1: count
            MockResult(scalars_all=[]),       # 2: list
        ]

        resp = client.get(
            "/api/v1/notifications",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["data"]["total"] == 0
        assert data["data"]["items"] == []

    def test_list_with_data(self, client_with_mocks):
        """有通知 → 200 + 列表"""
        client = client_with_mocks
        db = client.mock_db

        token = _make_token()

        notif = Notification(
            id=1, user_id=1, type="task", title="新任务",
            content="你有新的任务", link=None, is_read=False,
            created_at=datetime.now(),
        )

        db.execute = AsyncMock()
        db.execute.side_effect = [
            _user_result(),                    # 0: get_current_active_user
            MockResult(scalars_all=[]),  # 1: 角色查询（P0-9，空则不覆盖 JWT 快照）
            MockResult(scalar_value=1),        # 1: count
            MockResult(scalars_all=[notif]),   # 2: list
        ]

        resp = client.get(
            "/api/v1/notifications",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["data"]["total"] == 1
        assert data["data"]["items"][0]["id"] == 1
        assert data["data"]["items"][0]["type"] == "task"


# ============================================================
# 未读计数
# ============================================================

class TestUnreadCountAPI:
    """GET /api/v1/notifications/unread-count"""

    def test_unread_count(self, client_with_mocks):
        """正常查询 → 200 + count"""
        client = client_with_mocks
        db = client.mock_db

        token = _make_token()

        db.execute = AsyncMock()
        db.execute.side_effect = [
            _user_result(),                   # 0: get_current_active_user
            MockResult(scalars_all=[]),  # 1: 角色查询（P0-9，空则不覆盖 JWT 快照）
            MockResult(scalar_value=3),       # 1: unread count
        ]

        resp = client.get(
            "/api/v1/notifications/unread-count",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["data"]["count"] == 3


# ============================================================
# 删除单条通知（终局事件通知点击即删）
# ============================================================

class TestDeleteNotificationAPI:
    """DELETE /api/v1/notifications/{notification_id}"""

    def test_delete_own_notification(self, client_with_mocks):
        """删除自己的通知 → 200"""
        client = client_with_mocks
        db = client.mock_db

        token = _make_token()

        db.execute = AsyncMock()
        db.execute.side_effect = [
            _user_result(),              # 0: get_current_active_user
            MockResult(scalars_all=[]),  # 1: 角色查询（P0-9，空则不覆盖 JWT 快照）
            MagicMock(rowcount=1),       # 1: delete 命中
        ]

        resp = client.delete(
            "/api/v1/notifications/10",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_delete_not_found(self, client_with_mocks):
        """删除不存在/非本人通知 → 404"""
        client = client_with_mocks
        db = client.mock_db

        token = _make_token()

        db.execute = AsyncMock()
        db.execute.side_effect = [
            _user_result(),              # 0: get_current_active_user
            MockResult(scalars_all=[]),  # 1: 角色查询（P0-9，空则不覆盖 JWT 快照）
            MagicMock(rowcount=0),       # 1: delete 未命中
        ]

        resp = client.delete(
            "/api/v1/notifications/999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"


# ============================================================
# 通知汇总
# ============================================================

class TestSummaryAPI:
    """GET /api/v1/notifications/summary"""

    def test_summary(self, client_with_mocks):
        """正常查询 → 200 + 分类汇总"""
        client = client_with_mocks
        db = client.mock_db

        token = _make_token()

        db.execute = AsyncMock()
        db.execute.side_effect = [
            _user_result(),                   # 0: get_current_active_user
            MockResult(scalars_all=[]),  # 1: 角色查询（P0-9，空则不覆盖 JWT 快照）
            MockResult(rows_all=[]),          # 1: task counts
            MockResult(scalar_value=0),       # 2: check count
            MockResult(rows_all=[]),          # 3: approval counts
            MockResult(rows_all=[]),          # 4: endorsement counts
        ]

        resp = client.get(
            "/api/v1/notifications/summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["data"]["task_count"] == 0
        assert data["data"]["check_count"] == 0
        assert data["data"]["approval_count"] == 0
        assert data["data"]["endorsement_count"] == 0
