"""流程模板相关 Schema"""
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


class VersionHistoryItem(BaseModel):
    """版本历史简要"""

    id: int
    version_number: int
    status: str
    node_count: int = 0
    edge_count: int = 0
    has_soft_overrides: bool = False
    published_by: int | None = None
    published_by_name: str | None = None
    published_at: datetime | None = None

    class Config:
        from_attributes = True


class TemplateListItem(BaseModel):
    """模板列表项"""

    id: int
    name: str
    description: str | None = None
    organization_id: int
    organization_name: str | None = None
    status: str
    current_version: int
    node_count: int = 0  # 计算字段
    instance_count: int = 0  # 计算字段（运行中实例数）
    can_edit: bool = False  # 仅 draft 可编辑
    can_publish: bool = False  # draft + 节点数 >= 3 可发布
    can_start: bool = False  # published 且用户所属组织匹配
    created_by: int
    created_by_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class TemplateDetail(BaseModel):
    """模板详情（含节点/连线/版本历史）"""

    id: int
    name: str
    description: str | None = None
    organization_id: int
    organization_name: str | None = None
    status: str
    current_version: int
    node_count: int = 0
    instance_count: int = 0
    nodes: list[dict] = []  # TemplateNode 简化列表
    edges: list[dict] = []  # TemplateEdge 简化列表
    versions: list[VersionHistoryItem] = []
    created_by: int
    created_by_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class VersionDetail(BaseModel):
    """版本快照详情 —— 含完整 nodes_snapshot / edges_snapshot"""

    id: int
    version_number: int
    status: str
    nodes_snapshot: list[dict] = []
    edges_snapshot: list[dict] = []
    soft_config_overrides: dict | None = None
    published_by: int | None = None
    published_by_name: str | None = None
    published_at: datetime | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class OrgTemplateSummary(BaseModel):
    """组织卡片 —— 用于模板组织选择页"""

    id: int
    name: str
    template_count: int = 0
    running_instance_count: int = 0
