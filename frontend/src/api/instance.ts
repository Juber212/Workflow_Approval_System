/** 流程实例 API */
import request from './request'

// ==================== 类型 ====================

/** 节点覆盖配置 */
export interface NodeOverride {
  node_id: number
  assignee_id?: number | null
  deadline?: string | null
  checkers?: { user_id: number }[]
  approvers?: { user_id: number }[]
  skip?: boolean
}

/** 发起实例请求 */
export interface CreateInstanceData {
  template_id: number
  version_id: number
  name: string
  description?: string | null
  priority?: string
  node_overrides?: NodeOverride[]
}

/** 发起实例响应 */
export interface InstanceCreated {
  id: number
  name: string
  template_id: number
  version_id: number
  organization_id: number
  initiator_id: number
  priority: string
  status: string
  nodes: {
    id: number
    name: string
    is_start: boolean
    is_end: boolean
    is_skipped: boolean
    status: string
    sort_order: number
  }[]
  initiated_at: string | null
}

// ==================== API ====================

/** 发起流程实例 */
export async function createInstance(data: CreateInstanceData): Promise<InstanceCreated> {
  const res = await request.post('/instances', data)
  return res.data
}
