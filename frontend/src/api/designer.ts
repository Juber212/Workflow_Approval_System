/** 流程设计器 API —— 画布数据保存 */
import request from './request'

// ==================== 类型 ====================

/** 设计器节点数据 */
export interface DesignerNode {
  id?: number | null        // 已有节点 id（null/undefined 表示新增）
  name?: string
  is_start?: boolean
  is_end?: boolean
  assignee_id?: number | null
  time_limit_days?: number | null
  require_file?: boolean
  approvers?: number[] | null
  checkers?: number[] | null
  approval_strategy?: string
  position_x: number       // 画布X坐标
  position_y: number       // 画布Y坐标
  sort_order?: number
}

/** 设计器连线数据 */
export interface DesignerEdge {
  id?: number | null              // 已有连线 id（null/undefined 表示新增）
  source_node_id: number | string // 源节点 id（新节点可为临时字符串 ID）
  target_node_id: number | string // 目标节点 id（新节点可为临时字符串 ID）
}

/** 批量保存请求体 */
export interface SaveDesignData {
  nodes: DesignerNode[]
  edges: DesignerEdge[]
}

// ==================== API ====================

/** 批量保存设计器内容 */
export async function saveDesign(templateId: number, data: SaveDesignData) {
  const res = await request.put(`/templates/${templateId}/design`, data)
  return res.data as { template_id: number; node_count: number; edge_count: number }
}
