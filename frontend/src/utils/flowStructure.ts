/**
 * 发起模式流程结构工具 —— 纯函数，无 lf/DOM 依赖，可独立单测
 *
 * 覆盖三块易错逻辑：
 *  - topoSortNodes：画布节点按连线拓扑排序（新增节点插入后时间重排依赖）
 *  - normalizePersons：人员列表规范化为 [{user_id}]（后端 NodeOverride schema 要求 dict 数组）
 *  - calcChainDeadlines / countDaysExcludingStart：自然日期限链式计算（与后端自然日口径一致）
 */

export interface FlowNodeLike {
  id: string
  properties?: Record<string, any>
}

export interface FlowEdgeLike {
  sourceNodeId: string
  targetNodeId: string
}

/** 画布节点拓扑排序（Kahn 算法，模板节点 + 新增节点统一按连线结构） */
export function topoSortNodes(nodes: FlowNodeLike[], edges: FlowEdgeLike[]): FlowNodeLike[] {
  const nodeMap = new Map(nodes.map(n => [n.id, n]))
  const indeg = new Map<string, number>(nodes.map(n => [n.id, 0]))
  const adj = new Map<string, string[]>()
  edges.forEach(e => {
    if (nodeMap.has(e.sourceNodeId) && nodeMap.has(e.targetNodeId)) {
      if (!adj.has(e.sourceNodeId)) adj.set(e.sourceNodeId, [])
      adj.get(e.sourceNodeId)!.push(e.targetNodeId)
      indeg.set(e.targetNodeId, (indeg.get(e.targetNodeId) || 0) + 1)
    }
  })
  const queue = nodes.filter(n => (indeg.get(n.id) || 0) === 0).map(n => n.id)
  const order: string[] = []
  while (queue.length) {
    const id = queue.shift()!
    order.push(id)
    for (const t of adj.get(id) || []) {
      indeg.set(t, (indeg.get(t) || 0) - 1)
      if (indeg.get(t) === 0) queue.push(t)
    }
  }
  // 环 / 孤立节点兜底：未排序的追加到末尾，保证所有节点都返回
  nodes.forEach(n => { if (!order.includes(n.id)) order.push(n.id) })
  return order.map(id => nodeMap.get(id)!)
}

/** 规范化人员列表为 [{user_id}]（兼容模板节点历史数字数组 [id] 与 dict 数组） */
export function normalizePersons(list: any[]): { user_id: number }[] {
  return list.map(p =>
    typeof p === 'number' || typeof p === 'string'
      ? { user_id: Number(p) }
      : { user_id: Number(p.user_id ?? p.id) },
  )
}

/** 格式化 Date → 'YYYY-MM-DD' */
function fmtDate(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** 自然日链式期限：首节点从 start 起，截止 = 开始 + N 天 - 1；下一节点衔接截止次日（自然日，与后端口径一致）
 *
 * @param nodes 工作节点（须已按拓扑序传入），time_limit_days 缺省按 1 天
 * @param start 链首节点起始日（今天 0 点）
 * @returns id → { begin, deadline }（YYYY-MM-DD）
 */
export function calcChainDeadlines(
  nodes: { id: string; time_limit_days?: number | null }[],
  start: Date,
): Record<string, { begin: string; deadline: string }> {
  const result: Record<string, { begin: string; deadline: string }> = {}
  let cursor = new Date(start.toDateString())  // 起始日 0 点
  for (const n of nodes) {
    const days = Math.max(n.time_limit_days || 1, 1)
    const begin = new Date(cursor)
    const end = new Date(cursor.getTime() + (days - 1) * 86400000)  // 截止 = 开始 + N 天 - 1
    result[n.id] = { begin: fmtDate(begin), deadline: fmtDate(end) }
    cursor = new Date(end.getTime() + 86400000)  // 下一节点从截止次日开始
  }
  return result
}

/** 从 start 的下一日到 end（含 end）的天数 —— 自然日，与后端计算口径一致 */
export function countDaysExcludingStart(startStr: string, endStr: string): number {
  const cur = new Date(startStr)
  const end = new Date(endStr)
  return Math.max(1, Math.round((end.getTime() - cur.getTime()) / 86400000))
}
