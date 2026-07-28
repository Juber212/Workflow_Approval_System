"""批准 API 集成测试 —— 列表/详情/通过/驳回

使用 FastAPI TestClient + mock 依赖注入
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_active_user, get_db
from app.models import User
from tests.conftest import MockResult


@pytest.fixture
def client():
    """TestClient + mock get_db + mock user"""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.mock_db = mock_db
    yield c
    app.dependency_overrides.clear()


def _auth_user(user_id=1, role="manager", org_id=1):
    """注入已认证用户依赖"""
    from app.api.deps import CurrentUser
    user = CurrentUser({"sub": str(user_id), "username": f"user{user_id}",
                       "roles": [role], "org_id": org_id})
    app.dependency_overrides[get_current_active_user] = lambda: user
    return user


class TestEndorsementList:
    """批准列表测试"""

    def test_list_requires_auth(self, client):
        """未登录 → 401 or 403 or 422"""
        resp = client.get("/api/v1/endorsements")
        assert resp.status_code in (401, 403, 422)

    def test_list_empty(self, client):
        """已登录但无数据 → 200（列表 API 可达）"""
        _auth_user()
        # list_endorsements: 1) proposal template IDs, 2) count, 3) data
        client.mock_db.execute = AsyncMock()
        client.mock_db.execute.side_effect = [
            MockResult(scalars_all=[]),        # proposal template IDs query
            MockResult(scalar_value=0),        # count
            MockResult(rows_all=[]),            # data rows
        ]

        resp = client.get("/api/v1/endorsements")
        assert resp.status_code == 200

        app.dependency_overrides.pop(get_current_active_user, None)


class TestEndorsementDetail:
    """批准详情测试"""

    def test_detail_not_found(self, client):
        """不存在的记录 → 404"""
        _auth_user()
        client.mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=None))

        resp = client.get("/api/v1/endorsements/99999")
        assert resp.status_code == 404

        app.dependency_overrides.pop(get_current_active_user, None)


class TestEndorseAction:
    """批准操作测试"""

    def test_endorse_not_found(self, client):
        """批准不存在的记录 → 404"""
        _auth_user()
        client.mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=None))

        resp = client.post("/api/v1/endorsements/99999/approve", json={"opinion": "同意"})
        assert resp.status_code == 404

        app.dependency_overrides.pop(get_current_active_user, None)
