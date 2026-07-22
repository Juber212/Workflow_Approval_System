"""校验记录相关 Schema"""
from datetime import datetime
from pydantic import BaseModel, Field


class CheckListItem(BaseModel):
    """校验列表项"""
    id: int
    instance_id: int
    instance_name: str
    node_id: int
    node_name: str
    task_id: int
    submitter_name: str = ""  # 节点负责人姓名
    status: str  # pending/passed/returned/terminated
    round: int = 1
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CheckDetail(BaseModel):
    """校验详情 —— 含文件和校验进度"""
    id: int
    instance_id: int
    instance_name: str
    instance_status: str = ""
    initiator_id: int
    initiator_name: str = ""
    submitter_id: int
    submitter_name: str = ""
    priority: str = "normal"
    node_id: int
    node_name: str
    task_id: int
    checker_id: int
    checker_name: str = ""
    status: str
    opinion: str | None = None
    # 进度条
    total_nodes: int = 0
    current_node_index: int = 0
    nodes: list[dict] = []
    # 当前节点文件
    files: list[dict] = []
    # 负责人备注
    assignee_note: str | None = None
    # 并行校验进度
    check_progress: list[dict] = []
    # 节点签批配置
    require_assignee_signature: bool = True
    require_checker_signature: bool = True
    require_approver_signature: bool = True
    signature_x: float = 400
    signature_y: float = 100
    signature_page: int = -1
    # 当前校验人的签名图片 URL
    current_signature_url: str | None = None
    decided_at: datetime | None = None
    created_at: datetime | None = None


class CheckAction(BaseModel):
    """校验操作（通过/退回）"""
    opinion: str | None = Field(None, max_length=500, description="校验意见（通过时可选，退回时必填）")
    # 签批：支持多文档多签名
    signatures: list[dict] | None = Field(None, description="签名列表 [{file_id, signature_x, signature_y, signature_page}]")
