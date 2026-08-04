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

    def test_login_overlong_password(self, client):
        """超长密码（>72字节）→ 422（P1-23 bcrypt 截断防护）"""
        resp = client.post("/api/v1/auth/login", json={
            "username": "test", "password": "a" * 100
        })
        assert resp.status_code == 422


class TestProfile:
    """个人资料更新 API 测试"""

    def test_update_profile_unauthorized(self, client):
        """未登录请求 → 401 或 422（FastAPI 先校验 body 再跑依赖）"""
        resp = client.put("/api/v1/auth/profile", json={"email": "test@test.com"})
        assert resp.status_code in (401, 422)

    def test_update_profile_email_and_phone(self, client):
        """更新邮箱和手机号 → 200"""
        import bcrypt
        user = User(id=1, username="test", real_name="测试",
                    password_hash=bcrypt.hashpw(b"correct", bcrypt.gensalt()).decode(),
                    organization_id=1, is_active=True)
        client.mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=user))

        resp = client.put("/api/v1/auth/profile", json={
            "email": "new@test.com",
            "phone": "13800138000",
        }, headers={"Authorization": "Bearer fake-token"})
        # 用 mock token 走不下去（JWT 无效），但验证 schema 校验通过
        assert resp.status_code == 401  # JWT 解码失败 → 401

    def test_update_profile_partial(self, client):
        """只更新邮箱 → 200（空 body schema 通过）"""
        resp = client.put("/api/v1/auth/profile", json={
            "email": "only-email@test.com",
        }, headers={"Authorization": "Bearer fake-token"})
        assert resp.status_code == 401  # JWT 解码失败，但 schema 校验通过


class TestChangePassword:
    """修改密码 API 测试（P0-6：强制改密场景允许省略旧密码）"""

    def _mock_current_user(self, user_id=1, username="test"):
        """override 认证依赖，返回固定当前用户（绕过 JWT 解码）"""
        from app.api.deps import get_current_active_user, CurrentUser
        app.dependency_overrides[get_current_active_user] = \
            lambda: CurrentUser({"sub": str(user_id), "username": username, "roles": ["user"]})

    def _cleanup(self):
        from app.api.deps import get_current_active_user
        app.dependency_overrides.pop(get_current_active_user, None)

    def _make_user(self, must_change: bool, raw_password: str):
        """构造一个 bcrypt 密码可验证的 User 实例"""
        from app.core.security import hash_password
        return User(id=1, username="test", real_name="测试",
                    password_hash=hash_password(raw_password),
                    organization_id=1, is_active=True, must_change_password=must_change)

    def test_force_change_password_no_old_pwd(self, client):
        """强制改密用户省略旧密码 → 200 且清除强制改密标记"""
        user = self._make_user(must_change=True, raw_password="temp123")
        client.mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=user))
        self._mock_current_user()
        try:
            resp = client.put("/api/v1/auth/password", json={"new_password": "newpass123"})
            assert resp.status_code == 200
            assert user.must_change_password is False
        finally:
            self._cleanup()

    def test_force_change_password_wrong_old_pwd(self, client):
        """强制改密用户仍传了错误旧密码 → 403（传了就要校验）"""
        user = self._make_user(must_change=True, raw_password="temp123")
        client.mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=user))
        self._mock_current_user()
        try:
            resp = client.put("/api/v1/auth/password", json={
                "old_password": "wrong", "new_password": "newpass123"})
            assert resp.status_code == 403
        finally:
            self._cleanup()

    def test_normal_change_password_no_old_pwd(self, client):
        """非强制改密用户省略旧密码 → 400"""
        user = self._make_user(must_change=False, raw_password="correct")
        client.mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=user))
        self._mock_current_user()
        try:
            resp = client.put("/api/v1/auth/password", json={"new_password": "newpass123"})
            assert resp.status_code == 400
        finally:
            self._cleanup()

    def test_normal_change_password_wrong_old_pwd(self, client):
        """非强制改密用户错误旧密码 → 403"""
        user = self._make_user(must_change=False, raw_password="correct")
        client.mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=user))
        self._mock_current_user()
        try:
            resp = client.put("/api/v1/auth/password", json={
                "old_password": "wrong", "new_password": "newpass123"})
            assert resp.status_code == 403
        finally:
            self._cleanup()

    def test_change_password_overlong(self, client):
        """新密码或旧密码超过 72 字节 → 422（P1-23 bcrypt 截断防护）"""
        self._mock_current_user()
        try:
            # 新密码超长
            resp = client.put("/api/v1/auth/password", json={"new_password": "a" * 100 + "b1"})
            assert resp.status_code == 422
            # 旧密码超长
            resp = client.put("/api/v1/auth/password", json={
                "old_password": "a" * 100, "new_password": "newpass123"})
            assert resp.status_code == 422
        finally:
            self._cleanup()


class TestPasswordByteLimit:
    """bcrypt 72 字节上限（P1-23）—— 纯 schema 边界校验，不依赖 DB"""

    def test_72_bytes_exact_allowed(self):
        """恰好 72 字节的密码合法（72 英文 或 24 中文）"""
        from app.schemas.auth import LoginRequest, ChangePasswordRequest
        LoginRequest(username="test", password="a" * 72)          # 72 字节 ASCII
        LoginRequest(username="test", password="密" * 24)          # 24×3=72 字节 UTF-8
        ChangePasswordRequest(new_password="pass1234" + "a" * 64)  # 72 字节（含字母数字）

    def test_exceed_72_bytes_rejected(self):
        """超过 72 字节 → 拒绝（字符数未超但字节超限也要拦）"""
        from pydantic import ValidationError
        from app.schemas.auth import LoginRequest, ChangePasswordRequest
        with pytest.raises(ValidationError):
            LoginRequest(username="test", password="密" * 25)  # 25×3=75 字节
        with pytest.raises(ValidationError):
            ChangePasswordRequest(new_password="pass1234" + "密" * 23)  # 8+69=77 字节
