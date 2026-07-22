/** 方案 API */
import request from './request'
import type { PaginatedResponse } from './index'

export interface ProposalListItem {
  id: number
  name: string
  description: string | null
  organization_id: number
  organization_name: string  // 所属组织名称
  initiator_id: number
  initiator_name: string
  status: string
  created_at: string | null
}

export interface ProposalOrgCardItem {
  id: number
  name: string
  total_count: number
  running_count: number
  completed_count: number
  terminated_count: number
  latest_update_time: string | null
  is_current_user_org: boolean  // 是否为当前用户所属组织
}

export interface ProposalCreateRequest {
  name: string
  description?: string | null
  organization_id: number
  /** 设计人（工作节点负责人） */
  designer_id: number
  /** 方案无校验环节，仅需审批人 */
  approvers: { user_id: number }[]
  deadline?: string | null
}

/** 获取方案列表 */
export async function getProposals(params: {
  organization_id?: number
  status?: string
  keyword?: string
  page?: number
  page_size?: number
}) {
  const res = await request.get('/proposals', { params })
  return res.data as PaginatedResponse<ProposalListItem>
}

/** 获取方案组织卡片数据 */
export async function getProposalOrganizations(): Promise<{ organizations: ProposalOrgCardItem[] }> {
  const res = await request.get('/proposals/organizations')
  return res.data
}

/** 发起方案 */
export async function createProposal(data: ProposalCreateRequest) {
  const res = await request.post('/proposals', data)
  return res.data as { id: number; name: string; status: string }
}
