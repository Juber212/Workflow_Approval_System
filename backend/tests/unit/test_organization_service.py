"""organization_service 单元测试 —— 列表/创建/更新/启停"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import Organization, User, UserRole, Role
from app.services.organization_service import (
    list_organizations, create_organization, update_organization, toggle_org_status,
)
from tests.conftest import MockResult


# ============================================================
# 组织列表
# ============================================================

class TestListOrganizations:
    """list_organizations —— 分页列表 + 用户数 + 所长"""

    @pytest.mark.asyncio
    async def test_returns_data(self, mock_db):
        """有组织 → 返回列表含 user_count 和 manager_name"""
        org = Organization(id=1, name="测试所", description="测试", is_active=True,
                          created_at=datetime.now())

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_value=1),             # 0: count
            MockResult(scalars_all=[org]),           # 1: orgs
            MockResult(rows_all=[(1, 5)]),           # 2: user_count
            MockResult(rows_all=[(1, "张所长")]),    # 3: managers
        ]

        result = await list_organizations(mock_db)
        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].id == 1
        assert result.items[0].name == "测试所"
        assert result.items[0].user_count == 5
        assert result.items[0].manager_name == "张所长"

    @pytest.mark.asyncio
    async def test_empty(self, mock_db):
        """无组织 → 空列表"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_value=0),    # 0: count
            MockResult(scalars_all=[]),    # 1: orgs → 空 → 提前返回
        ]

        result = await list_organizations(mock_db)
        assert result.total == 0
        assert result.items == []


# ============================================================
# 创建组织
# ============================================================

class TestCreateOrganization:
    """create_organization —— 名称唯一性校验"""

    @pytest.mark.asyncio
    async def test_success(self, mock_db):
        """无重名 → 创建成功"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=None),  # 0: 名称查重 → 无重复
        ]
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        from app.schemas.organization import OrganizationCreate
        data = OrganizationCreate(name="新所", description="测试")

        result = await create_organization(mock_db, data)
        assert result is not None
        assert result.name == "新所"
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_name_conflict(self, mock_db):
        """重名 → 409"""
        existing_org = Organization(id=1, name="已存在", is_active=True)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=existing_org),  # 0: 名称查重 → 已存在
        ]

        from app.schemas.organization import OrganizationCreate
        data = OrganizationCreate(name="已存在")

        with pytest.raises(AppException) as exc:
            await create_organization(mock_db, data)
        assert exc.value.code == ErrorCode.CONFLICT


# ============================================================
# 更新组织
# ============================================================

class TestUpdateOrganization:
    """update_organization —— 校验存在 + 名称唯一性（排除自身）"""

    @pytest.mark.asyncio
    async def test_success(self, mock_db):
        """正常更新 → 返回更新后的组织"""
        org = Organization(id=1, name="旧名称", description="旧描述", is_active=True)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=org),       # 0: 查找组织 → 存在
            MockResult(scalar_one=None),       # 1: 名称唯一性 → 无重复
        ]
        mock_db.flush = AsyncMock()

        from app.schemas.organization import OrganizationUpdate
        data = OrganizationUpdate(name="新名称", description="新描述")

        result = await update_organization(mock_db, org_id=1, data=data)
        assert result is not None
        assert result.name == "新名称"

    @pytest.mark.asyncio
    async def test_not_found(self, mock_db):
        """组织不存在 → 404"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=None),  # 0: 查找组织 → 不存在
        ]

        from app.schemas.organization import OrganizationUpdate
        data = OrganizationUpdate(name="不存在", description="x")

        with pytest.raises(AppException) as exc:
            await update_organization(mock_db, org_id=999, data=data)
        assert exc.value.code == ErrorCode.NOT_FOUND

    @pytest.mark.asyncio
    async def test_name_conflict(self, mock_db):
        """重名（排除自身后仍存在）→ 409"""
        org = Organization(id=1, name="旧名称", is_active=True)
        conflict_org = Organization(id=2, name="冲突名称", is_active=True)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=org),            # 0: 查找组织 → 存在
            MockResult(scalar_one=conflict_org),   # 1: 名称唯一性 → 冲突
        ]

        from app.schemas.organization import OrganizationUpdate
        data = OrganizationUpdate(name="冲突名称")

        with pytest.raises(AppException) as exc:
            await update_organization(mock_db, org_id=1, data=data)
        assert exc.value.code == ErrorCode.CONFLICT


# ============================================================
# 启停组织
# ============================================================

class TestToggleOrgStatus:
    """toggle_org_status —— 启用/停用"""

    @pytest.mark.asyncio
    async def test_not_found(self, mock_db):
        """组织不存在 → 404"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=None),  # 0: 查找组织 → 不存在
        ]

        with pytest.raises(AppException) as exc:
            await toggle_org_status(mock_db, org_id=999, is_active=False)
        assert exc.value.code == ErrorCode.NOT_FOUND
