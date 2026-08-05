/** 任务 API —— 待办列表、详情、提交、草稿、文件上传 */
import request, { getToken, apiBase } from './request'
import type { PaginatedResponse } from './index'
import type { SignatureSlot } from './signature'
import type { DocTemplateItem } from './template'

// ==================== 类型 ====================

export interface TaskListItem {
  id: number
  instance_id: number
  instance_name: string
  template_name: string  // 所属模板名称
  node_id: number
  node_name: string
  initiator_name: string
  status: string
  deadline: string | null
  is_overdue: boolean
  days_remaining: number | null
  priority: string
  created_at: string | null
}

export interface TaskDetail {
  id: number
  instance_id: number
  instance_name: string
  instance_status: string
  initiator_id: number
  initiator_name: string
  priority: string
  difficulty: string  // 难度等级（1-4）
  node_id: number
  node_name: string
  node_description: string | null
  node_status: string
  assignee_id: number
  assignee_name: string
  status: string
  assignee_note: string | null
  require_file: boolean
  file_folders: Array<{ name: string; required: boolean; file_count: number | null }> | null  // 文件提交文件夹配置
  time_limit_days: number | null
  deadline: string | null
  round: number
  total_nodes: number
  current_node_index: number
  nodes: FlowNodeBrief[]
  files: TaskFileItem[]
  node_files: TaskFileItem[]  // 仅本节点文件（签批用，后端过滤）
  checks: TaskCheckItem[]
  approvals: TaskApprovalItem[]
  endorsements: Array<{ id: number; endorser_id: number; status: string; opinion?: string | null }>  // 批准记录（仅难度4时存在）
  rejected_type: string | null  // 退回类型: "check" | "approval" | null
  rejected_reason: string | null  // 退回原因
  // 节点签批配置（三个独立开关）
  require_assignee_signature: boolean
  require_checker_signature: boolean
  require_approver_signature: boolean
  require_endorser_signature: boolean
  signature_x: number
  signature_y: number
  signature_page: number
  current_signature_url: string | null  // 当前负责人的签名图片 URL
  role_signature: { x: number; y: number } | null  // 角色维度签名默认坐标
  submitted_at: string | null
  created_at: string | null
}

/** ProgressBar 用的流程节点简要信息 */
export interface FlowNodeBrief {
  id: number
  name: string
  is_start: boolean
  is_end: boolean
  status: string
  /** 排序序号（endorse 详情接口可能不返回；进度条分叉/汇合分组用，缺省按 0） */
  sort_order?: number
}

export interface TaskFileItem {
  id: number
  original_name: string
  mime_type: string | null
  file_size: number | null
  uploader_name: string
  upload_type: string
  folder_name: string | null
  round: number
  node_id: number | null   // 所属节点 ID
  node_name: string        // 所属节点名称
  conversion_status?: string  // PDF 转换状态（上传后 pending 待转换，提交后才转）
  created_at: string | null
}

export interface TaskCheckItem {
  id: number
  checker_id: number
  checker_name: string
  status: string
  opinion: string | null
  decided_at: string | null
}

export interface TaskApprovalItem {
  id: number
  approver_id: number
  approver_name: string
  status: string
  opinion: string | null
  signature_applied: boolean
  signature_x: number | null
  signature_y: number | null
  signature_page: number | null
  decided_at: string | null
}

// ==================== API ====================

export async function getTasks(params: {
  status?: string
  keyword?: string
  page?: number
  page_size?: number
  type?: string  // "project" 或 "proposal"
}) {
  const res = await request.get('/tasks', { params })
  return res.data as PaginatedResponse<TaskListItem>
}

export async function getTaskDetail(id: number): Promise<TaskDetail> {
  const res = await request.get(`/tasks/${id}`)
  return res.data
}

export async function saveTaskDraft(id: number, data: { assignee_note?: string | null }) {
  const res = await request.put(`/tasks/${id}`, data)
  return res.data
}

/** 提交任务 —— 支持签名 */
export async function submitTask(id: number, data: { assignee_note?: string | null; signatures?: SignatureSlot[] | null }) {
  const res = await request.post(`/tasks/${id}/submit`, data)
  return res.data
}

/** 预提交签名准备 —— 转换文件为 PDF 并返回文件列表，供签批弹窗预览 */
export interface PrepareSignFile {
  id: number
  original_name: string
  mime_type: string | null
  conversion_status: string  // ready | pending | converting | failed
  url: string
}

export interface PrepareSignResponse {
  files: PrepareSignFile[]
  conversion_pending: boolean  // true = 需要等待后台转换
  file_ids: number[]
}

export async function prepareSign(taskId: number): Promise<PrepareSignResponse> {
  const res = await request.post(`/tasks/${taskId}/prepare-sign`)
  return res.data  // { code, message, data: { files, conversion_pending, file_ids } }
}

/** 文件转换状态查询响应 */
export interface FileStatusItem {
  id: number
  original_name: string
  conversion_status: string
  conversion_error: string | null
}

export interface FilesStatusResponse {
  files: FileStatusItem[]
  all_ready: boolean
  has_failed: boolean
}

/** 轮询文件转换状态（WebSocket 未收到通知时的兜底方案） */
export async function getFilesStatus(taskId: number): Promise<FilesStatusResponse> {
  const res = await request.get(`/tasks/${taskId}/files/status`)
  return res.data
}

/** 上传任务文件 —— 支持指定文件夹 */
export async function uploadTaskFile(taskId: number, file: File, folderName?: string) {
  const form = new FormData()
  form.append('file', file)
  const params = folderName ? `?folder_name=${encodeURIComponent(folderName)}` : ''
  const res = await request.post(`/tasks/${taskId}/files${params}`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

export async function deleteTaskFile(taskId: number, fileId: number) {
  await request.delete(`/tasks/${taskId}/files/${fileId}`)
}

/** 文件下载 URL —— 预览/下载与签批弹窗共用（P2-2：统一 baseUrl 拼接，避免硬编码） */
export function fileDownloadUrl(fileId: number): string {
  return `${apiBase()}/files/${fileId}/download`
}

/** 预览文件 —— 通过 fetch + Token 获取 blob 后在新标签页打开（PDF/图片）或下载（其他） */
export async function previewFile(fileId: number): Promise<void> {
  const token = getToken()
  const resp = await fetch(fileDownloadUrl(fileId), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!resp.ok) {
    throw new Error('预览失败')
  }
  const blob = await resp.blob()
  const blobUrl = URL.createObjectURL(blob)
  const previewWindow = window.open(blobUrl, '_blank')
  // 延迟释放 Blob URL（等待新窗口加载完成）
  if (previewWindow) {
    setTimeout(() => {
      URL.revokeObjectURL(blobUrl)
    }, 60000)  // 1分钟后释放，足够浏览器加载
  } else {
    URL.revokeObjectURL(blobUrl)
  }
}

/** 下载文件 —— 获取文件 blob 后触发浏览器保存对话框 */
export async function downloadFile(fileId: number): Promise<void> {
  const token = getToken()
  const resp = await fetch(fileDownloadUrl(fileId), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!resp.ok) {
    throw new Error('下载失败')
  }
  const blob = await resp.blob()
  const blobUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = blobUrl
  // 从响应头解析文件名（优先取 filename*=UTF-8'' 编码名，兜底取 filename=）
  const disposition = resp.headers.get('Content-Disposition') || ''
  const starMatch = disposition.match(/filename\*=UTF-8''([^;\s]+)/)
  const plainMatch = disposition.match(/filename="?([^";\s]+)"?/)
  const raw = starMatch?.[1] || plainMatch?.[1] || `file-${fileId}`
  // 文件名含非法 % 序列时 decodeURIComponent 抛 URIError → 兜底用原始名
  try { a.download = decodeURIComponent(raw) } catch { a.download = raw }
  a.click()
  URL.revokeObjectURL(blobUrl)
}

// ==================== 文件模板（任务处理页用） ====================

/** 模板包（分类）—— 含内部模板列表 */
export interface TaskTemplateCategory {
  id: number
  name: string
  description: string | null
  document_count: number
  documents: DocTemplateItem[]
}

/** 任务可用文件模板响应 */
export interface TaskDocTemplatesResponse {
  templates: DocTemplateItem[]       // 未归包的散模板
  categories: TaskTemplateCategory[] // 模板包列表
}

/** 获取任务可用的文件模板列表（含模板包） */
export async function getTaskDocTemplates(taskId: number): Promise<TaskDocTemplatesResponse> {
  const res = await request.get(`/tasks/${taskId}/document-templates`)
  return res.data
}

/** 下载模板包 ZIP（填充占位符后打包） */
export async function downloadTaskTemplateZip(taskId: number, categoryId: number): Promise<void> {
  const token = getToken()
  const resp = await fetch(
    `${apiBase()}/tasks/${taskId}/document-templates/download-zip?category_id=${categoryId}`,
    { headers: token ? { Authorization: `Bearer ${token}` } : {} },
  )
  if (!resp.ok) throw new Error('下载失败')
  const blob = await resp.blob()
  const blobUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = blobUrl
  const disposition = resp.headers.get('Content-Disposition') || ''
  const starMatch = disposition.match(/filename\*=UTF-8''([^;\s]+)/)
  const plainMatch = disposition.match(/filename="?([^";\s]+)"?/)
  a.download = decodeURIComponent(starMatch?.[1] || plainMatch?.[1] || 'templates.zip')
  a.click()
  URL.revokeObjectURL(blobUrl)
}
