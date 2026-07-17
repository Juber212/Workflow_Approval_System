"""用户管理 API —— 仅系统管理员可访问"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.schemas.common import ApiResponse
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserStatusUpdate,
    ResetPasswordRequest,
)
from app.services.user_service import (
    list_users,
    create_user,
    update_user,
    toggle_user_status,
    reset_user_password,
)
from app.api.deps import get_current_active_user, CurrentUser, require_admin

router = APIRouter(prefix="/api/v1", tags=["用户管理"])


@router.get("/users")
async def get_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: str | None = Query(None, description="搜索关键词（用户名/姓名）"),
    organization_id: int | None = Query(None, description="组织筛选"),
    is_active: bool | None = Query(None, description="启用状态筛选"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """用户列表（分页+搜索+筛选）—— 仅系统管理员"""
    require_admin(current_user)

    result = await list_users(
        db,
        page=page,
        page_size=page_size,
        keyword=keyword,
        organization_id=organization_id,
        is_active=is_active,
    )
    return ApiResponse.ok(result.model_dump())


@router.post("/users")
async def post_users(
    data: UserCreate,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """新增用户 —— 仅系统管理员"""
    require_admin(current_user)

    user = await create_user(db, data)
    await db.commit()
    return ApiResponse.ok(user.model_dump(), message="用户创建成功")


@router.put("/users/{user_id}")
async def put_user(
    user_id: int,
    data: UserUpdate,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """编辑用户（不可改用户名）—— 仅系统管理员"""
    require_admin(current_user)

    user = await update_user(db, user_id, data)
    await db.commit()
    return ApiResponse.ok(user.model_dump(), message="用户信息已更新")


@router.put("/users/{user_id}/status")
async def put_user_status(
    user_id: int,
    data: UserStatusUpdate,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """启用/禁用用户 —— 仅系统管理员"""
    require_admin(current_user)

    await toggle_user_status(db, user_id, data.is_active)
    await db.commit()
    return ApiResponse.ok(message="已启用" if data.is_active else "已禁用")


@router.put("/users/{user_id}/reset-password")
async def put_user_reset_password(
    user_id: int,
    data: ResetPasswordRequest,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员重置用户密码 —— 仅系统管理员"""
    require_admin(current_user)

    await reset_user_password(db, user_id, data.new_password)
    await db.commit()
    return ApiResponse.ok(message="密码已重置")


@router.get("/users/search")
async def search_users(
    keyword: str | None = Query(None, description="搜索关键词（姓名/用户名），为空时配合 organization_id 可拉取组织全部成员"),
    organization_id: int | None = Query(None, description="按组织筛选，为空且无 keyword 时返回空"),
    limit: int = Query(100, ge=1, le=200, description="返回数量上限"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """用户搜索 —— 支持三种模式：

    1. 仅 keyword → 全局搜索（现有行为）
    2. 仅 organization_id → 返回该组织全部活跃用户
    3. keyword + organization_id → 在该组织内搜索
    """
    from sqlalchemy import select as sql_select, or_ as sql_or
    from app.models import User, Organization

    conditions = [User.is_active == True]

    if organization_id:
        conditions.append(User.organization_id == organization_id)

    if keyword:
        like = f"%{keyword}%"
        conditions.append(sql_or(User.real_name.like(like), User.username.like(like)))

    stmt = (
        sql_select(User)
        .options(joinedload(User.organization))
        .where(*conditions)
        .order_by(User.real_name)
        .limit(limit)
    )
    result = await db.execute(stmt)
    users = result.unique().scalars().all()
    return ApiResponse.ok([
        {
            "id": u.id,
            "username": u.username,
            "real_name": u.real_name,
            "organization_id": u.organization_id,
            "organization_name": u.organization.name if u.organization else None,
        }
        for u in users
    ])


# ==================== 辅助选项接口 ====================


@router.get("/roles/options")
async def get_role_options(
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取角色下拉选项（所有角色）"""
    from sqlalchemy import select as sql_select
    from app.models import Role

    stmt = sql_select(Role).order_by(Role.id)
    result = await db.execute(stmt)
    roles = result.scalars().all()
    return ApiResponse.ok([{"id": r.id, "code": r.code, "name": r.name} for r in roles])
