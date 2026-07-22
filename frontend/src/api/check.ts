/** 校验 API */
import request from './request'
import type { PaginatedResponse } from './index'
import type { SignatureSlot } from './signature'

export interface CheckListItem {
  id: number
  instance_id: number
  instance_name: string
  node_id: number
  node_name: string
  task_id: number
  submitter_name: string
  status: string
  round: number
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
  nodes: { id: number; name: string; is_start: boolean; is_end: boolean; status: string; sort_order: number }[]
  files: { id: number; original_name: string; mime_type: string | null; file_size: number | null; uploader_name: string; upload_type: string; round: number; created_at: string | null }[]
  assignee_note: string | null
  check_progress: { id: number; checker_id: number; checker_name: string; status: string; opinion: string | null; round: number; decided_at: string | null }[]
  // 节点签批配置
  require_assignee_signature: boolean
  require_checker_signature: boolean
  require_approver_signature: boolean
  signature_x: number
  signature_y: number
  signature_page: number
  current_signature_url: string | null
  decided_at: string | null
  created_at: string | null
}

export async function getChecks(params: { status?: string; keyword?: string; page?: number; page_size?: number }) {
  const res = await request.get('/checks', { params })
  return res.data as PaginatedResponse<CheckListItem>
}

export async function getCheckDetail(id: number): Promise<CheckDetail> {
  const res = await request.get(`/checks/${id}`)
  return res.data
}

/** 校验通过 —— 支持签名 */
export async function passCheck(id: number, opinion?: string | null, signatures?: SignatureSlot[] | null) {
  const res = await request.post(`/checks/${id}/pass`, { opinion, signatures })
  return res
}

export async function returnCheck(id: number, opinion: string) {
  const res = await request.post(`/checks/${id}/return`, { opinion })
  return res
}
