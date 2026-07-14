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
    """用户修改自己的密码"""
    old_password: str = Field(..., min_length=1, description="原密码")
    new_password: str = Field(..., min_length=6, max_length=32, description="新密码（6-32位）")
