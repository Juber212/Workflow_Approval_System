"""认证相关 Schema"""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=30, description="登录用户名")
    password: str = Field(..., min_length=1, description="密码")


class LoginResponse(BaseModel):
    token: str
    user_id: int
    username: str
    real_name: str
    roles: list[str]
    organization_id: int | None
    organization_name: str | None
    must_change_password: bool = False  # 首次登录是否需要强制改密码


class UserInfoResponse(BaseModel):
    """当前用户完整信息（/auth/me 响应）"""
    user_id: int
    username: str
    real_name: str
    email: str | None = None
    phone: str | None = None
    roles: list[str]
    organization_id: int | None = None
    organization_name: str | None = None
    has_signature: bool = False  # 是否已上传签名图片


class ChangePasswordRequest(BaseModel):
    """用户修改自己的密码（密码强度由后端 validate_password_strength 校验）"""
    old_password: str = Field(..., min_length=1, description="原密码")
    new_password: str = Field(..., min_length=8, max_length=128, description="新密码（≥8位，含字母和数字）")


class UpdateProfileRequest(BaseModel):
    """用户更新个人资料（邮箱/手机号）"""
    email: str | None = Field(None, max_length=120, description="邮箱地址")
    phone: str | None = Field(None, max_length=20, description="手机号")
