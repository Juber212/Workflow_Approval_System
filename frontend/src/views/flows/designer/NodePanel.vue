<template>
  <div class="node-panel">
    <div class="panel-title">节点库</div>
    <div class="panel-desc">拖拽或点击添加到画布</div>

    <!-- 基础工作节点（置顶） -->
    <div
      class="node-card node-card--base"
      draggable="true"
      @click="emit('add')"
      @dragstart="onBaseDragStart"
    >
      <div class="node-icon" style="background: #ecf5ff; border-color: #1a6fb5" />
      <div class="node-info">
        <div class="node-label">工作节点</div>
        <div class="node-hint">空白审批/校验节点</div>
      </div>
    </div>

    <!-- 预设节点列表 -->
    <div
      v-for="preset in presets"
      :key="preset.id"
      class="node-card node-card--preset"
      draggable="true"
      @click="emit('add', preset)"
      @dragstart="onPresetDragStart($event, preset)"
      @mouseenter="hoveredId = preset.id"
      @mouseleave="hoveredId = null"
    >
      <div class="node-icon" style="background: #f0f9eb; border-color: #67c23a" />
      <div class="node-info">
        <div class="node-label">{{ preset.name }}</div>
        <div class="node-hint">
          {{ preset.assignee_name || '未设负责人' }} · {{ preset.time_limit_days ?? '不限' }}工作日
        </div>
      </div>
      <!-- hover 操作图标 -->
      <Transition name="fade">
        <span v-show="hoveredId === preset.id" class="node-card__actions">
          <el-button text size="small" @click.stop="emit('edit-preset', preset)" title="编辑">
            <el-icon :size="14"><EditPen /></el-icon>
          </el-button>
          <el-button text size="small" @click.stop="emit('delete-preset', preset)" title="删除">
            <el-icon :size="14"><Delete /></el-icon>
          </el-button>
        </span>
      </Transition>
    </div>

    <!-- 新建预设按钮 -->
    <el-button class="add-preset-btn" @click="emit('edit-preset')">
      <el-icon><Plus /></el-icon>
      新建预设
    </el-button>
  </div>
</template>

<script setup lang="ts">
/** 节点库面板 —— 基础节点 + 预设节点列表 */
import { ref } from 'vue'
import { EditPen, Delete, Plus } from '@element-plus/icons-vue'
import type LogicFlow from '@logicflow/core'
import type { PresetItem } from '@/api/presets'

const emit = defineEmits<{
  /** 添加节点：无参 = 空白工作节点；传 preset = 预设节点 */
  add: [preset?: PresetItem]
  /** 编辑预设：无参 = 新建；传 preset = 编辑 */
  'edit-preset': [preset?: PresetItem]
  /** 删除预设 */
  'delete-preset': [preset: PresetItem]
}>()

const props = withDefaults(defineProps<{
  lf: LogicFlow | null
  presets?: PresetItem[]
}>(), {
  presets: () => [],
})

const hoveredId = ref<number | null>(null)

/** 基础工作节点 DnD */
function onBaseDragStart(e: DragEvent) {
  startDnD(e, {
    name: '新节点',
    is_start: false, is_end: false,
    require_file: true,
    approval_strategy: 'all_approve',
    time_limit_days: 3,
  })
}

/** 预设节点 DnD */
function onPresetDragStart(e: DragEvent, preset: PresetItem) {
  startDnD(e, {
    name: preset.node_name,
    is_start: false, is_end: false,
    assignee_id: preset.assignee_id,
    assignee_name: preset.assignee_name,
    checkers: preset.checkers?.map(c => c.user_id) || null,
    checkers_names: preset.checkers_names || null,
    approvers: preset.approvers?.map(a => a.user_id) || null,
    approvers_names: preset.approvers_names || null,
    time_limit_days: preset.time_limit_days,
    require_file: preset.require_file,
    approval_strategy: 'all_approve',
  })
}

/** LogicFlow DnD 启动 */
function startDnD(event: DragEvent, properties: Record<string, any>) {
  if (!props.lf || !event.dataTransfer) return
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', 'work-node')
  props.lf.dnd.startDrag({ type: 'work-node', properties })
}
</script>

<style lang="scss" scoped>
.node-panel {
  width: 160px; height: 100%;
  background: #fff;
  border-right: 1px solid var(--el-border-color-light);
  padding: 12px; display: flex;
  flex-direction: column; gap: 8px;
  flex-shrink: 0;
  overflow-y: auto;

  .panel-title { font-size: 14px; font-weight: 600; color: var(--el-text-color-primary); }
  .panel-desc { font-size: 11px; color: var(--el-text-color-placeholder); margin-bottom: 4px; }
}

.node-card {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 10px; border: 1px solid var(--el-border-color-light);
  border-radius: 6px; cursor: grab;
  transition: box-shadow 0.2s; user-select: none;
  position: relative;

  &:hover { box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1); border-color: var(--el-color-primary); }
  &:active { cursor: grabbing; }

  &--base { border-style: dashed; }
  &--preset { border-color: #e1f3d8; }
}

.node-icon { width: 32px; height: 32px; border-radius: 4px; border: 2px solid; flex-shrink: 0; }

.node-info {
  flex: 1; min-width: 0;
  .node-label { font-size: 13px; color: var(--el-text-color-primary); }
  .node-hint { font-size: 11px; color: var(--el-text-color-placeholder); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
}

/* hover 操作图标 */
.node-card__actions {
  position: absolute; top: 2px; right: 4px;
  display: flex; align-items: center; gap: 0;
  background: rgba(255,255,255,0.92);
  border-radius: 4px; padding: 0 2px;
}

.add-preset-btn {
  width: 100%;
  margin-top: 4px;
  border-style: dashed;
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
