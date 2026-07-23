/** 设计器 API —— 画布数据保存 */
import request from './request'

// ==================== 类型 ====================

/** 文件提交文件夹配置 */
export interface FileFolderConfig {
  name: string        // 文件夹名称
  required: boolean   // 是否必须提交
  file_count: number | null  // 精确数量限制（null=不限）
}

/** 设计器节点数据 */
export interface DesignerNode {
  id?: number | null        // 已有节点 id（null/undefined 表示新增）
  name?: string
  is_start?: boolean
  is_end?: boolean
  assignee_id?: number | null
  time_limit_days?: number | null
  require_file?: boolean
  file_folders?: FileFolderConfig[] | null  // 文件提交文件夹配置
  approvers?: number[] | null
  checkers?: number[] | null
  approval_strategy?: string
  require_assignee_signature?: boolean   // 负责人提交时是否签名
  require_checker_signature?: boolean    // 校验人通过时是否签名
  require_approver_signature?: boolean   // 审批人通过时是否签名
  endorser_id?: number | null            // 批准人（仅难度4时生效）
  require_endorser_signature?: boolean   // 批准人通过时是否签名
  signature_x?: number
  signature_y?: number
  signature_page?: number
  position_x: number       // 画布X坐标
  position_y: number       // 画布Y坐标
  sort_order?: number
}

/** 设计器连线数据 */
export interface DesignerEdge {
  id?: number | null              // 已有连线 id（null/undefined 表示新增）
  source_node_id: number | string // 源节点 id（新节点可为临时字符串 ID）
  target_node_id: number | string // 目标节点 id（新节点可为临时字符串 ID）
  points?: string | null          // 折线路径点串（LogicFlow points 字符串格式），保存后恢复避免路由重算
}

/** 批量保存请求体 */
export interface SaveDesignData {
  nodes: DesignerNode[]
  edges: DesignerEdge[]
}

/** 保存设计器响应 */
export interface SaveDesignResponse {
  template_id: number
  node_count: number
  edge_count: number
}

// ==================== API ====================

/** 批量保存设计器内容 */
export async function saveDesign(templateId: number, data: SaveDesignData) {
  const res = await request.put(`/templates/${templateId}/design`, data)
  return res.data as SaveDesignResponse
}
