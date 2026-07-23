"""批准（Endorsement）相关 Schema —— 难度4级时的最终审核"""
from datetime import datetime
from pydantic import BaseModel, Field


class EndorsementListItem(BaseModel):
    """批准列表项"""
    id: int
    instance_id: int
    instance_name: str = ""
    node_id: int
    node_name: str = ""
    task_id: int | None = None
    endorser_id: int
    status: str
    is_end_node: bool = False
    round: int = 1
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class EndorsementDetail(BaseModel):
    """批准详情 —— 用于批准操作页"""
    id: int
    instance_id: int
    instance_name: str = ""
    instance_status: str = ""
    initiator_id: int
    initiator_name: str = ""
    priority: str = "normal"
    difficulty: str = "1"
    node_id: int
    node_name: str
    node_status: str
    task_id: int | None = None
    endorser_id: int
    endorser_name: str = ""
    status: str
    opinion: str | None = None
    round: int = 1
    require_endorser_signature: bool = True
    signature_x: float = 400
    signature_y: float = 100
    signature_page: int = -1
    current_signature_url: str | None = None  # 当前批准人的签名图片URL
    current_node_index: int = 0
    total_nodes: int = 0
    nodes: list[dict] = []      # 节点简要列表（进度链）
    files: list[dict] = []      # 当前轮次文件
    checks: list[dict] = []     # 校验记录
    approvals: list[dict] = []  # 审批记录
    decided_at: datetime | None = None
    created_at: datetime | None = None


class EndorseRequest(BaseModel):
    """批准通过请求"""
    opinion: str | None = Field(None, max_length=500, description="批准意见")
    signatures: list[dict] | None = Field(None, description="签名列表 [{file_id, signature_x, signature_y, signature_page}]")
    signature_x: float | None = Field(None, description="签名X坐标（旧版兼容）")
    signature_y: float | None = Field(None, description="签名Y坐标（旧版兼容）")
    signature_page: int | None = Field(None, description="签名页码（旧版兼容）")


class EndorseRejectRequest(BaseModel):
    """批准驳回请求"""
    opinion: str = Field(..., min_length=1, max_length=500, description="驳回意见（必填）")
