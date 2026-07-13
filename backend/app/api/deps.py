"""FastAPI 依赖注入 —— JWT 认证 + 当前用户"""

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.core.security import decode_access_token
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import User, Role, UserRole


class CurrentUser:
    """当前登录用户信息（从 JWT 解析）"""

    def __init__(self, payload: dict):
        self.id: int = int(payload.get("sub", 0))
        self.username: str = payload.get("username", "")
        self.roles: list[str] = payload.get("roles", [])
        self.organization_id: int | None = payload.get("org_id")

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
    """获取当前用户并验证账号状态（用于需要查询数据库的场景）"""
    stmt = select(User).where(User.id == current_user.id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise AppException(ErrorCode.FORBIDDEN, "账号已被禁用")

    return current_user
