"""流程实例 Schema —— 请求/响应模型"""

from datetime import datetime
from pydantic import BaseModel, Field


# ==================== 发起实例 ====================

class NodeOverride(BaseModel):
    """发起实例时对单个节点的覆盖配置 —— 所有字段选填，未提供则使用模板默认值"""
    node_id: int = Field(..., description="模板节点 ID（快照中的 id）")
    assignee_id: int | None = Field(None, description="更换负责人")
    deadline: str | None = Field(None, description="截止日期，ISO 格式如 2026-07-21")
    checkers: list[dict] | None = Field(None, description="校验人列表 [{\"user_id\": 1}]")
    approvers: list[dict] | None = Field(None, description="审批人列表 [{\"user_id\": 1}]")
    skip: bool | None = Field(None, description="跳过该节点（仅 is_optional=1 的节点可跳过）")


class CreateInstanceRequest(BaseModel):
    """发起流程实例请求"""
    template_id: int = Field(..., description="模板 ID")
    version_id: int = Field(..., description="版本 ID（必须是已发布版本）")
    name: str = Field(..., min_length=2, max_length=100, description="实例名称")
    description: str | None = Field(None, max_length=500, description="实例描述")
    priority: str = Field("normal", description="优先级：urgent / high / normal / low")
    node_overrides: list[NodeOverride] | None = Field(None, description="节点覆盖配置（可选）")


class InstanceNodeBrief(BaseModel):
    """实例节点简要信息（创建实例响应用）"""
    id: int
    name: str
    is_start: bool
    is_end: bool
    is_skipped: bool
    status: str
    sort_order: int


class InstanceResponse(BaseModel):
    """发起实例成功响应"""
    id: int
    name: str
    template_id: int
    version_id: int
    organization_id: int
    initiator_id: int
    priority: str
    status: str
    nodes: list[InstanceNodeBrief] = []
    initiated_at: datetime | None = None


# ==================== 实例列表 ====================

class InstanceListItem(BaseModel):
    """实例列表项（列表视图字段）"""
    id: int
    name: str
    template_id: int
    template_name: str = ""
    organization_id: int
    organization_name: str = ""
    initiator_id: int
    initiator_name: str = ""
    priority: str
    status: str
    archive_status: str | None = None
    current_node_index: int = 0
    total_nodes: int = 0
    current_assignee_name: str | None = None
    initiated_at: datetime | None = None
    completed_at: datetime | None = None
    terminated_at: datetime | None = None


class InstanceListResponse(BaseModel):
    """实例列表分页响应"""
    items: list[InstanceListItem]
    total: int
    page: int
    page_size: int
