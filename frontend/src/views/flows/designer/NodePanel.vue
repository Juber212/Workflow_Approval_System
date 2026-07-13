<template>
  <div class="node-panel">
    <div class="panel-title">节点库</div>
    <div class="panel-desc">拖拽或点击添加到画布</div>

    <!-- 工作节点卡片 -->
    <div
      class="node-card"
      draggable="true"
      @click="emit('add')"
      @dragstart="handleDragStart"
    >
      <div class="node-icon" style="background: #ecf5ff; border-color: #1a6fb5" />
      <div class="node-info">
        <div class="node-label">工作节点</div>
        <div class="node-hint">审批/校验节点</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type LogicFlow from '@logicflow/core'

const emit = defineEmits<{
  add: []
}>()

const props = defineProps<{
  lf: LogicFlow | null
}>()

/** 拖拽开始 —— 通知 LogicFlow 开始 DnD */
function handleDragStart(event: DragEvent) {
  if (!props.lf || !event.dataTransfer) return

  // 设置拖拽效果
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', 'work-node')

  // 启动 LogicFlow DnD
  props.lf.dnd.startDrag({
    type: 'work-node',
    text: { value: '新节点', x: 80, y: 32 },
    properties: {
      name: '新节点',
      is_start: false,
      is_end: false,
      require_file: true,
      approval_strategy: 'all_approve',
      is_optional: false,
      time_limit_days: 3,
    },
  })
}
</script>

<style lang="scss" scoped>
.node-panel {
  width: 160px;
  height: 100%;
  background: #fff;
  border-right: 1px solid var(--el-border-color-light);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex-shrink: 0;

  .panel-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }

  .panel-desc {
    font-size: 11px;
    color: var(--el-text-color-placeholder);
    margin-bottom: 4px;
  }
}

/* 可拖拽节点卡片 */
.node-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  cursor: grab;
  transition: box-shadow 0.2s;
  user-select: none;

  &:hover {
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    border-color: var(--el-color-primary);
  }

  &:active {
    cursor: grabbing;
  }
}

.node-icon {
  width: 32px;
  height: 32px;
  border-radius: 4px;
  border: 2px solid;
  flex-shrink: 0;
}

.node-info {
  flex: 1;
  min-width: 0;

  .node-label {
    font-size: 13px;
    color: var(--el-text-color-primary);
  }

  .node-hint {
    font-size: 11px;
    color: var(--el-text-color-placeholder);
  }
}
</style>
