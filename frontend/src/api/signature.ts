/** 签名通用类型 —— 跨角色（负责人/校验人/审批人）共用 */

/** 签名提交单元 —— 前端签批弹框产出 */
export interface SignatureSlot {
  file_id: number
  signature_x: number
  signature_y: number
  signature_page: number  // -1=最后一页
  /** 签名宽度（px），null=使用全局默认 */
  signature_width?: number | null
  /** 签名高度（px），null=使用全局默认 */
  signature_height?: number | null
}

/** 签名记录 —— API 返回 */
export interface SignatureItem {
  id: number
  file_id: number
  signer_id: number
  signer_name: string
  role_type: string  // "assignee" | "checker" | "approver"
  source_id: number
  node_id: number
  signature_x: number
  signature_y: number
  signature_page: number
  applied: boolean
  sort_order: number
  created_at: string | null
}
