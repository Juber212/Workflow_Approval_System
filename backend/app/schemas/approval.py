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
    round: int = 1
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ApprovalDetail(BaseModel):
    """审批详情 —— 含文件、校验/审批进度、流程信息"""
    id: int
    instance_id: int
    instance_name: str
    instance_status: str = ""
    initiator_id: int
    initiator_name: str = ""
    priority: str = "normal"
    node_id: int
    node_name: str
    node_description: str | None = None
    task_id: int | None = None
    approver_id: int
    approver_name: str = ""
    status: str
    opinion: str | None = None
    is_end_node: bool = False
    # 进度条
    total_nodes: int = 0
    current_node_index: int = 0
    nodes: list[dict] = []
    # 节点文件
    files: list[dict] = []
    # 校验进度
    check_progress: list[dict] = []
    # 审批进度
    approval_progress: list[dict] = []
    # 驳回目标候选（仅结束节点）
    reject_target_nodes: list[dict] = []
    signature_applied: bool = False
    # 节点签批配置（三个独立开关 + 默认位置）
    require_assignee_signature: bool = True
    require_checker_signature: bool = True
    require_approver_signature: bool = True
    signature_x: float = 400
    signature_y: float = 100
    signature_page: int = -1
    # 当前审批人的签名图片 URL
    current_signature_url: str | None = None
    # 本审批记录的签名明细
    signatures: list[dict] = []
    decided_at: datetime | None = None
    created_at: datetime | None = None


class ApprovalAction(BaseModel):
    """审批操作（通过/退回）"""
    opinion: str | None = Field(None, max_length=500, description="审批意见")
    # 仅结束节点终审总驳回时需要
    target_node_id: int | None = Field(None, description="总驳回目标节点 ID（仅结束节点审批）")
    # 签批：支持多文档多签名（新版），兼容旧版单签名参数
    signatures: list[dict] | None = Field(None, description="签名列表 [{file_id, signature_x, signature_y, signature_page}]")
    signature_x: float | None = Field(None, description="[兼容] 调整后的签名 X 坐标")
    signature_y: float | None = Field(None, description="[兼容] 调整后的签名 Y 坐标")
    signature_page: int | None = Field(None, description="[兼容] 选择的签名页码")
