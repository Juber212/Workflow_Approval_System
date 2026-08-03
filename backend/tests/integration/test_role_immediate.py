"""角色降级即时生效集成测试 —— 旧 token 携带旧角色，但 DB 已变更则按 DB 角色判定（P0-9）"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_db
from app.models import User
from tests.conftest import MockResult


@pytest.fixture
def client():
    """TestClient + mock get_db（非 with 模式，避免 lifespan 触发全局 DB）"""
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


class TestRoleImmediateEffect:
    """角色变更即时生效"""

    def test_demoted_admin_old_token_forbidden(self, client):
        """JWT 含 system_admin 但 DB 角色已降级为 user → GET /users 返回 403"""
        from app.core.security import create_access_token

        # DB 中的用户：已降级为普通 user
        user = User(id=1, username="admin", real_name="管理员", password_hash="x",
                    organization_id=None, is_active=True)
        client.mock_db.execute = AsyncMock()
        client.mock_db.execute.side_effect = [
            MockResult(scalar_one=user),       # get_current_active_user → User
            MockResult(scalars_all=['user']),  # DB 角色：已降级
        ]
        # 旧 token：签发时还是 system_admin
        token = create_access_token({"sub": "1", "username": "admin", "roles": ["system_admin"], "org_id": None})

        resp = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})

        assert resp.status_code == 403

    def test_normal_admin_old_token_allowed(self, client):
        """未降级：DB 角色仍为 system_admin → GET /users 正常（验证 mock 链正确性）"""
        from app.core.security import create_access_token

        user = User(id=1, username="admin", real_name="管理员", password_hash="x",
                    organization_id=None, is_active=True)
        # 管理员列表查询的 execute 链：User → 角色 → 列表数据（3 个用户）等
        client.mock_db.execute = AsyncMock()
        client.mock_db.execute.side_effect = [
            MockResult(scalar_one=user),             # get_current_active_user → User
            MockResult(scalars_all=["system_admin"]),# DB 角色：仍为管理员
            MockResult(scalar_value=0),              # 总数
            MockResult(rows_all=[]),                 # 用户列表行
        ]
        token = create_access_token({"sub": "1", "username": "admin", "roles": ["system_admin"], "org_id": None})

        resp = client.get("/api/v1/users?page=1&page_size=10", headers={"Authorization": f"Bearer {token}"})

        assert resp.status_code == 200
