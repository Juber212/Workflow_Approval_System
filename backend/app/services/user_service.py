"""用户管理业务逻辑 —— 列表/新增/编辑/启禁用/重置密码"""
import re

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.security import hash_password
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import User, UserRole, Role, Organization
from app.schemas.common import PaginatedData
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserListItem,
    UserDetail,
)


async def list_users(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    organization_id: int | None = None,
    is_active: bool | None = None,
) -> PaginatedData:
    """分页查询用户列表，支持关键词/组织/启用状态筛选"""

    # 构建查询条件
    conditions = []
    if keyword:
        keyword_like = f"%{keyword}%"
        conditions.append(
            or_(
                User.username.like(keyword_like),
                User.real_name.like(keyword_like),
            )
        )
    if organization_id is not None:
        conditions.append(User.organization_id == organization_id)
    if is_active is not None:
        conditions.append(User.is_active == is_active)

    where_clause = and_(*conditions) if conditions else None

    # 总数
    count_stmt = select(func.count()).select_from(User)
    if where_clause is not None:
        count_stmt = count_stmt.where(where_clause)
    total = (await db.execute(count_stmt)).scalar() or 0

    # 分页数据（含组织名和角色）
    stmt = (
        select(User)
        .options(joinedload(User.organization))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .order_by(User.id.desc())
    )
    if where_clause is not None:
        stmt = stmt.where(where_clause)

    result = await db.execute(stmt)
    users = result.unique().scalars().all()

    # 批量查询所有用户的角色
    user_ids = [u.id for u in users]
    items: list[UserListItem] = []
    if user_ids:
        role_map = await _batch_get_user_roles(db, user_ids)
        for u in users:
            items.append(
                UserListItem(
                    id=u.id,
                    username=u.username,
                    real_name=u.real_name,
                    email=u.email,
                    phone=u.phone,
                    organization_id=u.organization_id,
                    organization_name=u.organization.name if u.organization else None,
                    roles=role_map.get(u.id, []),
                    is_active=u.is_active,
                    created_at=u.created_at,
                )
            )

    return PaginatedData(items=items, total=total, page=page, page_size=page_size)


async def create_user(db: AsyncSession, data: UserCreate) -> UserDetail:
    """新增用户 —— 校验唯一性 → 哈希密码 → 分配角色"""

    # 用户名唯一性
    existing = (await db.execute(select(User).where(User.username == data.username))).scalar_one_or_none()
    if existing:
        raise AppException(ErrorCode.CONFLICT, f"用户名 '{data.username}' 已存在")

    # 校验组织存在
    org = (await db.execute(select(Organization).where(Organization.id == data.organization_id))).scalar_one_or_none()
    if org is None:
        raise AppException(ErrorCode.NOT_FOUND, "所属组织不存在")

    # 校验角色存在
    roles = (await db.execute(select(Role).where(Role.id.in_(data.role_ids)))).scalars().all()
    if len(roles) != len(data.role_ids):
        raise AppException(ErrorCode.VALIDATION_ERROR, "部分角色 ID 不存在")

    # 创建用户
    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        real_name=data.real_name,
        organization_id=data.organization_id,
        email=data.email,
        phone=data.phone,
    )
    db.add(user)
    await db.flush()  # 获取 user.id

    # 分配角色
    for role_id in data.role_ids:
        db.add(UserRole(user_id=user.id, role_id=role_id))

    await db.flush()

    return UserDetail(
        id=user.id,
        username=user.username,
        real_name=user.real_name,
        email=user.email,
        phone=user.phone,
        organization_id=user.organization_id,
        organization_name=org.name,
        roles=[r.code for r in roles],
        is_active=user.is_active,
        created_at=user.created_at,
    )


async def update_user(db: AsyncSession, user_id: int, data: UserUpdate) -> UserDetail:
    """编辑用户 —— 不可改 username，更新基本信息和角色"""

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise AppException(ErrorCode.NOT_FOUND, "用户不存在")

    # 校验组织存在
    org = (await db.execute(select(Organization).where(Organization.id == data.organization_id))).scalar_one_or_none()
    if org is None:
        raise AppException(ErrorCode.NOT_FOUND, "所属组织不存在")

    # 校验角色存在
    roles = (await db.execute(select(Role).where(Role.id.in_(data.role_ids)))).scalars().all()
    if len(roles) != len(data.role_ids):
        raise AppException(ErrorCode.VALIDATION_ERROR, "部分角色 ID 不存在")

    # 更新基本信息
    user.real_name = data.real_name
    user.organization_id = data.organization_id
    user.email = data.email
    user.phone = data.phone

    # 替换角色：先删后增（用 delete 语句批量删除，避免 async delete 兼容问题）
    from sqlalchemy import delete as sql_delete
    await db.execute(sql_delete(UserRole).where(UserRole.user_id == user_id))
    for role_id in data.role_ids:
        db.add(UserRole(user_id=user.id, role_id=role_id))

    await db.flush()

    return UserDetail(
        id=user.id,
        username=user.username,
        real_name=user.real_name,
        email=user.email,
        phone=user.phone,
        organization_id=user.organization_id,
        organization_name=org.name,
        roles=[r.code for r in roles],
        is_active=user.is_active,
        created_at=user.created_at,
    )


async def toggle_user_status(db: AsyncSession, user_id: int, is_active: bool) -> None:
    """启用/禁用用户"""

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise AppException(ErrorCode.NOT_FOUND, "用户不存在")

    user.is_active = is_active
    await db.flush()


async def reset_user_password(db: AsyncSession, user_id: int, new_password: str) -> None:
    """管理员重置用户密码"""

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise AppException(ErrorCode.NOT_FOUND, "用户不存在")

    user.password_hash = hash_password(new_password)
    await db.flush()


async def _batch_get_user_roles(db: AsyncSession, user_ids: list[int]) -> dict[int, list[str]]:
    """批量查询用户角色，返回 {user_id: [role_code, ...]}"""
    if not user_ids:
        return {}

    stmt = (
        select(UserRole.user_id, Role.code)
        .join(Role, Role.id == UserRole.role_id)
        .where(UserRole.user_id.in_(user_ids))
    )
    result = await db.execute(stmt)
    rows = result.all()

    role_map: dict[int, list[str]] = {}
    for user_id, code in rows:
        role_map.setdefault(user_id, []).append(code)
    return role_map
