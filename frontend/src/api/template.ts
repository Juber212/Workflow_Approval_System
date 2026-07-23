/** 项目模板 API —— 简化版：无版本、无状态 */
import request from './request'
import type { PaginatedResponse } from './index'

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
  file_folders: Array<{ name: string; required: boolean; file_count: number | null }> | null  // 文件提交文件夹配置
  approvers: Array<{ user_id: number }> | null
  approvers_names: string[] | null
  checkers: Array<{ user_id: number }> | null
  checkers_names: string[] | null
  approval_strategy: string
  require_assignee_signature: boolean
  require_checker_signature: boolean
  require_approver_signature: boolean
  signature_x: number
  signature_y: number
  signature_page: number
  position_x: number
  position_y: number
  sort_order: number
}

/** 创建模板响应 */
export interface TemplateCreated { id: number; name: string }

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
  return res.data as PaginatedResponse<TemplateItem>
}

/** 模板详情 */
export async function getTemplateDetail(id: number): Promise<TemplateDetail> {
  const res = await request.get(`/templates/${id}`)
  return res.data
}

/** 创建模板 */
export async function createTemplate(data: { name: string; description?: string | null; organization_id: number }) {
  const res = await request.post('/templates', data)
  return res.data as TemplateCreated
}

/** 更新模板 */
export async function updateTemplate(id: number, data: { name: string; description?: string | null }) {
  await request.put(`/templates/${id}`, data)
}

/** 删除模板 */
export async function deleteTemplate(id: number) {
  await request.delete(`/templates/${id}`)
}

// ─── 文件模板 ───────────────────────────────────────────────

/** 文件模板列表项 */
export interface DocTemplateItem {
  id: number
  name: string           // 显示名称
  original_name: string  // 原始文件名
  file_size: number
  file_type: string      // "docx" | "xlsx"
  created_at: string | null
}

/** 文件模板列表响应（含已关联 + 未关联） */
export interface DocTemplateListResponse {
  linked: DocTemplateItem[]           // 已关联到此流程模板的
  available: DocTemplateItem[]        // 组织内可用但未关联的
  available_variables: string[]       // 可用变量列表
}

/** 获取模板的文件模板列表（已关联 + 组织内可用） */
export async function getDocTemplates(templateId: number): Promise<DocTemplateListResponse> {
  const res = await request.get(`/templates/${templateId}/documents`)
  return res.data
}

/** 关联文件模板到流程模板 */
export async function linkDocTemplates(templateId: number, docIds: number[]): Promise<{ linked: number }> {
  const res = await request.post(`/templates/${templateId}/documents/link`, docIds)
  return res.data
}

/** 取消文件模板与流程模板的关联 */
export async function unlinkDocTemplate(templateId: number, docId: number): Promise<void> {
  await request.delete(`/templates/${templateId}/documents/${docId}/link`)
}

/** 下载文件模板（自动替换占位符）—— 通过 fetch + blob 触发浏览器下载 */
export async function downloadDocTemplate(taskId: number, docId: number): Promise<void> {
  const token = localStorage.getItem('token')
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1'
  const resp = await fetch(`${baseUrl}/tasks/${taskId}/document-templates/${docId}/download`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!resp.ok) {
    const errData = await resp.json().catch(() => ({}))
    throw new Error((errData as any).message || '下载失败')
  }
  const blob = await resp.blob()
  const blobUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = blobUrl
  // 从响应头解析文件名
  const disposition = resp.headers.get('Content-Disposition') || ''
  const starMatch = disposition.match(/filename\*=UTF-8''([^;\s]+)/)
  const plainMatch = disposition.match(/filename="?([^";\s]+)"?/)
  const raw = starMatch?.[1] || plainMatch?.[1] || `template-${docId}`
  a.download = decodeURIComponent(raw)
  a.click()
  URL.revokeObjectURL(blobUrl)
}

// ─── 管理员文件模板管理 ──────────────────────────────────────

/** 管理员文档模板列表项（含组织名） */
export interface AdminDocTemplateItem extends DocTemplateItem {
  organization_id: number
  organization_name: string
}

/** 管理员文档模板列表响应 */
export interface AdminDocTemplateListResponse {
  items: AdminDocTemplateItem[]
  total: number
  page: number
  page_size: number
}

/** 管理员获取所有文件模板 */
export async function getAdminDocTemplates(params: {
  organization_id?: number
  keyword?: string
  page?: number
  page_size?: number
} = {}): Promise<AdminDocTemplateListResponse> {
  const res = await request.get('/admin/document-templates', { params })
  return res.data
}

/** 管理员上传文件模板 */
export async function adminUploadDocTemplate(
  file: File,
  organizationId: number,
  name?: string,
): Promise<{ id: number; name: string; file_type: string; organization_id: number }> {
  const form = new FormData()
  form.append('file', file)
  const params = new URLSearchParams()
  params.set('organization_id', String(organizationId))
  if (name) params.set('name', name)
  const res = await request.post(`/admin/document-templates?${params}`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

/** 管理员删除文件模板 */
export async function deleteAdminDocTemplate(docId: number): Promise<void> {
  await request.delete(`/admin/document-templates/${docId}`)
}

/** 管理员获取组织列表 */
export async function getAdminOrganizations(): Promise<{ id: number; name: string }[]> {
  const res = await request.get('/admin/organizations')
  return res.data.items
}
