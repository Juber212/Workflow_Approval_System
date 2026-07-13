/** 流程模板 API */
import request from './request'

// ==================== 类型 ====================

export interface OrgCardItem {
  id: number
  name: string
  template_count: number
  running_instance_count: number
}

export interface TemplateItem {
  id: number
  name: string
  description: string | null
  organization_id: number
  organization_name: string | null
  status: string
  current_version: number
  node_count: number
  instance_count: number
  can_edit: boolean
  can_publish: boolean
  can_start: boolean
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
  status: string
  current_version: number
  node_count: number
  instance_count: number
  nodes: TemplateNodeItem[]
  edges: TemplateEdgeItem[]
  versions: VersionItem[]
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
  time_limit_days: number | null
  require_file: boolean
  approvers: any
  checkers: any
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

export interface VersionItem {
  id: number
  version_number: number
  status: string
  node_count: number
  edge_count: number
  has_soft_overrides: boolean
  published_by: number | null
  published_by_name: string | null
  published_at: string | null
}

export interface TemplateListParams {
  page?: number
  page_size?: number
  organization_id?: number
  status?: string
  keyword?: string
}

// ==================== API ====================

/** 组织卡片列表 */
export async function getTemplateOrganizations(): Promise<OrgCardItem[]> {
  const res = await request.get('/templates/organizations')
  return res.data
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
  await request.post('/templates', data)
}

/** 更新模板 */
export async function updateTemplate(id: number, data: { name: string; description?: string | null }) {
  await request.put(`/templates/${id}`, data)
}

/** 删除模板 */
export async function deleteTemplate(id: number) {
  await request.delete(`/templates/${id}`)
}

/** 发布模板 */
export async function publishTemplate(id: number) {
  const res = await request.post(`/templates/${id}/publish`)
  return res.data as { version_id: number; version_number: number; node_count: number; edge_count: number }
}

/** 停用模板 */
export async function disableTemplate(id: number) {
  const res = await request.post(`/templates/${id}/disable`)
  return res.data
}

/** 创建新版本（从已发布/已停用复制为草稿） */
export async function newVersionTemplate(id: number) {
  const res = await request.post(`/templates/${id}/new-version`)
  return res.data as { id: number; status: string; current_version: number }
}
