"""认证 API —— 登录 / 个人信息 / 密码修改 / 签名上传"""

from fastapi import APIRouter, Depends, Header, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
import os
import uuid

from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_password, create_access_token, hash_password
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.schemas.common import ApiResponse
from app.schemas.auth import LoginRequest, LoginResponse, UserInfoResponse, ChangePasswordRequest
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


@router.put("/password")
async def change_password(
    req: ChangePasswordRequest,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """用户修改自己的密码 —— 需验证原密码"""
    # 查询用户
    stmt = select(User).where(User.id == current_user.id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise AppException(ErrorCode.NOT_FOUND, "用户不存在")

    # 验证原密码
    if not verify_password(req.old_password, user.password_hash):
        raise AppException(ErrorCode.FORBIDDEN, "原密码错误")

    # 更新密码
    user.password_hash = hash_password(req.new_password)
    await db.commit()

    return ApiResponse.ok(message="密码修改成功")


@router.post("/signature")
async def upload_signature(
    file: UploadFile = File(..., description="签名图片（PNG透明底，200×60px，<500KB）"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """上传/更新个人签名图片 —— 用于审批时 PDF 自动签名"""
    # 校验文件类型
    if file.content_type not in ("image/png", "image/jpeg", "image/gif", "image/webp"):
        raise AppException(ErrorCode.BAD_REQUEST, "仅支持 PNG/JPG/GIF/WebP 格式")

    # 读取文件内容以校验大小
    contents = await file.read()
    max_size = 500 * 1024  # 500KB
    if len(contents) > max_size:
        raise AppException(ErrorCode.BAD_REQUEST, "签名图片不能超过 500KB")

    # 查询用户
    stmt = select(User).where(User.id == current_user.id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise AppException(ErrorCode.NOT_FOUND, "用户不存在")

    # 创建存储目录（使用配置中的 STORAGE_ROOT）
    upload_dir = os.path.join(settings.STORAGE_ROOT, "signatures")
    os.makedirs(upload_dir, exist_ok=True)

    # 删除旧签名文件（如果存在）
    if user.signature_image:
        old_path = os.path.join(upload_dir, os.path.basename(user.signature_image))
        if os.path.exists(old_path):
            os.remove(old_path)

    # 保存新签名文件
    ext = os.path.splitext(file.filename or "signature.png")[1] or ".png"
    safe_name = f"{current_user.id}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = os.path.join(upload_dir, safe_name)

    with open(file_path, "wb") as f:
        f.write(contents)

    # 更新数据库
    user.signature_image = file_path
    await db.commit()

    return ApiResponse.ok(
        {"signature_url": f"/storage/signatures/{safe_name}"},
        message="签名图片已上传",
    )
