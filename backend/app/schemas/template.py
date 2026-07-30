"""项目模板相关 Schema —— 简化版：无版本、无状态"""

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
    type: str = "project"  # 模板类型: project / proposal
    description: str | None = None
    organization_id: int
    organization_name: str | None = None
    node_count: int = 0
    instance_count: int = 0
    created_by: int
    created_by_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class TemplateDetail(BaseModel):
    """模板详情（含节点/连线）"""
    id: int
    name: str
    type: str = "project"  # 模板类型: project / proposal
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

    model_config = {"from_attributes": True}


class DocTemplateItem(BaseModel):
    """文件模板列表项"""
    id: int
    name: str                     # 显示名称
    original_name: str            # 原始文件名
    file_size: int
    file_type: str                # docx / xlsx
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class DocTemplateListResponse(BaseModel):
    """文件模板列表"""
    items: list[DocTemplateItem]
    # 可用变量列表（供管理员参考）
    available_variables: list[str]


# ─── 模板分类 ───

class TemplateCategoryCreate(BaseModel):
    """创建模板分类"""
    name: str = Field(..., min_length=1, max_length=100, description="分类名称")
    description: str | None = Field(None, max_length=200, description="分类描述")
    organization_id: int = Field(..., description="所属组织 ID")


class TemplateCategoryUpdate(BaseModel):
    """更新模板分类"""
    name: str = Field(..., min_length=1, max_length=100, description="分类名称")
    description: str | None = Field(None, max_length=200, description="分类描述")


class TemplateCategoryItem(BaseModel):
    """模板分类列表项"""
    id: int
    organization_id: int
    organization_name: str | None = None
    name: str
    description: str | None = None
    document_count: int = 0  # 分类下文件模板数量
    created_by: int
    created_by_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class TemplateCategoryDetail(TemplateCategoryItem):
    """模板分类详情 —— 含内部文件模板列表"""
    documents: list[DocTemplateItem] = []


class CategoryDocLinkRequest(BaseModel):
    """关联/取消关联分类中的文件模板"""
    doc_ids: list[int] = Field(..., min_length=1, description="文件模板 ID 列表")


class OrgTemplateSummary(BaseModel):
    """组织卡片"""
    id: int
    name: str
    template_count: int = 0
    running_instance_count: int = 0
    completed_instance_count: int = 0   # 已完成项目数
    terminated_instance_count: int = 0  # 已终止项目数
    latest_update_time: str | None = None
    is_current_user_org: bool = False
