"""审批相关 Schema"""
from datetime import datetime
from pydantic import BaseModel, Field


class ApprovalListItem(BaseModel):
    """审批列表项"""
    id: int
    instance_id: int
    instance_name: str
    node_id: int
    node_name: str
    task_id: int | None = None
    approver_id: int
    status: str  # pending/approved/rejected/terminated
    is_end_node: bool = False
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class ApprovalDetail(BaseModel):
    """审批详情 —— 含文件、校验/审批进度、流程信息"""
    id: int
    instance_id: int
    instance_name: str
    node_id: int
    node_name: str
    node_description: str | None = None
    task_id: int | None = None
    approver_id: int
    approver_name: str = ""
    status: str
    opinion: str | None = None
    is_end_node: bool = False
    # 节点文件
    files: list[dict] = []
    # 校验进度
    check_progress: list[dict] = []
    # 审批进度
    approval_progress: list[dict] = []
    # 驳回目标候选（仅结束节点）
    reject_target_nodes: list[dict] = []
    signature_applied: bool = False
    decided_at: datetime | None = None
    created_at: datetime | None = None


class ApprovalAction(BaseModel):
    """审批操作（通过/退回）"""
    opinion: str | None = Field(None, max_length=500, description="审批意见")
    # 仅结束节点终审总驳回时需要
    target_node_id: int | None = Field(None, description="总驳回目标节点 ID（仅结束节点审批）")
