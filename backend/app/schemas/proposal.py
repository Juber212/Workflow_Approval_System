"""方案相关 Schema"""
from datetime import datetime, date
from pydantic import BaseModel, Field


class ProposalCreateRequest(BaseModel):
    """发起方案请求 —— 方案无校验环节，仅需设计人 + 审批人"""
    name: str = Field(..., min_length=1, max_length=100, description="方案名称")
    description: str | None = Field(None, max_length=500, description="补充说明")
    organization_id: int = Field(..., description="所属组织")
    designer_id: int = Field(..., description="设计人（工作节点负责人）")
    approvers: list[dict] = Field(..., description="审批人列表 [{'user_id': N}]")
    deadline: datetime | None = Field(None, description="截止日期")


class ProposalListItem(BaseModel):
    """方案列表项"""
    id: int
    name: str
    description: str | None = None
    organization_id: int
    initiator_id: int
    initiator_name: str = ""
    status: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
