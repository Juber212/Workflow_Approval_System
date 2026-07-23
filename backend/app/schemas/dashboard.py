"""Dashboard Schema —— 首页看板全局统计响应"""

from pydantic import BaseModel


class DashboardStats(BaseModel):
    """四大统计卡片（项目用 overdue_warnings=超期预警；方案用 overdue_warnings=方案总数）"""
    running_instances: int = 0
    archived_total: int = 0
    archived_this_month: int = 0
    overdue_warnings: int = 0
    total: int = 0  # 总数（方案卡片用）


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
    difficulty: str = "1"
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


class OrgOverview(BaseModel):
    """各所流程概览（供柱状图 + 饼图）"""
    org_id: int
    org_name: str
    total_count: int = 0       # 全部项目数（所有状态）
    running_count: int = 0     # 运行中项目数
    completed_count: int = 0   # 已完成项目数


class MyTaskCounts(BaseModel):
    """当前用户的个人待办统计"""
    pending: int = 0       # 待处理（任务 assignee_id=本人，status=pending）
    checking: int = 0      # 待校验（check_records checker_id=本人，status=pending）
    approval: int = 0      # 待审批（approvals approver_id=本人，status=pending）


class DashboardData(BaseModel):
    """Dashboard 完整响应数据"""
    stats: DashboardStats = DashboardStats()
    proposal_stats: DashboardStats = DashboardStats()  # 方案统计（同结构，含义不同）
    task_distribution: list[TaskDistItem] = []
    bottleneck: list[BottleneckItem] = []
    overdue_list: list[OverdueItem] = []
    org_overview: list[OrgOverview] = []
    my_task_counts: MyTaskCounts = MyTaskCounts()  # 当前用户个人待办
