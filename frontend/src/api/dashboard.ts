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
  current_assignee_name: string
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
  total_count: number     // 全部项目数
  running_count: number   // 运行中
  completed_count: number // 已完成
}

/** 当前用户个人待办统计 */
export interface MyTaskCounts {
  pending: number    // 待处理
  checking: number   // 待校验
  approval: number   // 待审批
}

export interface DashboardData {
  stats: DashboardStats
  proposal_stats: DashboardStats
  task_distribution: TaskDistItem[]
  bottleneck: BottleneckItem[]
  overdue_list: any[]  // 保留兼容，前端不再渲染
  org_overview: OrgOverview[]
  my_task_counts: MyTaskCounts  // 当前用户个人待办
}

// ==================== API ====================

export async function getDashboard(): Promise<DashboardData> {
  const res = await request.get('/dashboard')
  return res.data
}
