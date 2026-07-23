/** 批准（Endorsement）API —— 难度4级时的最终审核 */
import request from './request'

export interface EndorsementListItem {
  id: number
  instance_id: number
  instance_name: string
  node_id: number
  node_name: string
  task_id: number | null
  endorser_id: number
  status: string
  is_end_node: boolean
  round: number
  created_at: string | null
}

export interface EndorsementDetail {
  id: number
  instance_id: number
  instance_name: string
  instance_status: string
  initiator_id: number
  initiator_name: string
  priority: string
  difficulty: string
  node_id: number
  node_name: string
  node_status: string
  task_id: number | null
  endorser_id: number
  endorser_name: string
  status: string
  opinion: string | null
  round: number
  require_endorser_signature: boolean
  signature_x: number
  signature_y: number
  signature_page: number
  current_signature_url: string | null
  current_node_index: number
  total_nodes: number
  nodes: { id: number; name: string; status: string; is_start: boolean; is_end: boolean }[]
  files: { id: number; original_name: string; file_size: number; round: number }[]
  checks: { id: number; checker_id: number; status: string; opinion: string | null; decided_at: string | null }[]
  approvals: { id: number; approver_id: number; status: string; opinion: string | null; signature_applied: boolean; decided_at: string | null }[]
  decided_at: string | null
  created_at: string | null
}

/** 获取我的批准列表 */
export async function getEndorsements(params?: { type?: string }): Promise<{ items: EndorsementListItem[]; total: number }> {
  const res = await request.get('/endorsements', { params })
  return res.data.data
}

/** 获取批准详情 */
export async function getEndorsementDetail(id: number): Promise<EndorsementDetail> {
  const res = await request.get(`/endorsements/${id}`)
  return res.data.data
}

/** 批准通过 */
export async function endorse(id: number, data: {
  opinion?: string | null
  signatures?: { file_id: number; signature_x: number; signature_y: number; signature_page: number }[]
}): Promise<{ message: string }> {
  const res = await request.post(`/endorsements/${id}/approve`, data)
  return res.data.data
}

/** 批准驳回 */
export async function endorseReject(id: number, data: { opinion: string }): Promise<{ message: string }> {
  const res = await request.post(`/endorsements/${id}/reject`, data)
  return res.data.data
}
