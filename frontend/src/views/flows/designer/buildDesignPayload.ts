/**
 * 设计器图数据序列化 —— 节点/连线转 DesignerNode/DesignerEdge（P2-2 抽取）
 * FlowDesigner 的 handleSave 与 handleLaunch 共用同一套序列化逻辑
 */
import type { DesignerNode, DesignerEdge } from '@/api/designer'

/** 构建节点 LF UUID → 数据库 ID 的映射（通过 properties.db_id） */
function buildSystemIdMapping(graphData: { nodes: any[]; edges: any[] }): Record<string, number> {
  const mapping: Record<string, number> = {}
  for (const n of graphData.nodes) {
    if (n.properties?.db_id != null) {
      mapping[String(n.id)] = Number(n.properties.db_id)
    }
  }
  return mapping
}

/** LF 节点 ID → 数据库 ID（映射命中返回 db_id；纯数字返回原值；否则返回字符串临时 ID 由后端解析） */
function resolveNodeId(lfId: string | number, mapping: Record<string, number>): number | string | null {
  if (mapping[String(lfId)] !== undefined) return mapping[String(lfId)]
  const num = Number(lfId)
  // 能转数字 → 返回数字（DB ID）；否则返回原始字符串（新节点临时 ID，由后端 new_node_id_map 解析）
  return Number.isNaN(num) ? String(lfId) : num
}

/** 序列化画布为保存/发起用的节点与连线数组 */
export function buildDesignPayload(lf: any): { nodes: DesignerNode[]; edges: DesignerEdge[] } {
  const graphData = lf.getGraphData() as { nodes: any[]; edges: any[] }
  const idMapping = buildSystemIdMapping(graphData)

  const nodes: DesignerNode[] = graphData.nodes.map((n: any) => ({
    id: resolveNodeId(n.id, idMapping), name: n.properties?.name || n.text?.value || n.type,
    is_start: n.properties?.is_start ?? false, is_end: n.properties?.is_end ?? false,
    assignee_id: n.properties?.assignee_id ?? null, time_limit_days: n.properties?.time_limit_days ?? null,
    require_file: n.properties?.require_file ?? false, approvers: n.properties?.approvers ?? null,
    file_folders: n.properties?.file_folders ?? null,  // 文件提交文件夹配置
    checkers: n.properties?.checkers ?? null, approval_strategy: n.properties?.approval_strategy ?? 'all_approve',
    require_assignee_signature: n.properties?.require_assignee_signature ?? true,
    require_checker_signature: n.properties?.require_checker_signature ?? true,
    require_approver_signature: n.properties?.require_approver_signature ?? true,
    endorser_id: n.properties?.endorser_id ?? null,
    require_endorser_signature: n.properties?.require_endorser_signature ?? true,
    signature_x: n.properties?.signature_x ?? 400,
    signature_y: n.properties?.signature_y ?? 100,
    signature_page: n.properties?.signature_page ?? -1,
    position_x: Math.round(n.x), position_y: Math.round(n.y),
    sort_order: n.properties?.sort_order ?? 0,
  }))

  const edges: DesignerEdge[] = graphData.edges
    .filter((e: any) => e.sourceNodeId && e.targetNodeId)
    .map((e: any) => {
      // getGraphData() 不包含 points，需从 Model 实例直接读取
      const edgeModel = lf.getEdgeModelById(e.id) as any
      return { id: Number(e.id) || null, source_node_id: resolveNodeId(e.sourceNodeId, idMapping) ?? String(e.sourceNodeId), target_node_id: resolveNodeId(e.targetNodeId, idMapping) ?? String(e.targetNodeId), points: edgeModel?.points || null }
    })

  return { nodes, edges }
}
