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
    current_handlers: str = ""  # 当前处理人（根据节点状态动态：负责人/校验人/审批人/批准人）
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
    total_count: int = 0         # 全部项目数（所有状态）
    running_count: int = 0       # 运行中项目数
    completed_count: int = 0     # 已完成项目数
    terminated_count: int = 0    # 已终止项目数


class MyTaskCounts(BaseModel):
    """当前用户的个人待办统计"""
    pending: int = 0       # 待处理（任务 assignee_id=本人，status=pending）
    checking: int = 0      # 待校验（check_records checker_id=本人，status=pending）
    approval: int = 0      # 待审批（approvals approver_id=本人，status=pending）


class MyPendingItem(BaseModel):
    """我的待办列表项 —— 合并 Task/CheckRecord/Approval 三表，按优先级+截止时间排序"""
    type: str               # "task" | "check" | "approval"
    type_label: str         # "待办" | "校验" | "审批"（前端可直接展示）
    id: int                 # 记录 ID，用于构造跳转链接 /profile/{type}/{id}
    instance_id: int        # 所属实例 ID
    instance_name: str      # 实例名称（项目/方案名）
    node_name: str          # 当前节点名称
    priority: str           # urgent / high / normal / low
    deadline: str | None = None       # ISO 格式截止时间，null 表示无截止
    is_overdue: bool = False           # 是否逾期
    days_remaining: int | None = None  # 剩余天数（负数=已逾期）


class DashboardData(BaseModel):
    """Dashboard 完整响应数据"""
    stats: DashboardStats = DashboardStats()
    proposal_stats: DashboardStats = DashboardStats()  # 方案统计（同结构，含义不同）
    task_distribution: list[TaskDistItem] = []
    bottleneck: list[BottleneckItem] = []
    proposal_bottleneck: list[BottleneckItem] = []  # 方案卡点追踪（简化列）
    overdue_list: list[OverdueItem] = []
    org_overview: list[OrgOverview] = []        # 各所项目概览
    proposal_org_overview: list[OrgOverview] = []  # 各所方案概览（前端 tab 切换用）
    my_task_counts: MyTaskCounts = MyTaskCounts()  # 当前用户个人待办计数（侧边栏角标用）
    my_pending: list[MyPendingItem] = []           # 当前用户待办列表（项目视图）
    proposal_my_pending: list[MyPendingItem] = []   # 当前用户待办列表（方案视图）
