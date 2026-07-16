"""节点预设 Schema —— 请求/响应模型"""

from datetime import datetime
from pydantic import BaseModel, Field


class PresetCreate(BaseModel):
    """创建预设请求"""
    name: str = Field(..., min_length=1, max_length=30, description="预设名称")
    node_name: str = Field(..., min_length=1, max_length=30, description="拖出后的默认节点名称")
    assignee_id: int | None = Field(None, description="负责人 ID")
    checkers: list[dict] | None = Field(None, description="校验人列表 [{\"user_id\": N}]")
    approvers: list[dict] | None = Field(None, description="审批人列表 [{\"user_id\": N}]")
    time_limit_days: int | None = Field(None, description="完成时限（天）")
    require_file: bool = Field(False, description="是否必须上传文件")


class PresetUpdate(BaseModel):
    """更新预设请求 —— 所有字段选填"""
    name: str | None = Field(None, min_length=1, max_length=30, description="预设名称")
    node_name: str | None = Field(None, min_length=1, max_length=30, description="拖出后的默认节点名称")
    assignee_id: int | None = Field(None, description="负责人 ID")
    checkers: list[dict] | None = Field(None, description="校验人列表")
    approvers: list[dict] | None = Field(None, description="审批人列表")
    time_limit_days: int | None = Field(None, description="完成时限（天）")
    require_file: bool | None = Field(None, description="是否必须上传文件")


class PresetResponse(BaseModel):
    """预设响应（单条）"""
    id: int
    name: str
    node_name: str
    assignee_id: int | None = None
    assignee_name: str | None = None
    checkers: list[dict] | None = None
    checkers_names: list[str] | None = None
    approvers: list[dict] | None = None
    approvers_names: list[str] | None = None
    time_limit_days: int | None = None
    require_file: bool = False
    sort_order: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PresetListResponse(BaseModel):
    """预设列表响应"""
    items: list[PresetResponse]
    total: int
