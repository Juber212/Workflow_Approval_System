"""校验记录相关 Schema"""
from datetime import datetime
from pydantic import BaseModel, Field

from app.schemas.instance import CheckRecordBrief, DetailFileBrief, InstanceNodeBrief


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
    deadline: str | None = None       # 截止时间（ISO 格式）
    is_overdue: bool = False           # 是否逾期
    days_remaining: int | None = None  # 剩余天数（负数=已逾期）
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
    difficulty: str = "1"  # 难度等级（1-4）
    node_id: int
    node_name: str
    node_description: str | None = None  # 节点说明
    task_id: int
    checker_id: int
    checker_name: str = ""
    status: str
    opinion: str | None = None
    time_limit_days: int | None = None  # 完成时限（工作日）
    deadline: datetime | None = None  # 截止时间
    round: int = 1  # 当前轮次
    # 进度条
    total_nodes: int = 0
    current_node_index: int = 0
    nodes: list[InstanceNodeBrief] = []
    # 实例全部文件（展示用）
    files: list[DetailFileBrief] = []
    # 仅本节点文件（签批预览用，后端过滤）
    node_files: list[DetailFileBrief] = []
    # 负责人备注
    assignee_note: str | None = None
    # 并行校验进度
    check_progress: list[CheckRecordBrief] = []
    # 节点签批配置
    require_assignee_signature: bool = True
    require_checker_signature: bool = True
    require_approver_signature: bool = True
    signature_x: float = 400
    signature_y: float = 100
    signature_page: int = -1
    # 当前校验人的签名图片 URL
    current_signature_url: str | None = None
    # 角色维度签名默认配置（从 SystemConfig 读取）
    role_signature: dict | None = None
    decided_at: datetime | None = None
    created_at: datetime | None = None


class CheckAction(BaseModel):
    """校验操作（通过/退回）"""
    opinion: str | None = Field(None, max_length=500, description="校验意见（通过时可选，退回时必填）")
    # 签批：支持多文档多签名
    signatures: list[dict] | None = Field(None, description="签名列表 [{file_id, signature_x, signature_y, signature_page}]")
