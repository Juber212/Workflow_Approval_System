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
  name: string
  description?: string | null
  priority?: string
  node_overrides?: NodeOverride[]
}

/** 发起实例响应 */
export interface InstanceCreated {
  id: number
  name: string
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

// ==================== 实例列表 ====================

/** 实例列表查询参数 */
export interface InstanceListParams {
  organization_id?: number
  status?: string
  priority?: string
  keyword?: string
  page?: number
  page_size?: number
}

/** 实例列表项 */
export interface InstanceListItem {
  id: number
  name: string
  organization_id: number
  organization_name: string
  initiator_id: number
  initiator_name: string
  priority: string
  status: string
  archive_status: string | null
  current_node_index: number
  total_nodes: number
  current_assignee_name: string | null
  initiated_at: string | null
  completed_at: string | null
  terminated_at: string | null
}

/** 实例列表响应 */
export interface InstanceListResponse {
  items: InstanceListItem[]
  total: number
  page: number
  page_size: number
}

// ==================== 实例详情 ====================

/** 节点文件简要 */
export interface NodeFileBrief {
  id: number
  original_name: string
  file_size: number | null
  uploader_id: number
  uploader_name: string
  upload_type: string
  round: number
  created_at: string | null
}

/** 校验记录简要 */
export interface CheckRecordBrief {
  id: number
  checker_id: number
  checker_name: string
  status: string
  opinion: string | null
  decided_at: string | null
}

/** 审批记录简要 */
export interface ApprovalBrief {
  id: number
  approver_id: number
  approver_name: string
  status: string
  opinion: string | null
  signature_applied: boolean
  decided_at: string | null
}

/** 实例详情中的节点信息 */
export interface DetailNodeInfo {
  id: number
  name: string
  is_start: boolean
  is_end: boolean
  is_optional: boolean
  is_skipped: boolean
  status: string
  sort_order: number
  round: number
  assignee_id: number | null
  assignee_name: string | null
  deadline: string | null
  time_limit_days: number | null
  checkers: { user_id: number; user_name?: string }[] | null
  approvers: { user_id: number; user_name?: string }[] | null
  require_file: boolean
  approval_strategy: string
  started_at: string | null
  completed_at: string | null
  files: NodeFileBrief[]
  checks: CheckRecordBrief[]
  approvals: ApprovalBrief[]
}

/** 操作日志项 */
export interface LogItemBrief {
  id: number
  operator_type: string
  operator_id: number | null
  operator_name: string | null
  node_id: number | null
  operation_type: string
  round: number
  description: string
  detail: Record<string, any> | null
  created_at: string | null
}

/** 实例详情完整响应 */
export interface InstanceDetailResponse {
  id: number
  name: string
  description: string | null
  organization_id: number
  organization_name: string
  initiator_id: number
  initiator_name: string
  priority: string
  status: string
  archive_status: string | null
  termination_reason: string | null
  current_node_index: number
  total_nodes: number
  initiated_at: string | null
  completed_at: string | null
  terminated_at: string | null
  nodes: DetailNodeInfo[]
  logs: { items: LogItemBrief[]; total: number } | null
}

// ==================== API ====================

/** 发起流程实例 */
export async function createInstance(data: CreateInstanceData): Promise<InstanceCreated> {
  const res = await request.post('/instances', data)
  return res.data
}

/** 查询实例列表 */
export async function getInstances(params: InstanceListParams = {}): Promise<InstanceListResponse> {
  const res = await request.get('/instances', { params })
  return res.data
}

/** 查询实例详情 */
export async function getInstanceDetail(id: number): Promise<InstanceDetailResponse> {
  const res = await request.get(`/instances/${id}`)
  return res.data
}

/** 终止流程实例 */
export async function terminateInstance(id: number, reason: string): Promise<{
  id: number
  name: string
  status: string
  termination_reason: string
  terminated_at: string
}> {
  const res = await request.post(`/instances/${id}/terminate`, { reason })
  return res.data
}

/** 修改流程优先级 */
// ========== 我发起的流程 ==========
export interface MyInitiatedItem {
  id: number
  name: string
  status: string
  archive_status: string
  priority: string
  initiated_at: string | null
  completed_at: string | null
  created_at: string | null
}

export async function getMyInitiated(params: { page?: number; page_size?: number }): Promise<{ items: MyInitiatedItem[]; total: number }> {
  const res = await request.get('/instances/my-initiated', { params })
  return res.data
}

export async function changePriority(id: number, priority: string): Promise<{
  id: number
  priority: string
  old_priority: string
}> {
  const res = await request.put(`/instances/${id}/priority`, { priority })
  return res.data
}

/** 紧急换人 —— 更换运行中节点的负责人/校验人/审批人 */
export async function changePersonnel(
  instanceId: number,
  nodeId: number,
  data: {
    assignee_id?: number | null
    checkers?: { user_id: number }[]
    approvers?: { user_id: number }[]
  }
): Promise<{
  id: number
  node_name: string
  assignee_id: number | null
  checkers: { user_id: number }[] | null
  approvers: { user_id: number }[] | null
  changes: string[]
}> {
  const res = await request.put(`/instances/${instanceId}/nodes/${nodeId}/personnel`, data)
  return res.data
}

/** 永久删除流程实例（仅系统管理员，仅已终止） */
export async function permanentDeleteInstance(instanceId: number): Promise<void> {
  await request.delete(`/instances/${instanceId}/permanent`)
}
