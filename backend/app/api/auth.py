"""认证 API —— 登录"""

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.core.security import verify_password, create_access_token
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.schemas.common import ApiResponse
from app.schemas.auth import LoginRequest, LoginResponse, UserInfoResponse
from app.models import User, Role, UserRole
from app.api.deps import get_current_active_user, CurrentUser

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户登录 —— 校验用户名密码，返回 JWT Token 和用户信息"""
    # 查询用户（含组织）
    stmt = (
        select(User)
        .options(joinedload(User.organization))
        .where(User.username == req.username)
    )
    result = await db.execute(stmt)
    user = result.unique().scalar_one_or_none()

    if user is None or not verify_password(req.password, user.password_hash):
        raise AppException(ErrorCode.LOGIN_FAILED)

    if not user.is_active:
        raise AppException(ErrorCode.FORBIDDEN, "账号已被禁用，请联系管理员")

    # 查询角色（通过 user_roles 多对多表）
    role_stmt = (
        select(Role.code)
        .join(UserRole, Role.id == UserRole.role_id)
        .where(UserRole.user_id == user.id)
    )
    role_result = await db.execute(role_stmt)
    roles = [row[0] for row in role_result.fetchall()]

    # 生成 JWT，payload 含 user_id/username/roles/org_id
    token = create_access_token(
        {
            "sub": str(user.id),
            "username": user.username,
            "roles": roles,
            "org_id": user.organization_id,
        }
    )

    return ApiResponse.ok(
        LoginResponse(
            token=token,
            user_id=user.id,
            username=user.username,
            real_name=user.real_name,
            roles=roles,
            organization_id=user.organization_id,
            organization_name=user.organization.name if user.organization else None,
        ).model_dump()
    )


@router.get("/me")
async def get_me(
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前登录用户完整信息（含签名状态）"""
    # 查询用户（含组织）
    stmt = (
        select(User)
        .options(joinedload(User.organization))
        .where(User.id == current_user.id)
    )
    result = await db.execute(stmt)
    user = result.unique().scalar_one_or_none()

    return ApiResponse.ok(
        UserInfoResponse(
            user_id=user.id,
            username=user.username,
            real_name=user.real_name,
            email=user.email,
            phone=user.phone,
            roles=current_user.roles,
            organization_id=user.organization_id,
            organization_name=user.organization.name if user.organization else None,
            has_signature=user.signature_image is not None,
        ).model_dump()
    )


@router.post("/logout")
async def logout(current_user: CurrentUser = Depends(get_current_active_user)):
    """退出登录 —— V1 客户端删除 Token 即可，服务端不做黑名单"""
    return ApiResponse.ok({"message": "退出成功"})
