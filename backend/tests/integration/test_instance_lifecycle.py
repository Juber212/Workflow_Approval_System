"""集成测试 —— 实例生命周期（API 端到端）

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
from app.models.enums import (
    InstanceStatus, InstanceNodeStatus, Priority,
)
from tests.factories import make_instance
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
# 项目终止
# ============================================================

class TestTerminateInstance:
    """POST /api/v1/instances/{id}/terminate"""

    def test_terminate_not_initiator(self, client_with_mocks):
        """非发起人终止 → 403"""
        client = client_with_mocks
        db = client.mock_db

        token = _make_token(user_id=99)

        inst = make_instance(id=1, initiator_id=1, status=InstanceStatus.RUNNING)

        db.execute = AsyncMock()
        db.execute.side_effect = [
            _user_result(user_id=99),  # 0: get_current_active_user
            MockResult(scalar_one=inst),  # 1: SELECT instance
            MockResult(scalar_one=None),  # 2: template type for _get_type_label
        ]

        resp = client.post(
            "/api/v1/instances/1/terminate",
            json={"reason": "不需要了"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"

    def test_terminate_already_terminated(self, client_with_mocks):
        """已终止的实例不能再终止 → 403"""
        client = client_with_mocks
        db = client.mock_db

        token = _make_token()

        inst = make_instance(id=1, initiator_id=1, status=InstanceStatus.TERMINATED)

        db.execute = AsyncMock()
        db.execute.side_effect = [
            _user_result(),            # 0: get_current_active_user
            MockResult(scalar_one=inst),  # 1: SELECT instance
            MockResult(scalar_one=None),  # 2: template type for _get_type_label
        ]

        resp = client.post(
            "/api/v1/instances/1/terminate",
            json={"reason": "不需要了"},
            headers={"Authorization": f"Bearer {token}"},
        )
        # terminate_instance 返回 INSTANCE_ALREADY_TERMINATED = 403
        assert resp.status_code in (403, 409), f"Expected 403/409, got {resp.status_code}"


# ============================================================
# 优先级修改
# ============================================================

class TestChangePriority:
    """PUT /api/v1/instances/{id}/priority"""

    def test_change_priority_not_initiator(self, client_with_mocks):
        """非发起人修改优先级 → 403"""
        client = client_with_mocks
        db = client.mock_db

        token = _make_token(user_id=99)

        inst = make_instance(id=1, initiator_id=1, status=InstanceStatus.RUNNING,
                             priority=Priority.NORMAL)

        db.execute = AsyncMock()
        db.execute.side_effect = [
            _user_result(user_id=99),   # 0: get_current_active_user
            MockResult(scalar_one=inst),  # 1: SELECT instance
            MockResult(scalar_one=None),  # 2: template type for _get_type_label
        ]

        resp = client.put(
            "/api/v1/instances/1/priority",
            json={"priority": "urgent"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"

    def test_change_priority_success(self, client_with_mocks, mocker):
        """发起人修改优先级 → 200"""
        mocker.patch("app.services.notification_service.send_refresh_signal", new=AsyncMock())

        client = client_with_mocks
        db = client.mock_db

        token = _make_token()

        inst = make_instance(id=1, initiator_id=1, status=InstanceStatus.RUNNING,
                             priority=Priority.NORMAL)

        db.execute = AsyncMock()
        db.execute.side_effect = [
            _user_result(),             # 0: get_current_active_user
            MockResult(scalar_one=inst),  # 1: SELECT instance
            MockResult(scalar_one=None),  # 2: template type for _get_type_label
            MagicMock(),                  # 3: INSERT operation log
        ]

        resp = client.put(
            "/api/v1/instances/1/priority",
            json={"priority": "urgent"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (200, 201), f"Expected 200/201, got {resp.status_code}: {resp.text}"


# ============================================================
# 实例详情
# ============================================================

class TestGetInstanceDetail:
    """GET /api/v1/instances/{id}"""

    def test_instance_not_found(self, client_with_mocks):
        """查询不存在的项目 → 404"""
        client = client_with_mocks
        db = client.mock_db

        token = _make_token()

        db.execute = AsyncMock()
        db.execute.side_effect = [
            _user_result(),            # 0: get_current_active_user
            MockResult(scalars_all=[]),  # 1: SELECT instance → 不存在
        ]

        resp = client.get(
            "/api/v1/instances/999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"


