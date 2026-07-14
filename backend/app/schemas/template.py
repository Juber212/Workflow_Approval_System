"""流程模板相关 Schema —— 简化版：无版本、无状态"""

from datetime import datetime
from pydantic import BaseModel, Field


class TemplateCreate(BaseModel):
    """创建模板"""
    name: str = Field(..., min_length=1, max_length=50, description="流程名称")
    description: str | None = Field(None, max_length=500, description="流程描述")
    organization_id: int = Field(..., description="所属组织 ID")


class TemplateUpdate(BaseModel):
    """更新模板基本信息"""
    name: str = Field(..., min_length=1, max_length=50, description="流程名称")
    description: str | None = Field(None, max_length=500, description="流程描述")


class TemplateListItem(BaseModel):
    """模板列表项"""
    id: int
    name: str
    description: str | None = None
    organization_id: int
    organization_name: str | None = None
    node_count: int = 0
    instance_count: int = 0
    created_by: int
    created_by_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class TemplateDetail(BaseModel):
    """模板详情（含节点/连线）"""
    id: int
    name: str
    description: str | None = None
    organization_id: int
    organization_name: str | None = None
    node_count: int = 0
    instance_count: int = 0
    nodes: list[dict] = []
    edges: list[dict] = []
    created_by: int
    created_by_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class OrgTemplateSummary(BaseModel):
    """组织卡片"""
    id: int
    name: str
    template_count: int = 0
    running_instance_count: int = 0
    latest_update_time: str | None = None
    is_current_user_org: bool = False
