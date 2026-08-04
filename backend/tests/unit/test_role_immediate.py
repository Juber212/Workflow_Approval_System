"""get_current_active_user 单测 —— DB 实时角色覆盖 JWT 快照（P0-9 角色变更即时生效）"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.api.deps import get_current_active_user, CurrentUser
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import User
from tests.conftest import MockResult


def _make_request(path="/api/v1/instances"):
    """构造 mock Request（get_current_active_user 签名含 request 参数，P1-28）"""
    req = MagicMock()
    req.url.path = path
    return req


def _make_user(is_active=True):
    return User(id=1, username="m", real_name="测试用户", password_hash="x",
                organization_id=1, is_active=is_active)


def _make_current_user(roles):
    return CurrentUser({"sub": "1", "username": "m", "roles": roles, "org_id": 1})


class TestGetCurrentActiveUserRoles:
    """角色实时性：DB 角色为权威，覆盖 JWT 签发时的角色快照"""

    @pytest.mark.asyncio
    async def test_db_roles_override_jwt_on_demotion(self, mock_db):
        """manager 降级为 user：DB 角色 ['user'] 覆盖 JWT 的 ['manager']"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=_make_user()),   # User 查询
            MockResult(scalars_all=['user']),      # DB 角色查询
        ]
        result = await get_current_active_user(_make_request(), _make_current_user(["manager"]), mock_db)
        assert result.roles == ["user"]

    @pytest.mark.asyncio
    async def test_db_roles_override_jwt_on_promotion(self, mock_db):
        """user 升为 manager：DB 角色 ['manager'] 覆盖 JWT 的 ['user']"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=_make_user()),
            MockResult(scalars_all=["manager"]),
        ]
        result = await get_current_active_user(_make_request(), _make_current_user(["user"]), mock_db)
        assert result.roles == ["manager"]

    @pytest.mark.asyncio
    async def test_empty_db_roles_keep_jwt_snapshot(self, mock_db):
        """DB 角色为空时保留 JWT 快照（兼容无角色用户与测试 mock，避免误清空）"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=_make_user()),
            MockResult(scalars_all=[]),            # 角色查询返回空
        ]
        result = await get_current_active_user(_make_request(), _make_current_user(["manager"]), mock_db)
        assert result.roles == ["manager"]

    @pytest.mark.asyncio
    async def test_disabled_user_rejected(self, mock_db):
        """禁用用户 → 403"""
        mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=_make_user(is_active=False)))
        with pytest.raises(AppException) as exc:
            await get_current_active_user(_make_request(), _make_current_user(["user"]), mock_db)
        assert exc.value.code == ErrorCode.FORBIDDEN
