"""P1-5 集成测试：改密/重置密码后按密码版本号吊销旧 token

覆盖：
1. TokenBlacklistMiddleware 密码版本号校验 —— token.iat 早于版本号 → 401
2. 改密成功后重新签发 token —— 当前会话无缝续期，旧 token 全部失效
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_active_user, CurrentUser, get_db
from app.core.security import create_access_token, decode_access_token, hash_password
from app.models import User
from tests.conftest import MockResult


@pytest.fixture
def client():
    """TestClient + mock get_db（非 with 模式，避免 lifespan 触发全局 DB）"""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()
    _nested_ctx = MagicMock()
    _nested_ctx.__aenter__ = AsyncMock()
    _nested_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_db.begin_nested = MagicMock(return_value=_nested_ctx)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.mock_db = mock_db
    yield c
    app.dependency_overrides.clear()


def _make_token(user_id=1):
    """签发真实 JWT（含 iat/jti）"""
    return create_access_token({"sub": str(user_id), "username": f"u{user_id}",
                                "roles": ["user"], "org_id": 1})


def _make_current_user(user_id=1, username="test"):
    """构造当前用户（绕过 JWT 解码与角色重查）"""
    return CurrentUser({"sub": str(user_id), "username": username,
                        "roles": ["user"], "org_id": 1,
                        "jti": "test-jti", "iat": 1_700_000_000})


def _make_user(must_change=False):
    """构造 DB 用户（bcrypt 密码可验证）"""
    return User(id=1, username="test", real_name="测试",
                password_hash=hash_password("oldpass123"),
                organization_id=1, is_active=True, must_change_password=must_change)


class TestPasswordVersionMiddleware:
    """TokenBlacklistMiddleware 密码版本号校验"""

    def _override_user(self):
        app.dependency_overrides[get_current_active_user] = lambda: _make_current_user()

    def _cleanup(self):
        app.dependency_overrides.pop(get_current_active_user, None)

    def test_old_token_rejected_after_password_change(self, client):
        """改密时间戳 > token.iat → 401（改密前签发的旧 token 被吊销）"""
        self._override_user()
        try:
            with patch("app.core.token_blacklist.get_password_version",
                       new=AsyncMock(return_value=2_000_000_000)):
                resp = client.get("/api/v1/auth/me",
                                  headers={"Authorization": f"Bearer {_make_token()}"})
            assert resp.status_code == 401
        finally:
            self._cleanup()

    def test_new_token_allowed_after_password_change(self, client):
        """改密时间戳 < token.iat → 放行（改密后重新签发的 token 有效）"""
        self._override_user()
        client.mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=_make_user()))
        try:
            with patch("app.core.token_blacklist.get_password_version",
                       new=AsyncMock(return_value=1)):
                resp = client.get("/api/v1/auth/me",
                                  headers={"Authorization": f"Bearer {_make_token()}"})
            assert resp.status_code == 200
        finally:
            self._cleanup()

    def test_no_version_allowed(self, client):
        """从未改密/重置 → 无版本号 → 放行（不误伤正常用户）"""
        self._override_user()
        client.mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=_make_user()))
        try:
            with patch("app.core.token_blacklist.get_password_version",
                       new=AsyncMock(return_value=None)):
                resp = client.get("/api/v1/auth/me",
                                  headers={"Authorization": f"Bearer {_make_token()}"})
            assert resp.status_code == 200
        finally:
            self._cleanup()


class TestChangePasswordReissueToken:
    """改密成功后记录版本号 + 重新签发 token（P1-5）"""

    def _override_user(self):
        app.dependency_overrides[get_current_active_user] = lambda: _make_current_user()

    def _cleanup(self):
        app.dependency_overrides.pop(get_current_active_user, None)

    def test_change_password_reissues_token(self, client):
        """改密成功 → 记录密码版本号 + 返回重新签发的新 token"""
        client.mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=_make_user()))
        self._override_user()
        try:
            with patch("app.core.token_blacklist.set_password_version",
                       new=AsyncMock()) as mock_set_version:
                resp = client.put("/api/v1/auth/password",
                                  headers={"Authorization": f"Bearer {_make_token()}"},
                                  json={"old_password": "oldpass123", "new_password": "newpass123"})
        finally:
            self._cleanup()

        assert resp.status_code == 200
        data = resp.json()["data"]
        # 返回了重新签发的新 token，且属于同一用户
        assert data["token"]
        payload = decode_access_token(data["token"])
        assert payload is not None
        assert payload["sub"] == "1"
        assert payload["iat"] > 1_700_000_000  # 改密后重新签发的时间戳
        # 密码版本号已更新（用于吊销该用户所有旧 token）
        mock_set_version.assert_awaited_once_with(1)
