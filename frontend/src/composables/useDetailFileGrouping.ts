/**
 * 详情页文件分组 —— 历史节点文件按节点分组（Task/Check/Approval/Endorse 四页共用，P2-2 抽取）
 * 本节点文件由后端 node_files 字段直接提供，无需计算
 */
import { computed, type ComputedRef } from 'vue'

/** 详情页历史文件分组的单文件项（四页文件结构的公共字段，鸭子类型） */
export interface DetailFileItem {
  id: number
  node_id: number | null
  node_name?: string
  original_name: string
  file_size: number | null
  mime_type?: string | null
}

/** 历史节点文件分组 */
export interface HistoryFileGroup {
  nodeKey: string
  nodeId: number | null
  nodeName: string
  files: DetailFileItem[]
}

export function useDetailFileGrouping(
  allFiles: ComputedRef<DetailFileItem[] | undefined>,
  currentNodeId: ComputedRef<number | undefined>,
) {
  /** 历史节点文件（按节点分组，排除当前节点） */
  const historyFileGroups = computed<HistoryFileGroup[]>(() => {
    const files = allFiles.value
    if (!files) return []
    const map = new Map<string, HistoryFileGroup>()
    for (const f of files) {
      if (f.node_id === currentNodeId.value) continue
      // 分组 key 用 node_id，避免不同节点同名导致 :key 冲突
      const key = f.node_id ? String(f.node_id) : '_unknown'
      if (!map.has(key)) {
        map.set(key, { nodeKey: key, nodeId: f.node_id, nodeName: f.node_name || '未知节点', files: [] })
      }
      map.get(key)!.files.push(f)
    }
    return [...map.values()]
  })

  return { historyFileGroups }
}
