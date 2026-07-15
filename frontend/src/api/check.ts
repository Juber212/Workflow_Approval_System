/** 校验 API */
import request from './request'

export interface CheckListItem {
  id: number
  instance_id: number
  instance_name: string
  node_id: number
  node_name: string
  task_id: number
  submitter_name: string
  status: string
  created_at: string | null
}

export interface CheckDetail {
  id: number
  instance_id: number
  instance_name: string
  instance_status: string
  initiator_id: number
  initiator_name: string
  submitter_id: number
  submitter_name: string
  priority: string
  node_id: number
  node_name: string
  task_id: number
  checker_id: number
  checker_name: string
  status: string
  opinion: string | null
  total_nodes: number
  current_node_index: number
  nodes: { id: number; name: string; is_start: boolean; is_end: boolean; is_skipped: boolean; status: string; sort_order: number }[]
  files: { id: number; original_name: string; file_size: number | null; uploader_name: string; upload_type: string; round: number; created_at: string | null }[]
  assignee_note: string | null
  check_progress: { id: number; checker_id: number; checker_name: string; status: string; opinion: string | null; decided_at: string | null }[]
  decided_at: string | null
  created_at: string | null
}

export async function getChecks(params: { status?: string; keyword?: string; page?: number; page_size?: number }) {
  const res = await request.get('/checks', { params })
  return res.data as { items: CheckListItem[]; total: number; page: number; page_size: number }
}

export async function getCheckDetail(id: number): Promise<CheckDetail> {
  const res = await request.get(`/checks/${id}`)
  return res.data
}

export async function passCheck(id: number, opinion?: string | null) {
  const res = await request.post(`/checks/${id}/pass`, { opinion })
  return res
}

export async function returnCheck(id: number, opinion: string) {
  const res = await request.post(`/checks/${id}/return`, { opinion })
  return res
}
