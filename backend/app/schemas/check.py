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
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class CheckDetail(BaseModel):
    """校验详情 —— 含文件和校验进度"""
    id: int
    instance_id: int
    instance_name: str
    node_id: int
    node_name: str
    task_id: int
    checker_id: int
    checker_name: str = ""
    status: str
    opinion: str | None = None
    # 当前节点文件
    files: list[dict] = []
    # 负责人备注
    assignee_note: str | None = None
    # 并行校验进度
    check_progress: list[dict] = []
    decided_at: datetime | None = None
    created_at: datetime | None = None


class CheckAction(BaseModel):
    """校验操作（通过/退回）"""
    opinion: str | None = Field(None, max_length=500, description="校验意见（通过时可选，退回时必填）")
