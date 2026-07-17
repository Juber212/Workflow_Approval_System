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
    node_id: int
    node_name: str
    node_description: str | None = None
    node_status: str
    assignee_id: int
    assignee_name: str = ""
    status: str
    assignee_note: str | None = None
    require_file: bool = False
    time_limit_days: int | None = None
    deadline: datetime | None = None
    round: int = 1
    files: list[dict] = []
    checks: list[dict] = []
    approvals: list[dict] = []
    submitted_at: datetime | None = None
    created_at: datetime | None = None


class TaskSaveDraft(BaseModel):
    """保存草稿 —— 仅更新备注"""
    assignee_note: str | None = Field(None, max_length=500, description="负责人备注")


class TaskSubmit(BaseModel):
    """提交任务"""
    assignee_note: str | None = Field(None, max_length=500, description="负责人备注")
