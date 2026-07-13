"""角色管理 API —— 仅系统管理员可访问（V1 只读）"""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.schemas.common import ApiResponse
from app.schemas.role import RoleListItem
from app.models import Role, UserRole
from app.api.deps import get_current_active_user, CurrentUser

router = APIRouter(prefix="/api/v1", tags=["角色管理"])


def _require_admin(current_user: CurrentUser):
    if not current_user.is_admin():
        raise AppException(ErrorCode.FORBIDDEN, "仅系统管理员可执行此操作")


@router.get("/roles")
async def get_roles(
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """角色列表 —— 含 user_count 计算字段（V1 仅查看）"""
    _require_admin(current_user)

    # 查询角色
    result = await db.execute(select(Role).order_by(Role.id))
    roles = result.scalars().all()

    # 批量计算 user_count
    role_ids = [r.id for r in roles]
    count_stmt = (
        select(UserRole.role_id, func.count(UserRole.user_id))
        .where(UserRole.role_id.in_(role_ids))
        .group_by(UserRole.role_id)
    )
    count_rows = (await db.execute(count_stmt)).all()
    count_map = {role_id: cnt for role_id, cnt in count_rows}

    items = [
        RoleListItem(
            id=r.id,
            name=r.name,
            code=r.code,
            description=r.description,
            user_count=count_map.get(r.id, 0),
        )
        for r in roles
    ]

    return ApiResponse.ok([item.model_dump() for item in items])
