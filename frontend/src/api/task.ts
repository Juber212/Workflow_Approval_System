/** 任务 API —— 待办列表、详情、提交、草稿、文件上传 */
import request from './request'
import type { PaginatedResponse } from './index'
import type { SignatureSlot } from './signature'

// ==================== 类型 ====================

export interface TaskListItem {
  id: number
  instance_id: number
  instance_name: string
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
  checks: TaskCheckItem[]
  approvals: TaskApprovalItem[]
  rejected_type: string | null  // 退回类型: "check" | "approval" | null
  rejected_reason: string | null  // 退回原因
  // 节点签批配置（三个独立开关）
  require_assignee_signature: boolean
  require_checker_signature: boolean
  require_approver_signature: boolean
  signature_x: number
  signature_y: number
  signature_page: number
  current_signature_url: string | null  // 当前负责人的签名图片 URL
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
  sort_order: number
}

export interface TaskFileItem {
  id: number
  original_name: string
  mime_type: string | null  // 文件 MIME 类型，用于判断是否为 PDF
  file_size: number | null
  uploader_name: string
  upload_type: string
  folder_name: string | null  // 所属文件夹名称
  round: number
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
  return res
}

/** 提交任务 —— 支持签名 */
export async function submitTask(id: number, data: { assignee_note?: string | null; signatures?: SignatureSlot[] | null }) {
  const res = await request.post(`/tasks/${id}/submit`, data)
  return res
}

/** 预提交签名准备 —— 转换文件为 PDF 并返回文件列表，供签批弹窗预览 */
export interface PrepareSignFile {
  id: number
  original_name: string
  mime_type: string | null
  url: string
}

export async function prepareSign(taskId: number): Promise<PrepareSignFile[]> {
  const res = await request.post(`/tasks/${taskId}/prepare-sign`)
  return res.data.files  // res = { code, message, data: { files: [...] } }
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

/** 预览文件 —— 通过 fetch + Token 获取 blob 后在新标签页打开（PDF/图片）或下载（其他） */
export async function previewFile(fileId: number): Promise<void> {
  const token = localStorage.getItem('token')
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1'
  const resp = await fetch(`${baseUrl}/files/${fileId}/download`, {
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
  const token = localStorage.getItem('token')
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1'
  const resp = await fetch(`${baseUrl}/files/${fileId}/download`, {
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
  a.download = decodeURIComponent(raw)
  a.click()
  URL.revokeObjectURL(blobUrl)
}
