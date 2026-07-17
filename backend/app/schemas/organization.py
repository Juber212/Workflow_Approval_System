"""组织管理相关 Schema"""
from datetime import datetime

from pydantic import BaseModel, Field


class OrganizationCreate(BaseModel):
    """新增组织"""

    name: str = Field(..., min_length=1, max_length=50, description="组织名称")
    description: str | None = Field(None, max_length=500, description="组织描述")


class OrganizationUpdate(BaseModel):
    """编辑组织"""

    name: str = Field(..., min_length=1, max_length=50, description="组织名称")
    description: str | None = Field(None, max_length=500, description="组织描述")


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
