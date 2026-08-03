"""user_service 单元测试 —— 列表/创建/更新/启停/重置密码"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import User, Organization, Role, UserRole
from app.services.user_service import (
    list_users, create_user, update_user, toggle_user_status, reset_user_password,
)
from tests.conftest import MockResult


# ============================================================
# 用户列表
# ============================================================

class TestListUsers:
    """list_users —— 分页 + 筛选 + 角色批量查询"""

    @pytest.mark.asyncio
    async def test_returns_data(self, mock_db):
        """有用户 → 返回列表含角色"""
        org = Organization(id=1, name="测试所")
        user = User(
            id=1, username="zhangsan", real_name="张三",
            password_hash="x", organization_id=1, is_active=True,
            created_at=datetime.now(),
        )
        user.organization = org  # joinedload 预加载

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_value=1),                        # 0: count
            MockResult(scalars_all=[user]),                     # 1: users (含 joinedload)
            MockResult(rows_all=[(1, "manager"), (1, "user")]), # 2: batch roles
        ]

        result = await list_users(mock_db)
        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].id == 1
        assert result.items[0].username == "zhangsan"
        assert result.items[0].real_name == "张三"
        assert result.items[0].organization_name == "测试所"
        assert "manager" in result.items[0].roles
        assert "user" in result.items[0].roles

    @pytest.mark.asyncio
    async def test_empty(self, mock_db):
        """无用户 → 空列表"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_value=0),       # 0: count
            MockResult(scalars_all=[]),       # 1: users → 空
        ]

        result = await list_users(mock_db)
        assert result.total == 0
        assert result.items == []


# ============================================================
# 创建用户
# ============================================================

class TestCreateUser:
    """create_user —— 用户名唯一性 + 组织/角色校验"""

    @pytest.mark.asyncio
    async def test_username_conflict(self, mock_db):
        """用户名已存在 → 409"""
        existing = User(id=1, username="admin", real_name="管理员")

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=existing),  # 0: 用户名查重 → 已存在
        ]

        from app.schemas.user import UserCreate
        data = UserCreate(
            username="admin", real_name="管理员", password="123456",
            organization_id=1, role_id=1,
        )

        with pytest.raises(AppException) as exc:
            await create_user(mock_db, data)
        assert exc.value.code == ErrorCode.CONFLICT

    @pytest.mark.asyncio
    async def test_org_not_found(self, mock_db):
        """组织不存在 → 404（非管理员角色，org 必填）"""
        mock_role = Role(id=1, code="user", name="普通用户")
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=None),                 # 0: 用户名查重 → 无
            MockResult(scalar_one=mock_role),            # 1: 角色查询 → 非管理员角色
            MockResult(scalar_one=None),                 # 2: 组织查询 → 不存在
        ]

        from app.schemas.user import UserCreate
        data = UserCreate(
            username="newuser", real_name="新用户",
            organization_id=999, role_id=1,
        )

        with pytest.raises(AppException) as exc:
            await create_user(mock_db, data)
        assert exc.value.code == ErrorCode.NOT_FOUND


# ============================================================
# 更新用户
# ============================================================

class TestUpdateUser:
    """update_user —— 组织/角色校验 + 角色替换"""

    @pytest.mark.asyncio
    async def test_user_not_found(self, mock_db):
        """用户不存在 → 404"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=None),  # 0: 查找用户 → 不存在
        ]

        from app.schemas.user import UserUpdate
        data = UserUpdate(real_name="x", organization_id=1, role_id=1)

        with pytest.raises(AppException) as exc:
            await update_user(mock_db, user_id=999, data=data)
        assert exc.value.code == ErrorCode.NOT_FOUND

    @pytest.mark.asyncio
    async def test_org_not_found(self, mock_db):
        """目标组织不存在 → 404（非管理员角色，org 必填）"""
        user = User(id=1, username="test", real_name="测试", password_hash="x",
                    organization_id=1, is_active=True)
        mock_role = Role(id=1, code="user", name="普通用户")

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=user),               # 0: 查找用户 → 存在
            MockResult(scalar_one=mock_role),          # 1: 角色查询 → 非管理员角色
            MockResult(scalar_one=None),               # 2: 组织查询 → 不存在
        ]

        from app.schemas.user import UserUpdate
        data = UserUpdate(real_name="x", organization_id=999, role_id=1)

        with pytest.raises(AppException) as exc:
            await update_user(mock_db, user_id=1, data=data)
        assert exc.value.code == ErrorCode.NOT_FOUND


# ============================================================
# 启停用户
# ============================================================

class TestToggleUserStatus:
    """toggle_user_status —— 启用/禁用"""

    @pytest.mark.asyncio
    async def test_not_found(self, mock_db):
        """用户不存在 → 404"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=None),  # 0: 查找用户 → 不存在
        ]

        with pytest.raises(AppException) as exc:
            await toggle_user_status(mock_db, user_id=999, is_active=False)
        assert exc.value.code == ErrorCode.NOT_FOUND


# ============================================================
# 重置密码
# ============================================================

class TestResetUserPassword:
    """reset_user_password —— 管理员重置"""

    @pytest.mark.asyncio
    async def test_not_found(self, mock_db):
        """用户不存在 → 404"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=None),  # 0: 查找用户 → 不存在
        ]

        with pytest.raises(AppException) as exc:
            await reset_user_password(mock_db, user_id=999)
        assert exc.value.code == ErrorCode.NOT_FOUND
