/** 批准 API —— 难度4级的最终审核环节 */
import request from './request'
import type { SignatureSlot } from './signature'

/** 批准列表项 */
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

/** 批准详情 */
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
  nodes: { id: number; name: string; is_start: boolean; is_end: boolean; status: string }[]
  files: { id: number; original_name: string; file_size: number | null; round: number }[]
  checks: { id: number; checker_id: number; status: string; opinion: string | null; decided_at: string | null }[]
  approvals: { id: number; approver_id: number; status: string; opinion: string | null; signature_applied: boolean; decided_at: string | null }[]
  decided_at: string | null
  created_at: string | null
}

/** 获取我的批准列表 */
export async function getEndorsements(params: { type?: string } = {}) {
  const res = await request.get('/endorsements', { params })
  return res.data as { items: EndorsementListItem[]; total: number }
}

/** 获取批准详情 */
export async function getEndorsementDetail(id: number): Promise<EndorsementDetail> {
  const res = await request.get(`/endorsements/${id}`)
  return res.data
}

/** 批准通过 —— 支持多签名 */
export async function endorseApprove(
  id: number,
  opinion?: string | null,
  signatures?: SignatureSlot[] | null,
) {
  const res = await request.post(`/endorsements/${id}/approve`, {
    opinion,
    signatures,
  })
  return res
}

/** 批准驳回 */
export async function endorseReject(id: number, opinion: string) {
  const res = await request.post(`/endorsements/${id}/reject`, { opinion })
  return res
}
