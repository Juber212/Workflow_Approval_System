/** 项目模板 API —— 简化版：无版本、无状态 */
import request, { getToken, apiBase } from './request'
import type { PaginatedResponse } from './index'

// ==================== 类型 ====================

export interface OrgCardItem {
  id: number
  name: string
  template_count: number
  running_instance_count: number
  completed_instance_count: number   // 已完成项目数
  terminated_instance_count: number  // 已终止项目数
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
  type: string  // 模板类型: project / proposal
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
  type: string  // 模板类型: project / proposal
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
  require_endorser_signature: boolean
  endorser_id: number | null
  endorser_name: string | null
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
  /** 折线路径点串（模板详情接口可能返回，设计器恢复路由形状用） */
  points?: string | null
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

/** 检查模板名称是否可用（同一组织下不可重名） */
export async function checkTemplateName(organizationId: number, name: string): Promise<boolean> {
  const res = await request.get('/template-name-check', { params: { organization_id: organizationId, name } })
  return res.data?.available ?? true
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

/** 分类（模板包）摘要 —— 列表展示用，不含分类内模板详情 */
export interface TemplateCategorySummary {
  id: number
  name: string
  description: string | null
  document_count: number  // 分类下文件模板数量
}

/** 已关联分类（含分类内模板详情）—— 后端 GET /templates/{id}/documents 的 linked_categories 必带 documents，发起弹窗勾选联动依赖 */
export interface LinkedTemplateCategory extends TemplateCategorySummary {
  documents: DocTemplateItem[]
}

/** 文件模板列表响应（含已关联 + 未关联 + 分类） */
export interface DocTemplateListResponse {
  linked: DocTemplateItem[]                 // 已关联的单个模板
  linked_categories: LinkedTemplateCategory[]  // 已关联的分类（模板包，必带 documents）
  available: DocTemplateItem[]              // 组织内可用但未关联的单个模板
  available_categories: TemplateCategorySummary[]  // 组织内可用但未关联的分类
  available_variables: string[]             // 可用变量列表
}

/** 获取模板的文件模板列表（已关联 + 分类 + 组织内可用） */
export async function getDocTemplates(templateId: number): Promise<DocTemplateListResponse> {
  const res = await request.get(`/templates/${templateId}/documents`)
  return res.data
}

/** 关联文件模板或分类到流程模板 */
export async function linkDocTemplates(
  templateId: number,
  docIds?: number[],
  categoryIds?: number[],
): Promise<{ linked_docs: number; linked_categories: number }> {
  const res = await request.post(`/templates/${templateId}/documents/link`, {
    doc_ids: docIds || [],
    category_ids: categoryIds || [],
  })
  return res.data
}

/** 取消文件模板或分类与流程模板的关联 */
export async function unlinkDocTemplate(
  templateId: number,
  linkType: 'document' | 'category',
  linkId: number,
): Promise<void> {
  await request.delete(`/templates/${templateId}/documents/${linkType}/${linkId}/link`)
}

/** 下载文件模板（自动替换占位符）—— 通过 fetch + blob 触发浏览器下载 */
export async function downloadDocTemplate(taskId: number, docId: number): Promise<void> {
  const token = getToken()
  const resp = await fetch(`${apiBase()}/tasks/${taskId}/document-templates/${docId}/download`, {
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
  // 文件名含非法 % 序列时 decodeURIComponent 抛 URIError → 兜底用原始名
  try { a.download = decodeURIComponent(raw) } catch { a.download = raw }
  a.click()
  URL.revokeObjectURL(blobUrl)
}

/** 批量下载文件模板 ZIP（填充占位符后打包） */
export async function downloadTemplatesZip(
  templateId: number,
  docIds: number[],
  instanceId: number,
  nodeId?: number,
): Promise<void> {
  const token = getToken()
  const params = new URLSearchParams()
  params.set('doc_ids', docIds.join(','))
  params.set('instance_id', String(instanceId))
  if (nodeId) params.set('node_id', String(nodeId))
  const resp = await fetch(`${apiBase()}/templates/${templateId}/download-zip?${params}`, {
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
  a.download = 'templates.zip'
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

/** 管理员上传文件模板（支持选择分类） */
export async function adminUploadDocTemplate(
  file: File,
  organizationId: number,
  name?: string,
  categoryIds?: number[],
): Promise<{ id: number; name: string; file_type: string; organization_id: number }> {
  const form = new FormData()
  form.append('file', file)
  const params = new URLSearchParams()
  params.set('organization_id', String(organizationId))
  if (name) params.set('name', name)
  if (categoryIds?.length) params.set('category_ids', categoryIds.join(','))
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

// ─── 管理员：模板分类（模板包）管理 ──────────────────────────────

/** 分类列表项 */
export interface TemplateCategoryItem {
  id: number
  organization_id: number
  organization_name: string | null
  name: string
  description: string | null
  document_count: number
  created_by: number
  created_by_name: string | null
  created_at: string | null
  updated_at: string | null
}

/** 分类详情（含内部文件模板） */
export interface TemplateCategoryDetail extends TemplateCategoryItem {
  documents: DocTemplateItem[]
}

/** 管理员获取分类列表 */
export async function getAdminCategories(params: {
  organization_id?: number
  keyword?: string
  page?: number
  page_size?: number
} = {}): Promise<PaginatedResponse<TemplateCategoryItem>> {
  const res = await request.get('/admin/template-categories', { params })
  return res.data
}

/** 管理员创建分类 */
export async function createAdminCategory(data: {
  name: string
  description?: string | null
  organization_id: number
}): Promise<{ id: number; name: string }> {
  const res = await request.post('/admin/template-categories', data)
  return res.data
}

/** 管理员获取分类详情 */
export async function getAdminCategoryDetail(categoryId: number): Promise<TemplateCategoryDetail> {
  const res = await request.get(`/admin/template-categories/${categoryId}`)
  return res.data
}

/** 获取分类详情（含分类内文件模板列表）—— 普通用户可调用（仅本组织，非管理员只读） */
export async function getCategoryDetail(categoryId: number): Promise<TemplateCategoryDetail> {
  const res = await request.get(`/template-categories/${categoryId}`)
  return res.data
}

/** 管理员更新分类 */
export async function updateAdminCategory(
  categoryId: number,
  data: { name: string; description?: string | null },
): Promise<void> {
  await request.put(`/admin/template-categories/${categoryId}`, data)
}

/** 管理员删除分类 */
export async function deleteAdminCategory(categoryId: number): Promise<void> {
  await request.delete(`/admin/template-categories/${categoryId}`)
}

/** 管理员将文件模板加入分类 */
export async function linkDocsToCategory(categoryId: number, docIds: number[]): Promise<{ linked: number }> {
  const res = await request.post(`/admin/template-categories/${categoryId}/documents`, { doc_ids: docIds })
  return res.data
}

/** 管理员从分类中移除文件模板 */
export async function unlinkDocsFromCategory(categoryId: number, docIds: number[]): Promise<{ removed: number }> {
  const res = await request.delete(`/admin/template-categories/${categoryId}/documents`, { data: { doc_ids: docIds } })
  return res.data
}
