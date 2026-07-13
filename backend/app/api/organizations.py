"""组织管理 API —— 仅系统管理员可访问"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select as sql_select

from app.core.database import get_db
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.schemas.common import ApiResponse
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationStatusUpdate,
)
from app.services.organization_service import (
    list_organizations,
    create_organization,
    update_organization,
    toggle_org_status,
)
from app.models import Organization
from app.api.deps import get_current_active_user, CurrentUser

router = APIRouter(prefix="/api/v1", tags=["组织管理"])


def _require_admin(current_user: CurrentUser):
    """权限守卫"""
    if not current_user.is_admin():
        raise AppException(ErrorCode.FORBIDDEN, "仅系统管理员可执行此操作")


@router.get("/organizations")
async def get_organizations(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    is_active: bool | None = Query(None, description="启用状态筛选"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """组织列表 —— 含所长姓名和用户数"""
    _require_admin(current_user)
    result = await list_organizations(db, page=page, page_size=page_size, is_active=is_active)
    return ApiResponse.ok(result.model_dump())


@router.post("/organizations")
async def post_organization(
    data: OrganizationCreate,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """新增组织"""
    _require_admin(current_user)
    org = await create_organization(db, data)
    await db.commit()
    return ApiResponse.ok({"id": org.id, "name": org.name}, message="组织创建成功")


@router.put("/organizations/{org_id}")
async def put_organization(
    org_id: int,
    data: OrganizationUpdate,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """编辑组织"""
    _require_admin(current_user)
    org = await update_organization(db, org_id, data)
    await db.commit()
    return ApiResponse.ok({"id": org.id, "name": org.name}, message="组织信息已更新")


@router.put("/organizations/{org_id}/status")
async def put_org_status(
    org_id: int,
    data: OrganizationStatusUpdate,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """启用/停用组织"""
    _require_admin(current_user)
    await toggle_org_status(db, org_id, data.is_active)
    await db.commit()
    return ApiResponse.ok(message="已启用" if data.is_active else "已停用")


@router.get("/organizations/options")
async def get_org_options(
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """组织下拉选项（仅启用状态）"""
    stmt = sql_select(Organization).where(Organization.is_active == True).order_by(Organization.id)
    result = await db.execute(stmt)
    orgs = result.scalars().all()
    return ApiResponse.ok([{"id": o.id, "name": o.name, "is_active": o.is_active} for o in orgs])
