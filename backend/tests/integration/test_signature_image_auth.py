"""P1-6 集成测试：签名图片接口仅本人可访问

GET /auth/users/{user_id}/signature-image 返回个人笔迹签名素材。
四个详情接口均「仅操作人本人可查看」，前端加载签名预览的场景全是本人看自己，
故接口只放行本人，他人一律 403，防止枚举抓取任意用户签名。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_active_user, CurrentUser, get_db
from app.models import User
from tests.conftest import MockResult


@pytest.fixture
def client():
    """TestClient + mock get_db（非 with 模式）"""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.mock_db = mock_db
    yield c
    app.dependency_overrides.clear()


def _override_user(user_id=1, roles=("user",)):
    """覆盖认证依赖，直接返回指定用户身份"""
    app.dependency_overrides[get_current_active_user] = lambda: CurrentUser(
        {"sub": str(user_id), "username": f"u{user_id}", "roles": list(roles),
         "org_id": 1, "jti": "t", "iat": 1}
    )


def _cleanup_user():
    app.dependency_overrides.pop(get_current_active_user, None)


def _make_user(user_id=1, signature_path="/tmp/sig.png"):
    """构造带签名路径的用户"""
    return User(id=user_id, username=f"u{user_id}", real_name="用户",
                password_hash="x", organization_id=1, is_active=True,
                signature_image=signature_path)


class TestSignatureImageAuth:
    """签名图片接口 —— 仅本人可访问"""

    def test_self_allowed(self, client, tmp_path):
        """本人查看自己的签名 → 200"""
        # 创建真实文件供 FileResponse 读取
        sig_file = tmp_path / "sig.png"
        sig_file.write_bytes(b"fake-png-bytes")
        _override_user(user_id=1)
        client.mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=_make_user(1, str(sig_file))))
        try:
            resp = client.get("/api/v1/auth/users/1/signature-image")
            assert resp.status_code == 200
            assert resp.content == b"fake-png-bytes"
        finally:
            _cleanup_user()

    def test_other_user_forbidden(self, client):
        """他人查看非本人签名 → 403（不查 DB，直接拦截）"""
        _override_user(user_id=1)
        try:
            resp = client.get("/api/v1/auth/users/2/signature-image")
            assert resp.status_code == 403
        finally:
            _cleanup_user()

    def test_unauthenticated_rejected(self, client):
        """未登录（无 Authorization）→ 不可访问

        当前缺 header 时 FastAPI 返回 422（必填 Header 校验，P1-24 待修为 401），
        重点断言「未登录拿不到签名图」。
        """
        resp = client.get("/api/v1/auth/users/1/signature-image")
        assert resp.status_code != 200

    def test_invalid_token_rejected(self, client):
        """携带无效 token → 401"""
        resp = client.get(
            "/api/v1/auth/users/1/signature-image",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401
