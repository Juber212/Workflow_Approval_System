/** 任务 API —— 待办列表、详情、提交、草稿、文件上传 */
import request from './request'

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
  submitted_at: string | null
  created_at: string | null
}

/** ProgressBar 用的流程节点简要信息 */
export interface FlowNodeBrief {
  id: number
  name: string
  is_start: boolean
  is_end: boolean
  is_skipped: boolean
  status: string
  sort_order: number
}

export interface TaskFileItem {
  id: number
  original_name: string
  file_size: number | null
  uploader_name: string
  upload_type: string
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
  decided_at: string | null
}

// ==================== API ====================

export async function getTasks(params: {
  status?: string
  keyword?: string
  page?: number
  page_size?: number
}) {
  const res = await request.get('/tasks', { params })
  return res.data as { items: TaskListItem[]; total: number; page: number; page_size: number }
}

export async function getTaskDetail(id: number): Promise<TaskDetail> {
  const res = await request.get(`/tasks/${id}`)
  return res.data
}

export async function saveTaskDraft(id: number, data: { assignee_note?: string | null }) {
  const res = await request.put(`/tasks/${id}`, data)
  return res
}

export async function submitTask(id: number, data: { assignee_note?: string | null }) {
  const res = await request.post(`/tasks/${id}/submit`, data)
  return res
}

export async function uploadTaskFile(taskId: number, file: File) {
  const form = new FormData()
  form.append('file', file)
  const res = await request.post(`/tasks/${taskId}/files`, form, {
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
  window.open(blobUrl, '_blank')
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
