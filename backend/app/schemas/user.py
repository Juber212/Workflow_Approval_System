"""用户管理相关 Schema —— 新增/编辑/列表/状态/重置密码"""
from datetime import datetime

from pydantic import BaseModel, Field, field_validator
import re


# ==================== 字段校验器（模块级函数，供 UserCreate / UserUpdate 共享） ====================

def _validate_username(v: str) -> str:
    """用户名仅允许字母、数字、下划线"""
    if not re.match(r"^[a-zA-Z0-9_]+$", v):
        raise ValueError("用户名只能包含字母、数字和下划线")
    return v


def _validate_email(v: str | None) -> str | None:
    """邮箱格式校验（允许空值）"""
    if v is not None and v.strip():
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v.strip()):
            raise ValueError("邮箱格式不正确")
        return v.strip()
    return None


def _validate_phone(v: str | None) -> str | None:
    """手机号格式校验（允许空值，支持中国大陆手机号）"""
    if v is not None and v.strip():
        if not re.match(r"^1[3-9]\d{9}$", v.strip()):
            raise ValueError("手机号格式不正确（11位中国大陆手机号）")
        return v.strip()
    return None


class UserCreate(BaseModel):
    """新增用户请求 —— 密码由系统默认生成，管理员无需手动输入"""

    username: str = Field(..., min_length=3, max_length=30, description="登录用户名")
    real_name: str = Field(..., min_length=1, max_length=20, description="真实姓名")
    organization_id: int | None = Field(None, description="所属组织 ID（管理员可选，其他角色必填）")
    role_ids: list[int] = Field(..., min_length=1, description="角色 ID 列表")
    email: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=20)

    _validate_username = field_validator("username")(_validate_username)
    _validate_email = field_validator("email")(_validate_email)
    _validate_phone = field_validator("phone")(_validate_phone)


class UserUpdate(BaseModel):
    """编辑用户请求（不可改 username）"""

    real_name: str = Field(..., min_length=1, max_length=20, description="真实姓名")
    organization_id: int | None = Field(None, description="所属组织 ID（管理员可选，其他角色必填）")
    role_ids: list[int] = Field(..., min_length=1, description="角色 ID 列表")
    email: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=20)

    # 复用模块级校验函数（不可用 classmethod 引用，classmethod 绑定后会导致参数错位）
    _validate_email = field_validator("email")(_validate_email)
    _validate_phone = field_validator("phone")(_validate_phone)


class UserStatusUpdate(BaseModel):
    """启用/禁用用户"""

    is_active: bool = Field(..., description="是否启用")



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

    model_config = {"from_attributes": True}


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

    model_config = {"from_attributes": True}
