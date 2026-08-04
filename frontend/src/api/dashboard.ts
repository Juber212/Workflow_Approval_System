/** Dashboard API —— 首页看板全局统计 */
import request from './request'

// ==================== 类型 ====================

export interface DashboardStats {
  running_instances: number
  archived_total: number
  archived_this_month: number
  overdue_warnings: number
  total?: number  // 方案统计用：方案总数
}

export interface TaskDistItem {
  status: string
  label: string
  color: string
  count: number
}

export interface BottleneckItem {
  instance_id: number
  instance_name: string
  organization_name: string
  progress_chain: string[]
  current_node_name: string
  current_handlers: string  // 当前处理人（根据节点状态动态显示：负责人/校验人/审批人/批准人）
  priority: string
  difficulty: string
  finished_count: number
  total_nodes: number
  overdue_status: string
  all_finished: boolean
}

export interface OrgOverview {
  org_id: number
  org_name: string
  total_count: number       // 全部项目数
  running_count: number     // 运行中
  completed_count: number   // 已完成
  terminated_count: number  // 已终止
}

/** 当前用户个人待办统计 */
export interface MyTaskCounts {
  pending: number    // 待处理
  checking: number   // 待校验
  approval: number   // 待审批
}

/** 我的待办列表项 —— 合并 Task/CheckRecord/Approval 三表 */
export interface MyPendingItem {
  type: 'task' | 'check' | 'approval'
  type_label: string     // "待办" | "校验" | "审批"
  id: number             // 记录 ID，跳转 /profile/{type}/{id}
  instance_id: number
  instance_name: string
  node_name: string
  priority: string       // urgent / high / normal / low
  deadline: string | null       // ISO 格式截止时间
  is_overdue: boolean            // 是否逾期
  days_remaining: number | null  // 剩余天数（负数=已逾期）
}

export interface DashboardData {
  stats: DashboardStats
  proposal_stats: DashboardStats
  task_distribution: TaskDistItem[]
  bottleneck: BottleneckItem[]
  proposal_bottleneck: BottleneckItem[]  // 方案卡点追踪（简化列）
  overdue_list: any[]  // 保留兼容，前端不再渲染
  org_overview: OrgOverview[]        // 各所项目概览
  proposal_org_overview: OrgOverview[]  // 各所方案概览（前端 tab 切换用）
  my_task_counts: MyTaskCounts  // 当前用户个人待办计数（侧边栏角标用）
  my_pending: MyPendingItem[]           // 当前用户待办列表（项目视图）
  proposal_my_pending: MyPendingItem[]   // 当前用户待办列表（方案视图）
  my_pending_total: number  // 项目待办真实全量条数（P1-33：列表仅展示前 8 条，此为完整计数）
  proposal_my_pending_total: number  // 方案待办真实全量条数
}

// ==================== API ====================

export async function getDashboard(): Promise<DashboardData> {
  const res = await request.get('/dashboard')
  return res.data
}
