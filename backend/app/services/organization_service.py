"""组织管理业务逻辑"""
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import Organization, User, UserRole, Role
from app.schemas.common import PaginatedData
from app.schemas.organization import OrganizationCreate, OrganizationUpdate, OrganizationListItem


async def list_organizations(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
    is_active: bool | None = None,
) -> PaginatedData:
    """分页查询组织列表，含 manager_name 和 user_count 计算字段"""

    # 总数
    count_stmt = select(func.count()).select_from(Organization)
    if is_active is not None:
        count_stmt = count_stmt.where(Organization.is_active == is_active)
    total = (await db.execute(count_stmt)).scalar() or 0

    # 组织列表
    stmt = select(Organization).order_by(Organization.id)
    if is_active is not None:
        stmt = stmt.where(Organization.is_active == is_active)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    orgs = result.scalars().all()

    if not orgs:
        return PaginatedData(items=[], total=total, page=page, page_size=page_size)

    org_ids = [o.id for o in orgs]

    # 批量计算 user_count（按组织分组）
    user_count_stmt = (
        select(User.organization_id, func.count(User.id))
        .where(User.organization_id.in_(org_ids))
        .group_by(User.organization_id)
    )
    user_count_rows = (await db.execute(user_count_stmt)).all()
    user_count_map = {org_id: cnt for org_id, cnt in user_count_rows}

    # 批量查询所长（manager 角色 + 该组织下的用户）
    manager_stmt = (
        select(User.organization_id, User.real_name)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            User.organization_id.in_(org_ids),
            Role.code == "manager",
            User.is_active == True,
        )
    )
    manager_rows = (await db.execute(manager_stmt)).all()

    # 每个组织取第一个所长作为代表
    manager_map: dict[int, str] = {}
    for org_id, real_name in manager_rows:
        if org_id not in manager_map:
            manager_map[org_id] = real_name

    items = [
        OrganizationListItem(
            id=o.id,
            name=o.name,
            description=o.description,
            is_active=o.is_active,
            user_count=user_count_map.get(o.id, 0),
            manager_name=manager_map.get(o.id),
            created_at=o.created_at,
        )
        for o in orgs
    ]

    return PaginatedData(items=items, total=total, page=page, page_size=page_size)


async def create_organization(db: AsyncSession, data: OrganizationCreate) -> Organization:
    """新增组织 —— 校验名称唯一"""

    existing = (await db.execute(select(Organization).where(Organization.name == data.name))).scalar_one_or_none()
    if existing:
        raise AppException(ErrorCode.CONFLICT, f"组织名称 '{data.name}' 已存在")

    org = Organization(name=data.name, description=data.description)
    db.add(org)
    await db.flush()
    return org


async def update_organization(db: AsyncSession, org_id: int, data: OrganizationUpdate) -> Organization:
    """编辑组织 —— 校验名称唯一（排除自身）"""

    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if org is None:
        raise AppException(ErrorCode.NOT_FOUND, "组织不存在")

    # 名称唯一性（排除自身）
    existing = (
        await db.execute(select(Organization).where(Organization.name == data.name, Organization.id != org_id))
    ).scalar_one_or_none()
    if existing:
        raise AppException(ErrorCode.CONFLICT, f"组织名称 '{data.name}' 已存在")

    org.name = data.name
    org.description = data.description
    await db.flush()
    return org


async def toggle_org_status(db: AsyncSession, org_id: int, is_active: bool) -> None:
    """启用/停用组织"""

    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if org is None:
        raise AppException(ErrorCode.NOT_FOUND, "组织不存在")

    org.is_active = is_active
    await db.flush()
