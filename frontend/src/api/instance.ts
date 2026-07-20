/** 项目 API */
import request from './request'

// ==================== 类型 ====================

/** 节点覆盖配置 */
export interface NodeOverride {
  node_id: number
  assignee_id?: number | null
  deadline?: string | null
  checkers?: { user_id: number }[]
  approvers?: { user_id: number }[]
  require_signature?: boolean
  signature_x?: number
  signature_y?: number
  signature_page?: number
}

/** 发起项目请求 */
export interface CreateInstanceData {
  template_id: number
  name: string
  description?: string | null
  priority?: string
  contract_no?: string | null
  product_model?: string | null
  sales_manager?: string | null
  node_overrides?: NodeOverride[]
  proposal_id?: number | null  // 关联的已完成方案 ID（可选）
}

/** 发起项目响应 */
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
    status: string
    sort_order: number
  }[]
  initiated_at: string | null
}

// ==================== 项目列表 ====================

/** 项目列表查询参数 */
export interface InstanceListParams {
  organization_id?: number
  status?: string
  priority?: string
  keyword?: string
  sort_by?: string
  page?: number
  page_size?: number
}

/** 项目列表项 */
export interface InstanceListItem {
  id: number
  name: string
  organization_id: number
  organization_name: string
  initiator_id: number
  initiator_name: string
  priority: string
  status: string
  current_node_index: number
  total_nodes: number
  current_assignee_name: string | null
  initiated_at: string | null
  completed_at: string | null
  terminated_at: string | null
}

/** 项目列表响应 */
export interface InstanceListResponse {
  items: InstanceListItem[]
  total: number
  page: number
  page_size: number
}

// ==================== 项目详情 ====================

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
  round: number
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
  signature_x: number | null
  signature_y: number | null
  signature_page: number | null
  round: number
  decided_at: string | null
}

/** 项目详情中的节点信息 */
export interface DetailNodeInfo {
  id: number
  name: string
  is_start: boolean
  is_end: boolean
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
  require_signature: boolean
  signature_x: number
  signature_y: number
  signature_page: number
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
  detail: Record<string, unknown> | null
  created_at: string | null
}

/** 项目详情完整响应 */
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
  termination_reason: string | null
  contract_no: string | null
  product_model: string | null
  sales_manager: string | null
  proposal_id: number | null    // 关联的方案 ID
  proposal_name: string | null  // 关联的方案名称
  current_node_index: number
  total_nodes: number
  initiated_at: string | null
  completed_at: string | null
  terminated_at: string | null
  nodes: DetailNodeInfo[]
  logs: { items: LogItemBrief[]; total: number } | null
}

// ==================== API ====================

// ==================== 截止日期计算 ====================

/** 截止日期计算入参 */
export interface DeadlineCalcItem {
  node_id: number
  time_limit_days: number | null
}

/** 截止日期计算响应 */
export interface DeadlineCalcResult {
  node_id: number
  begin: string | null      // 预估开始日期 YYYY-MM-DD
  deadline: string | null   // 截止日期 YYYY-MM-DD
}

/** 批量计算节点截止日期（跳过法定节假日和周末） */
export async function calculateDeadlines(
  startDate: string,
  nodes: DeadlineCalcItem[],
): Promise<DeadlineCalcResult[]> {
  const res = await request.post('/utils/calculate-deadlines', {
    start_date: startDate,
    nodes,
  })
  return res.data.deadlines
}

// ==================== API ====================

/** 发起项目 */
export async function createInstance(data: CreateInstanceData): Promise<InstanceCreated> {
  const res = await request.post('/instances', data)
  return res.data
}

/** 查询项目列表 */
export async function getInstances(params: InstanceListParams = {}): Promise<InstanceListResponse> {
  const res = await request.get('/instances', { params })
  return res.data
}

/** 查询项目详情 */
export async function getInstanceDetail(id: number): Promise<InstanceDetailResponse> {
  const res = await request.get(`/instances/${id}`)
  return res.data
}

/** 终止项目 */
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

/** 修改项目优先级 */
// ========== 我发起的项目 ==========
export interface MyInitiatedItem {
  id: number
  name: string
  status: string
  priority: string
  initiated_at: string | null
  completed_at: string | null
  created_at: string | null
}

export async function getMyInitiated(params: { page?: number; page_size?: number; type?: string }): Promise<{ items: MyInitiatedItem[]; total: number }> {
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

/** 永久删除项目（仅系统管理员，仅已终止） */
export async function permanentDeleteInstance(instanceId: number): Promise<void> {
  await request.delete(`/instances/${instanceId}/permanent`)
}

/** 补交文件到已完成项目的已完成节点 */
export async function supplementFiles(
  instanceId: number,
  nodeId: number,
  files: File[],
): Promise<{ files: NodeFileBrief[] }> {
  const form = new FormData()
  files.forEach(f => form.append('files', f))
  const res = await request.post(
    `/instances/${instanceId}/nodes/${nodeId}/supplement-files`,
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  )
  return res.data
}
