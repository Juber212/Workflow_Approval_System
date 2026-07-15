/** 流程模板 API —— 简化版：无版本、无状态 */
import request from './request'

// ==================== 类型 ====================

export interface OrgCardItem {
  id: number
  name: string
  template_count: number
  running_instance_count: number
  latest_update_time: string | null
  is_current_user_org: boolean
}

export interface OrgCardListResponse {
  organizations: OrgCardItem[]
  total_running_instances: number
}

export interface TemplateItem {
  id: number
  name: string
  description: string | null
  organization_id: number
  organization_name: string | null
  node_count: number
  instance_count: number
  created_by: number
  created_by_name: string | null
  created_at: string | null
  updated_at: string | null
}

export interface TemplateDetail {
  id: number
  name: string
  description: string | null
  organization_id: number
  organization_name: string | null
  node_count: number
  instance_count: number
  nodes: TemplateNodeItem[]
  edges: TemplateEdgeItem[]
  created_by: number
  created_by_name: string | null
  created_at: string | null
  updated_at: string | null
}

export interface TemplateNodeItem {
  id: number
  name: string
  is_start: boolean
  is_end: boolean
  assignee_id: number | null
  assignee_name: string | null
  time_limit_days: number | null
  require_file: boolean
  approvers: any
  approvers_names: string[] | null
  checkers: any
  checkers_names: string[] | null
  approval_strategy: string
  is_optional: boolean
  position_x: number
  position_y: number
  sort_order: number
}

export interface TemplateEdgeItem {
  id: number
  source_node_id: number
  target_node_id: number
}

export interface TemplateListParams {
  page?: number
  page_size?: number
  organization_id?: number
  keyword?: string
}

// ==================== API ====================

/** 组织卡片列表 */
export async function getTemplateOrganizations(): Promise<OrgCardListResponse> {
  const res = await request.get('/templates/organizations')
  const payload = res.data
  if (Array.isArray(payload)) {
    return { organizations: payload, total_running_instances: 0 }
  }
  return payload
}

/** 模板列表 */
export async function getTemplates(params: TemplateListParams = {}) {
  const res = await request.get('/templates', { params })
  return res.data as { items: TemplateItem[]; total: number; page: number; page_size: number }
}

/** 模板详情 */
export async function getTemplateDetail(id: number): Promise<TemplateDetail> {
  const res = await request.get(`/templates/${id}`)
  return res.data
}

/** 创建模板 */
export async function createTemplate(data: { name: string; description?: string | null; organization_id: number }) {
  const res = await request.post('/templates', data)
  return res.data as { id: number; name: string }
}

/** 更新模板 */
export async function updateTemplate(id: number, data: { name: string; description?: string | null }) {
  await request.put(`/templates/${id}`, data)
}

/** 删除模板 */
export async function deleteTemplate(id: number) {
  await request.delete(`/templates/${id}`)
}
