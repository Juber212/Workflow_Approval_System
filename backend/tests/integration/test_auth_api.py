"""认证 API 集成测试 —— 登录/Token刷新/健康检查

使用 FastAPI TestClient + mock 依赖注入
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_db
from app.models import User
from tests.conftest import MockResult


@pytest.fixture
def client():
    """TestClient + mock get_db"""
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


class TestHealth:
    """健康检查测试"""

    def test_health_check(self, client):
        """健康检查 → 200"""
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200


class TestLogin:
    """登录 API 测试"""

    def test_login_empty_body(self, client):
        """空请求体 → 422"""
        resp = client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422

    def test_login_user_not_found(self, client):
        """用户不存在 → 401"""
        client.mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=None))

        resp = client.post("/api/v1/auth/login", json={
            "username": "nonexistent", "password": "wrong"
        })
        assert resp.status_code in (401, 403)

    def test_login_wrong_password(self, client):
        """密码错误 → 401"""
        import bcrypt
        user = User(id=1, username="test", real_name="测试",
                    password_hash=bcrypt.hashpw(b"correct", bcrypt.gensalt()).decode(),
                    organization_id=1, is_active=True)
        client.mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=user))

        resp = client.post("/api/v1/auth/login", json={
            "username": "test", "password": "wrongpassword"
        })
        assert resp.status_code == 401
