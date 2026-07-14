/** 任务 API —— 待办列表、详情、提交、草稿、文件上传 */
import request from './request'

// ==================== 类型 ====================

export interface TaskListItem {
  id: number
  instance_id: number
  instance_name: string
  node_id: number
  node_name: string
  template_name: string
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
  files: TaskFileItem[]
  checks: TaskCheckItem[]
  approvals: TaskApprovalItem[]
  submitted_at: string | null
  created_at: string | null
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
