"""项目 Schema —— 请求/响应模型"""

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
    require_assignee_signature: bool | None = Field(None, description="负责人提交时是否签名")
    require_checker_signature: bool | None = Field(None, description="校验人通过时是否签名")
    require_approver_signature: bool | None = Field(None, description="审批人通过时是否签名")
    endorser_id: int | None = Field(None, description="更换批准人（仅难度4级时生效）")
    require_endorser_signature: bool | None = Field(None, description="批准人通过时是否签名")


class CreateInstanceRequest(BaseModel):
    """发起项目请求"""
    template_id: int = Field(..., description="模板 ID")
    name: str = Field(..., min_length=2, max_length=100, description="实例名称")
    description: str | None = Field(None, max_length=500, description="实例描述")
    priority: str = Field("normal", description="优先级：urgent / high / normal / low")
    difficulty: str = Field("1", description="难度等级：1 / 2 / 3 / 4")
    contract_no: str | None = Field(None, max_length=100, description="合同号")
    product_model: str | None = Field(None, max_length=100, description="产品型号")
    sales_manager: str | None = Field(None, max_length=50, description="销售经理")
    node_overrides: list[NodeOverride] | None = Field(None, description="节点覆盖配置（可选）")
    proposal_id: int | None = Field(None, description="关联的方案 ID（可选）")
    doc_template_ids: list[int] | None = Field(None, description="文件模板 ID 列表（可选，为空则继承模板关联）")


class InstanceNodeBrief(BaseModel):
    """实例节点简要信息（创建实例响应用）"""
    id: int
    name: str
    is_start: bool
    is_end: bool
    status: str
    sort_order: int


class InstanceResponse(BaseModel):
    """发起实例成功响应"""
    id: int
    name: str
    organization_id: int
    initiator_id: int
    priority: str
    difficulty: str = "1"
    status: str
    nodes: list[InstanceNodeBrief] = []
    initiated_at: datetime | None = None


# ==================== 实例列表 ====================

class InstanceListItem(BaseModel):
    """实例列表项（列表视图字段）"""
    id: int
    name: str
    organization_id: int
    organization_name: str = ""
    initiator_id: int
    initiator_name: str = ""
    priority: str
    difficulty: str = "1"
    status: str
    current_node_index: int = 0
    total_nodes: int = 0
    current_assignee_name: str | None = None
    proposal_name: str | None = None  # 关联的方案名称
    initiated_at: datetime | None = None
    completed_at: datetime | None = None
    terminated_at: datetime | None = None


# ==================== 实例详情 ====================

class NodeFileBrief(BaseModel):
    """节点文件简要信息"""
    id: int
    original_name: str
    file_size: int | None = None
    uploader_id: int
    uploader_name: str = ""
    upload_type: str = "normal"
    folder_name: str | None = None  # 所属文件夹名称
    round: int = 1
    created_at: datetime | None = None


class CheckRecordBrief(BaseModel):
    """校验记录简要信息"""
    id: int
    checker_id: int
    checker_name: str = ""
    status: str
    opinion: str | None = None
    round: int = 1
    decided_at: datetime | None = None


class ApprovalBrief(BaseModel):
    """审批记录简要信息"""
    id: int
    approver_id: int
    approver_name: str = ""
    status: str
    opinion: str | None = None
    signature_applied: bool = False
    signature_x: float | None = None
    signature_y: float | None = None
    signature_page: int | None = None
    round: int = 1
    decided_at: datetime | None = None


class DetailNodeInfo(BaseModel):
    """实例详情中的节点信息（含文件/校验/审批）"""
    id: int
    name: str
    is_start: bool = False
    is_end: bool = False
    status: str
    sort_order: int = 0
    round: int = 1
    assignee_id: int | None = None
    assignee_name: str | None = None
    deadline: datetime | None = None
    time_limit_days: int | None = None
    checkers: list[dict] | None = None
    approvers: list[dict] | None = None
    require_file: bool = False
    file_folders: list | None = None  # 文件提交文件夹配置快照
    require_assignee_signature: bool = True
    require_checker_signature: bool = True
    require_approver_signature: bool = True
    endorser_id: int | None = None
    endorser_name: str | None = None
    require_endorser_signature: bool = True
    signature_x: float = 400
    signature_y: float = 100
    signature_page: int = -1
    approval_strategy: str = "all_approve"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    files: list[NodeFileBrief] = []
    checks: list[CheckRecordBrief] = []
    approvals: list[ApprovalBrief] = []
    endorsements: list[dict] = []  # 批准记录（仅难度4时存在）


class LogItemBrief(BaseModel):
    """操作日志简要信息"""
    id: int
    operator_type: str
    operator_id: int | None = None
    operator_name: str | None = None
    node_id: int | None = None
    operation_type: str
    round: int = 1
    description: str
    detail: dict | None = None
    created_at: datetime | None = None


class InstanceDetailResponse(BaseModel):
    """实例详情完整响应"""
    id: int
    name: str
    description: str | None = None
    organization_id: int
    organization_name: str = ""
    initiator_id: int
    initiator_name: str = ""
    priority: str
    difficulty: str = "1"
    status: str
    termination_reason: str | None = None
    contract_no: str | None = None
    product_model: str | None = None
    sales_manager: str | None = None
    proposal_id: int | None = None      # 关联的方案 ID
    proposal_name: str | None = None    # 关联的方案名称
    template_type: str = "project"      # 模板类型：project / proposal（前端面包屑/标题用）
    current_node_index: int = 0
    total_nodes: int = 0
    initiated_at: datetime | None = None
    completed_at: datetime | None = None
    terminated_at: datetime | None = None
    nodes: list[DetailNodeInfo] = []
    logs: dict | None = None  # {"items": [...], "total": N}


# ==================== 终止实例 ====================

class TerminateInstanceRequest(BaseModel):
    """终止项目请求"""
    reason: str = Field(
        ..., min_length=1, max_length=500,
        description="终止原因（必填，1-500字符）"
    )


# ==================== 紧急换人 ====================

class ChangePersonnelRequest(BaseModel):
    """紧急换人请求 —— 所有字段选填，仅更新传入的字段"""
    assignee_id: int | None = Field(None, description="新负责人 ID")
    checkers: list[dict] | None = Field(None, description="新校验人列表 [{\"user_id\": N}]")
    approvers: list[dict] | None = Field(None, description="新审批人列表 [{\"user_id\": N}]")
    endorser_id: int | None = Field(None, description="新批准人 ID（仅难度4级时有效）")


# ==================== 优先级修改 ====================

class ChangePriorityRequest(BaseModel):
    """修改优先级请求"""
    priority: str = Field(
        ..., pattern="^(urgent|high|normal|low)$",
        description="优先级：urgent / high / normal / low"
    )


# ==================== 补交文件 ====================

class SupplementFileResponse(BaseModel):
    """补交文件上传响应 —— 返回本次上传的文件列表"""
    files: list[NodeFileBrief] = Field(..., description="本次补交的文件列表")
