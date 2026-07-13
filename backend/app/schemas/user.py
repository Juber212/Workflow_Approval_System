"""用户管理相关 Schema —— 新增/编辑/列表/状态/重置密码"""
from datetime import datetime

from pydantic import BaseModel, Field, field_validator
import re


class UserCreate(BaseModel):
    """新增用户请求"""

    username: str = Field(..., min_length=3, max_length=30, description="登录用户名")
    real_name: str = Field(..., min_length=1, max_length=20, description="真实姓名")
    password: str = Field(..., min_length=6, max_length=128, description="登录密码")
    organization_id: int = Field(..., description="所属组织 ID")
    role_ids: list[int] = Field(..., min_length=1, description="角色 ID 列表")
    email: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=20)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """用户名仅允许字母、数字、下划线"""
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("用户名只能包含字母、数字和下划线")
        return v


class UserUpdate(BaseModel):
    """编辑用户请求（不可改 username）"""

    real_name: str = Field(..., min_length=1, max_length=20, description="真实姓名")
    organization_id: int = Field(..., description="所属组织 ID")
    role_ids: list[int] = Field(..., min_length=1, description="角色 ID 列表")
    email: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=20)


class UserStatusUpdate(BaseModel):
    """启用/禁用用户"""

    is_active: bool = Field(..., description="是否启用")


class ResetPasswordRequest(BaseModel):
    """管理员重置密码"""

    new_password: str = Field(..., min_length=6, max_length=128, description="新密码")


class UserListItem(BaseModel):
    """用户列表项"""

    id: int
    username: str
    real_name: str
    email: str | None = None
    phone: str | None = None
    organization_id: int | None = None
    organization_name: str | None = None
    roles: list[str] = []
    is_active: bool = True
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class UserDetail(BaseModel):
    """用户详情（含角色）"""

    id: int
    username: str
    real_name: str
    email: str | None = None
    phone: str | None = None
    organization_id: int | None = None
    organization_name: str | None = None
    roles: list[str] = []
    is_active: bool = True
    created_at: datetime | None = None

    class Config:
        from_attributes = True
