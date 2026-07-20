/** Dashboard API —— 首页看板全局统计 */
import request from './request'

// ==================== 类型 ====================

export interface DashboardStats {
  running_instances: number
  archived_total: number
  archived_this_month: number
  overdue_warnings: number
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
  template_name: string
  organization_name: string
  progress_chain: string[]
  current_node_name: string
  current_assignee_name: string
  priority: string
  finished_count: number
  total_nodes: number
  overdue_status: string
  all_finished: boolean
}

export interface OverdueItem {
  task_id: number
  instance_id: number
  instance_name: string
  node_name: string
  assignee_name: string
  deadline: string | null
  days_label: string
  organization_name: string
  is_overdue: boolean
}

export interface OrgOverviewInst {
  id: number
  name: string
  template_name: string
  priority: string
  current_node_name: string
  current_assignee_name: string
  status: string
}

export interface OrgOverview {
  org_id: number
  org_name: string
  running_count: number
  instances: OrgOverviewInst[]
}

export interface DashboardData {
  stats: DashboardStats
  proposal_stats: DashboardStats  // 方案统计
  task_distribution: TaskDistItem[]
  bottleneck: BottleneckItem[]
  overdue_list: OverdueItem[]
  org_overview: OrgOverview[]
}

// ==================== API ====================

export async function getDashboard(): Promise<DashboardData> {
  const res = await request.get('/dashboard')
  return res.data
}
