"""签名相关 Schema —— 统一的签名数据模型"""

from datetime import datetime
from pydantic import BaseModel, Field


class SignatureSlot(BaseModel):
    """单个签名槽位 —— 前端签批弹框提交的数据单元"""
    file_id: int = Field(..., description="签在哪个文件上")
    signature_x: float = Field(400, description="签名 X 坐标（距左边）")
    signature_y: float = Field(100, description="签名 Y 坐标（距底部）")
    signature_page: int = Field(-1, description="签名页码（-1=最后一页）")
    signature_width: float | None = Field(None, description="签名宽度（NULL=使用全局默认）")
    signature_height: float | None = Field(None, description="签名高度（NULL=使用全局默认）")


class SignatureItem(BaseModel):
    """签名记录响应（API 返回用）"""
    id: int
    file_id: int
    signer_id: int
    signer_name: str = ""
    role_type: str  # assignee | checker | approver
    source_id: int
    node_id: int
    signature_x: float = 400
    signature_y: float = 100
    signature_page: int = -1
    signature_width: float | None = None
    signature_height: float | None = None
    applied: bool = False
    sort_order: int = 0
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
