/** 审批 API */
import request from './request'
import type { PaginatedResponse } from './index'

export interface ApprovalListItem {
  id: number
  instance_id: number
  instance_name: string
  node_id: number
  node_name: string
  task_id: number | null
  approver_id: number
  status: string
  is_end_node: boolean
  round: number
  created_at: string | null
}

export interface ApprovalDetail {
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
  task_id: number | null
  approver_id: number
  approver_name: string
  status: string
  opinion: string | null
  is_end_node: boolean
  total_nodes: number
  current_node_index: number
  nodes: { id: number; name: string; is_start: boolean; is_end: boolean; status: string; sort_order: number }[]
  files: { id: number; original_name: string; file_size: number | null; node_id: number | null; node_name: string; uploader_name: string; upload_type: string; round: number; created_at: string | null }[]
  check_progress: { id: number; checker_id: number; checker_name: string; status: string; opinion: string | null; round: number; decided_at: string | null }[]
  approval_progress: { id: number; approver_id: number; approver_name: string; status: string; opinion: string | null; signature_applied: boolean; round: number; decided_at: string | null }[]
  reject_target_nodes: { id: number; name: string; sort_order: number; status: string }[]
  signature_applied: boolean
  // 节点签批配置
  require_signature: boolean
  signature_x: number
  signature_y: number
  signature_page: number
  current_signature_url: string | null
  decided_at: string | null
  created_at: string | null
}

export async function getApprovals(params: { status?: string; keyword?: string; page?: number; page_size?: number; type?: string }) {
  const res = await request.get('/approvals', { params })
  return res.data as PaginatedResponse<ApprovalListItem>
}

export async function getApprovalDetail(id: number): Promise<ApprovalDetail> {
  const res = await request.get(`/approvals/${id}`)
  return res.data
}

/** 审批签批位置参数 */
export interface SignaturePosition {
  signature_x?: number | null
  signature_y?: number | null
  signature_page?: number | null
}

export async function approveApproval(
  id: number,
  opinion?: string | null,
  sigPos?: SignaturePosition,
) {
  const res = await request.post(`/approvals/${id}/approve`, {
    opinion,
    signature_x: sigPos?.signature_x ?? null,
    signature_y: sigPos?.signature_y ?? null,
    signature_page: sigPos?.signature_page ?? null,
  })
  return res
}

export async function rejectApproval(id: number, opinion: string, target_node_id?: number | null) {
  const res = await request.post(`/approvals/${id}/reject`, { opinion, target_node_id })
  return res
}
