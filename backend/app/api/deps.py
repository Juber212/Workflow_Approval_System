"""FastAPI 依赖注入 —— JWT 认证 + 当前用户"""

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.core.security import decode_access_token
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import User, Role, UserRole, FlowTemplate


class CurrentUser:
    """当前登录用户信息（从 JWT 解析）"""

    def __init__(self, payload: dict):
        self.id: int = int(payload.get("sub", 0))
        self.username: str = payload.get("username", "")
        self.roles: list[str] = payload.get("roles", [])
        self.organization_id: int | None = payload.get("org_id")
        self.jti: str = payload.get("jti", "")  # JWT 唯一 ID，用于黑名单吊销
        self.iat: int = payload.get("iat", 0)   # 签发时间（Unix 时间戳）

    def has_role(self, role_code: str) -> bool:
        """检查是否拥有指定角色"""
        return role_code in self.roles

    def is_admin(self) -> bool:
        return self.has_role("system_admin")

    def is_manager(self) -> bool:
        return self.has_role("manager")


async def get_current_user(
    authorization: str = Header(..., description="Bearer <token>"),
) -> CurrentUser:
    """从 Authorization Header 解析 JWT，返回当前用户"""
    if not authorization.startswith("Bearer "):
        raise AppException(ErrorCode.UNAUTHORIZED)

    token = authorization[7:]  # 去掉 "Bearer " 前缀
    payload = decode_access_token(token)
    if payload is None:
        raise AppException(ErrorCode.UNAUTHORIZED)

    return CurrentUser(payload)


async def get_current_active_user(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """获取当前用户并验证账号状态，同时重查实时角色（P0-9：角色变更即时生效）

    JWT 中的 roles 是签发时的快照——管理员降级/升级用户后旧 token 仍携带旧角色。
    这里每次请求从 DB 重查角色覆盖快照，require_admin/require_manager 基于最新角色判断。
    仅当 DB 角色查询到非空结果才覆盖（避免 mock 环境与「无角色用户」误清空 JWT 快照）。
    """
    stmt = select(User).where(User.id == current_user.id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise AppException(ErrorCode.FORBIDDEN, "账号已被禁用")

    # 重查实时角色（与账号状态校验在同一次依赖解析内完成）
    role_result = await db.execute(
        select(Role.code)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == current_user.id)
    )
    db_roles = list(role_result.scalars().all())
    if db_roles:
        current_user.roles = db_roles

    return current_user


def require_admin(current_user: CurrentUser) -> None:
    """要求系统管理员权限，否则抛出 403（供各 Admin API 复用）"""
    if not current_user.is_admin():
        raise AppException(ErrorCode.FORBIDDEN, "仅系统管理员可执行此操作")


def require_manager(current_user: CurrentUser) -> None:
    """要求所长权限，否则抛出 403（供模板/实例/设计器 API 复用）"""
    if not current_user.is_manager():
        raise AppException(ErrorCode.FORBIDDEN, "仅所长可执行此操作")


def require_same_org(current_user: CurrentUser, org_id: int) -> None:
    """要求当前用户属于指定组织，否则抛出 403（防止跨所操作）"""
    if current_user.organization_id is None:
        raise AppException(ErrorCode.FORBIDDEN, "您无组织归属，不可执行此操作")
    if current_user.organization_id != org_id:
        raise AppException(ErrorCode.FORBIDDEN, "不可跨所操作，仅本所所长可执行此操作")


def resolve_org_scope(current_user: CurrentUser, organization_id: int | None) -> int | None:
    """解析组织筛选范围：非管理员不传 org_id 时默认限制为本组织（防止跨所数据泄露）

    用于 templates / instances / proposals 列表端点的 organization_id 参数处理。
    """
    if organization_id is None and not current_user.is_admin():
        return current_user.organization_id
    return organization_id


async def check_template_ownership(db: AsyncSession, template_id: int, current_user: CurrentUser) -> int:
    """校验模板存在 + 当前用户是本所所长 → 返回模板所属组织 ID

    可用于 PUT/DELETE 模板端点及发起实例时的模板校验。
    原为 designer.py 私有函数 _check_template_ownership，已提升为公共 helper。
    """
    require_manager(current_user)
    org_id = (await db.execute(
        select(FlowTemplate.organization_id).where(FlowTemplate.id == template_id)
    )).scalar_one_or_none()
    if org_id is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")
    require_same_org(current_user, org_id)
    return org_id
