"""Dashboard Schema —— 首页看板全局统计响应"""

from pydantic import BaseModel


class DashboardStats(BaseModel):
    """四大统计卡片（项目用 overdue_warnings=超期预警；方案用 overdue_warnings=方案总数）"""
    running_instances: int = 0
    archived_total: int = 0
    archived_this_month: int = 0
    overdue_warnings: int = 0
    total: int = 0  # 总数（方案卡片用）


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


class OrgOverview(BaseModel):
    """各所流程概览（供柱状图 + 饼图）"""
    org_id: int
    org_name: str
    total_count: int = 0         # 全部项目数（所有状态）
    running_count: int = 0       # 运行中项目数
    completed_count: int = 0     # 已完成项目数
    terminated_count: int = 0    # 已终止项目数


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


class TrendPoint(BaseModel):
    """趋势图数据点（按月/年粒度）"""
    period: str  # 月度 "YYYY-MM" / 年度 "YYYY"
    label: str   # 中文化标签（"2026年8月" / "2026年"）
    initiated: int = 0  # 该时间段发起量
    completed: int = 0  # 该时间段归档量


class TrendData(BaseModel):
    """发起/归档趋势完整响应"""
    granularity: str = "month"
    periods: list[TrendPoint] = []


class DashboardData(BaseModel):
    """Dashboard 完整响应数据"""
    stats: DashboardStats = DashboardStats()
    proposal_stats: DashboardStats = DashboardStats()  # 方案统计（同结构，含义不同）
    bottleneck: list[BottleneckItem] = []
    bottleneck_total: int = 0  # 项目卡点追踪真实运行中实例总数（列表仅取前 N 条）
    proposal_bottleneck: list[BottleneckItem] = []  # 方案卡点追踪（简化列）
    proposal_bottleneck_total: int = 0  # 方案卡点追踪真实运行中实例总数
    org_overview: list[OrgOverview] = []        # 各所项目概览
    proposal_org_overview: list[OrgOverview] = []  # 各所方案概览（前端 tab 切换用）
    my_pending: list[MyPendingItem] = []           # 当前用户待办列表（项目视图）
    proposal_my_pending: list[MyPendingItem] = []   # 当前用户待办列表（方案视图）
    my_pending_total: int = 0            # 项目待办真实全量条数（P1-33：列表仅展示前 8 条，此为完整计数）
    proposal_my_pending_total: int = 0   # 方案待办真实全量条数（P1-33）
