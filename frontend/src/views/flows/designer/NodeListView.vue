<template>
  <div class="node-list-view">
    <div class="list-header">
      <span class="list-title">节点配置总览</span>
      <span class="list-count">共 {{ nodes.length }} 个节点</span>
    </div>

    <el-table
      :data="nodes"
      :row-class-name="rowClassName"
      stripe
      size="small"
      highlight-current-row
      @row-click="handleRowClick"
      class="node-table"
    >
      <!-- 序号 -->
      <el-table-column type="index" width="50" label="#" />

      <!-- 节点名称 -->
      <el-table-column prop="name" label="节点名称" min-width="100">
        <template #default="{ row }">
          <span class="node-name-cell">
            <el-tag v-if="row.is_start" size="small" type="success">开始</el-tag>
            <el-tag v-else-if="row.is_end" size="small" type="primary">结束</el-tag>
            <span v-else>{{ row.name || '未命名' }}</span>
          </span>
        </template>
      </el-table-column>

      <!-- 负责人 -->
      <el-table-column label="负责人" width="90">
        <template #default="{ row }">
          <template v-if="row.is_start || row.is_end">
            <span class="text-muted">系统</span>
          </template>
          <template v-else-if="row.assignee_name">
            <span class="text-ok">{{ row.assignee_name }}</span>
          </template>
          <template v-else>
            <span class="text-warn">⚠ 未配置</span>
          </template>
        </template>
      </el-table-column>

      <!-- 校验人 -->
      <el-table-column label="校验人" min-width="120">
        <template #default="{ row }">
          <template v-if="row.is_start || row.is_end">
            <span class="text-muted">—</span>
          </template>
          <template v-else-if="row.checkers_names && row.checkers_names.length > 0">
            <span class="text-ok">
              {{ row.checkers_names.slice(0, 2).join('、') }}
              <el-tag v-if="row.checkers_names.length > 2" size="small" type="info" class="more-tag">
                +{{ row.checkers_names.length - 2 }}
              </el-tag>
            </span>
          </template>
          <template v-else>
            <span class="text-warn">⚠ 未配置</span>
          </template>
        </template>
      </el-table-column>

      <!-- 审批人 -->
      <el-table-column label="审批人" min-width="120">
        <template #default="{ row }">
          <template v-if="row.is_start || row.is_end">
            <span class="text-muted">—</span>
          </template>
          <template v-else-if="row.approvers_names && row.approvers_names.length > 0">
            <span class="text-ok">
              {{ row.approvers_names.slice(0, 2).join('、') }}
              <el-tag v-if="row.approvers_names.length > 2" size="small" type="info" class="more-tag">
                +{{ row.approvers_names.length - 2 }}
              </el-tag>
            </span>
          </template>
          <template v-else>
            <span class="text-warn">⚠ 未配置</span>
          </template>
        </template>
      </el-table-column>

      <!-- 时限 -->
      <el-table-column label="时限" width="70" align="center">
        <template #default="{ row }">
          <template v-if="row.is_start || row.is_end">
            <span class="text-muted">—</span>
          </template>
          <template v-else-if="row.time_limit_days">
            <span class="text-ok">{{ row.time_limit_days }}天</span>
          </template>
          <template v-else>
            <span class="text-warn">⚠</span>
          </template>
        </template>
      </el-table-column>

      <!-- 状态 -->
      <el-table-column label="状态" width="80" align="center">
        <template #default="{ row }">
          <template v-if="row.is_start || row.is_end">
            <el-tag size="small" type="info">系统</el-tag>
          </template>
          <template v-else-if="isRowConfigured(row)">
            <el-tag size="small" type="success">已配置</el-tag>
          </template>
          <template v-else>
            <el-tag size="small" type="warning">未配置</el-tag>
          </template>
        </template>
      </el-table-column>
    </el-table>

    <div class="list-footer">
      <span>点击行可定位到画布对应节点</span>
    </div>
  </div>
</template>

<script setup lang="ts">
/** 节点列表表格 —— 辅助快捷核对全部节点配置 */
interface NodeItem {
  id: string | number
  name?: string
  is_start?: boolean
  is_end?: boolean
  assignee_id?: number | null
  assignee_name?: string
  checkers?: number[] | null
  checkers_names?: string[]
  approvers?: number[] | null
  approvers_names?: string[]
  time_limit_days?: number | null
  sort_order?: number
}

const props = defineProps<{
  nodes: NodeItem[]
}>()

const emit = defineEmits<{
  'select-node': [nodeId: string | number]
}>()

/** 判断行对应节点是否已配置 */
function isRowConfigured(row: NodeItem): boolean {
  return !!(
    row.name &&
    row.assignee_id &&
    row.checkers && row.checkers.length > 0 &&
    row.approvers && row.approvers.length > 0 &&
    row.time_limit_days && row.time_limit_days >= 1
  )
}

/** 行样式：系统节点灰色背景 */
function rowClassName({ row }: { row: NodeItem }): string {
  if (row.is_start || row.is_end) return 'system-row'
  return isRowConfigured(row) ? 'configured-row' : 'unconfigured-row'
}

/** 点击行 → 定位画布节点 */
function handleRowClick(row: NodeItem) {
  emit('select-node', row.id)
}
</script>

<style lang="scss" scoped>
.node-list-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--el-border-color-light);
  flex-shrink: 0;

  .list-title {
    font-size: 15px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }

  .list-count {
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
}

.node-table {
  flex: 1;
  overflow-y: auto;

  // 系统节点行灰色背景
  :deep(.system-row) {
    background-color: #f5f7fa;
    color: var(--el-text-color-secondary);
  }

  // 未配置行浅橙背景
  :deep(.unconfigured-row) {
    background-color: #fef9f0;
  }
}

.list-footer {
  padding: 8px 16px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  border-top: 1px solid var(--el-border-color-light);
  flex-shrink: 0;
}

// 文字状态色
.text-ok { color: var(--el-text-color-regular); }
.text-warn { color: #f56c6c; font-weight: 500; }
.text-muted { color: #c0c4cc; }

.more-tag {
  margin-left: 2px;
  vertical-align: bottom;
}
</style>
