"""任务相关 Schema"""
from datetime import datetime
from pydantic import BaseModel, Field


class TaskListItem(BaseModel):
    """待办列表项"""
    id: int
    instance_id: int
    instance_name: str
    node_id: int
    node_name: str
    template_name: str = ""
    initiator_name: str = ""
    status: str  # pending/processing/waiting_check/waiting_approval/completed
    deadline: datetime | None = None
    is_overdue: bool = False
    days_remaining: int | None = None
    priority: str = "normal"
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class TaskDetail(BaseModel):
    """任务详情 —— 含节点文件/校验/审批进度"""
    id: int
    instance_id: int
    instance_name: str
    instance_status: str
    initiator_id: int
    initiator_name: str = ""
    priority: str = "normal"
    node_id: int
    node_name: str
    node_description: str | None = None
    node_status: str
    assignee_id: int
    assignee_name: str = ""
    status: str
    assignee_note: str | None = None
    require_file: bool = False
    file_folders: list | None = None  # 文件提交文件夹配置（来自节点快照）
    time_limit_days: int | None = None
    deadline: datetime | None = None
    round: int = 1
    total_nodes: int = 0
    current_node_index: int = 0
    nodes: list[dict] = []
    files: list[dict] = []
    checks: list[dict] = []
    approvals: list[dict] = []
    endorsements: list[dict] = []  # 批准记录（仅难度4时存在）
    rejected_type: str | None = None
    rejected_reason: str | None = None
    # 节点签批配置
    require_assignee_signature: bool = True
    require_checker_signature: bool = True
    require_approver_signature: bool = True
    require_endorser_signature: bool = True
    signature_x: float = 400
    signature_y: float = 100
    signature_page: int = -1
    # 当前负责人的签名图片 URL
    current_signature_url: str | None = None
    submitted_at: datetime | None = None
    created_at: datetime | None = None


class TaskSaveDraft(BaseModel):
    """保存草稿 —— 仅更新备注"""
    assignee_note: str | None = Field(None, max_length=500, description="负责人备注")


class TaskSubmit(BaseModel):
    """提交任务"""
    assignee_note: str | None = Field(None, max_length=500, description="负责人备注")
    # 签批：负责人选择的签名列表
    signatures: list[dict] | None = Field(None, description="签名列表 [{file_id, signature_x, signature_y, signature_page}]")
