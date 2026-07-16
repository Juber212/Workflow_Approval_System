/** 节点预设 API */
import request from './request'

// ==================== 类型 ====================

/** 预设列表项 */
export interface PresetItem {
  id: number
  name: string
  node_name: string
  assignee_id: number | null
  assignee_name: string | null
  checkers: Array<{ user_id: number }> | null
  checkers_names: string[] | null
  approvers: Array<{ user_id: number }> | null
  approvers_names: string[] | null
  time_limit_days: number | null
  require_file: boolean
  sort_order: number
  created_at: string | null
}

/** 预设表单数据（创建/编辑用） */
export interface PresetFormData {
  name: string
  node_name: string
  assignee_id?: number | null
  checkers?: Array<{ user_id: number }> | null
  approvers?: Array<{ user_id: number }> | null
  time_limit_days?: number | null
  require_file?: boolean
}

// ==================== API ====================

/** 获取当前用户的预设列表 */
export async function getPresets(): Promise<{ items: PresetItem[]; total: number }> {
  const res = await request.get('/node-presets')
  return res.data
}

/** 创建预设 */
export async function createPreset(data: PresetFormData): Promise<PresetItem> {
  const res = await request.post('/node-presets', data)
  return res.data
}

/** 更新预设 */
export async function updatePreset(id: number, data: Partial<PresetFormData>): Promise<PresetItem> {
  const res = await request.put(`/node-presets/${id}`, data)
  return res.data
}

/** 删除预设 */
export async function deletePreset(id: number): Promise<void> {
  await request.delete(`/node-presets/${id}`)
}
