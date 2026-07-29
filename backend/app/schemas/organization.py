"""组织管理相关 Schema"""
import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


def _validate_org_name(v: str) -> str:
    """组织名称不能为空或纯空白"""
    stripped = v.strip()
    if not stripped:
        raise ValueError("组织名称不能为空")
    return stripped


class OrganizationCreate(BaseModel):
    """新增组织"""

    name: str = Field(..., min_length=1, max_length=50, description="组织名称")
    description: str | None = Field(None, max_length=500, description="组织描述")

    _validate_name = field_validator("name")(_validate_org_name)


class OrganizationUpdate(BaseModel):
    """编辑组织"""

    name: str = Field(..., min_length=1, max_length=50, description="组织名称")
    description: str | None = Field(None, max_length=500, description="组织描述")

    _validate_name = field_validator("name")(_validate_org_name)


class OrganizationStatusUpdate(BaseModel):
    """启停组织"""

    is_active: bool = Field(..., description="是否启用")


class OrganizationListItem(BaseModel):
    """组织列表项"""

    id: int
    name: str
    description: str | None = None
    is_active: bool = True
    user_count: int = 0  # 计算字段：该组织下的用户数
    manager_name: str | None = None  # 计算字段：所长姓名
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
