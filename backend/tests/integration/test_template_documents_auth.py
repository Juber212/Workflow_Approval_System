"""P1-4 集成测试：模板文件列表接口组织隔离

GET /templates/{template_id}/documents 仅本所所长可查看，
普通用户 / 其他组织所长一律 403，防止枚举模板关联的文件模板。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_db
from app.models import FlowTemplate
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


def _make_token(user_id=1, roles=("manager",), org_id=1):
    """签发 JWT（含角色快照）"""
    from app.core.security import create_access_token
    return create_access_token({"sub": str(user_id), "username": f"u{user_id}",
                                "roles": list(roles), "org_id": org_id})


def _make_user(user_id=1, org_id=1):
    """构造当前登录用户（DB 角色来自 get_current_active_user 重查）"""
    from app.models import User
    return User(id=user_id, username=f"u{user_id}", real_name="用户", password_hash="x",
                organization_id=org_id, is_active=True)


def _make_tpl(org_id=1):
    """模板属于指定组织"""
    return FlowTemplate(id=1, name="测试模板", type="project", organization_id=org_id)


class TestTemplateDocumentsAuth:
    """模板文件列表接口 —— 组织隔离"""

    def test_regular_user_forbidden(self, client):
        """普通用户（无所长角色）→ 403"""
        db = client.mock_db
        db.execute = AsyncMock()
        db.execute.side_effect = [
            MockResult(scalar_one=_make_user()),    # 0: get_current_active_user → User
            MockResult(scalars_all=['user']),       # 1: DB 角色：普通用户
            MockResult(scalar_one=_make_tpl()),     # 2: 模板查询
        ]

        resp = client.get("/api/v1/templates/1/documents",
                          headers={"Authorization": f"Bearer {_make_token(roles=['user'])}"})
        assert resp.status_code == 403

    def test_cross_org_manager_forbidden(self, client):
        """其他组织所长 → 403（require_same_org 拒绝）"""
        db = client.mock_db
        db.execute = AsyncMock()
        db.execute.side_effect = [
            MockResult(scalar_one=_make_user(org_id=2)),  # 0: 用户属于组织 2
            MockResult(scalars_all=['manager']),          # 1: DB 角色：所长
            MockResult(scalar_one=_make_tpl(org_id=1)),   # 2: 模板属于组织 1
        ]

        resp = client.get("/api/v1/templates/1/documents",
                          headers={"Authorization": f"Bearer {_make_token(org_id=2)}"})
        assert resp.status_code == 403

    def test_same_org_manager_allowed(self, client):
        """本所所长 → 200（正常路径不被破坏）"""
        db = client.mock_db
        db.execute = AsyncMock()
        db.execute.side_effect = [
            MockResult(scalar_one=_make_user(org_id=1)),   # 0: 用户属于组织 1
            MockResult(scalars_all=['manager']),           # 1: DB 角色：所长
            MockResult(scalar_one=_make_tpl(org_id=1)),    # 2: 模板属于组织 1
            MockResult(scalars_all=[]),                    # 3: 本组织分类 → 空
            MockResult(scalars_all=[]),                    # 4: 已关联分类链接 → 空
            MockResult(scalars_all=[]),                    # 5: 已关联单个模板 → 空
            MockResult(scalars_all=[]),                    # 6: 可关联单个模板 → 空
        ]

        resp = client.get("/api/v1/templates/1/documents",
                          headers={"Authorization": f"Bearer {_make_token()}"})
        assert resp.status_code == 200
