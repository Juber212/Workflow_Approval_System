"""Dashboard Schema —— 首页看板全局统计响应"""

from pydantic import BaseModel


class DashboardStats(BaseModel):
    """四大统计卡片"""
    running_instances: int = 0
    archived_total: int = 0
    archived_this_month: int = 0
    overdue_warnings: int = 0


class TaskDistItem(BaseModel):
    """任务状态分布项"""
    status: str
    label: str
    color: str
    count: int


class BottleneckItem(BaseModel):
    """流程卡点追踪项"""
    instance_id: int
    instance_name: str
    organization_name: str = ""
    progress_chain: list[str] = []
    current_node_name: str = ""
    current_assignee_name: str = ""
    priority: str = "normal"
    finished_count: int = 0
    total_nodes: int = 0
    overdue_status: str = "正常"
    all_finished: bool = False


class OverdueItem(BaseModel):
    """超期预警项"""
    task_id: int
    instance_id: int
    instance_name: str = ""
    node_name: str = ""
    assignee_name: str = ""
    deadline: str | None = None
    days_label: str = ""
    organization_name: str = ""
    is_overdue: bool = False


class OrgOverviewInst(BaseModel):
    """各所概览——实例简要"""
    id: int
    name: str
    priority: str = "normal"
    current_node_name: str = "—"
    current_assignee_name: str = ""
    status: str = "running"


class OrgOverview(BaseModel):
    """各所流程概览"""
    org_id: int
    org_name: str
    running_count: int = 0
    instances: list[OrgOverviewInst] = []


class DashboardData(BaseModel):
    """Dashboard 完整响应数据"""
    stats: DashboardStats = DashboardStats()
    task_distribution: list[TaskDistItem] = []
    bottleneck: list[BottleneckItem] = []
    overdue_list: list[OverdueItem] = []
    org_overview: list[OrgOverview] = []
