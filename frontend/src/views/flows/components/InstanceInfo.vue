<template>
  <!-- 实例基本信息卡片 —— 名称/状态/归档/优先级 + 5列信息网格 + 进度条 -->
  <div class="sticky-head">
    <!-- 第一行：标题 + 标签 + 操作按钮 -->
    <div class="sticky-head__top">
      <div class="sticky-head__left">
        <h1 class="sticky-head__name">{{ detail.name }}</h1>
        <span class="status-tag" :class="statusTagClass">{{ statusLabel }}</span>
        <!-- 归档状态标签（PRD §10.3：已归档灰色标签） -->
        <span v-if="archiveLabel" class="status-tag status-tag--archived">{{ archiveLabel }}</span>
        <span class="priority-badge" :class="'priority--' + detail.priority">
          {{ priorityLabel }}
        </span>
      </div>
      <div class="sticky-head__actions" v-if="showActions">
        <el-button
          v-if="canSupplement"
          size="default"
          @click="$emit('supplement')"
        >补交文件</el-button>
        <el-button
          v-if="canChangePriority"
          size="default"
          @click="$emit('changePriority')"
        >修改优先级</el-button>
        <el-button
          v-if="canTerminate"
          type="danger"
          size="default"
          @click="$emit('terminate')"
        >终止流程</el-button>
      </div>
    </div>

    <!-- 第二行：信息网格（5列） -->
    <div class="info-grid">
      <div class="info-grid__item">
        <div class="k">所属组织</div>
        <div class="v">{{ detail.organization_name }}</div>
      </div>
      <div class="info-grid__item">
        <div class="k">发起人</div>
        <div class="v">{{ detail.initiator_name }}</div>
      </div>
      <div class="info-grid__item">
        <div class="k">发起时间</div>
        <div class="v num">{{ formatTime(detail.initiated_at) }}</div>
      </div>
      <div class="info-grid__item">
        <div class="k">节点进度</div>
        <div class="v">
          <span class="stat-num" style="font-size:18px">{{ detail.current_node_index }}</span>
          <span style="font-size:13px;color:var(--el-text-color-secondary)"> / {{ detail.total_nodes }}</span>
        </div>
      </div>
    </div>

    <!-- 第三行：流程进度条 -->
    <ProgressBar v-if="detail.nodes.length > 0" :nodes="detail.nodes" />
  </div>
</template>

<script setup lang="ts">
/** 实例基本信息头部 —— 组合标题/标签/操作/信息网格/进度条 */
import { computed } from 'vue'
import ProgressBar from './ProgressBar.vue'
import type { InstanceDetailResponse } from '@/api/instance'

const props = defineProps<{
  detail: InstanceDetailResponse
  isInitiator: boolean
}>()

defineEmits<{
  supplement: []
  changePriority: []
  terminate: []
}>()

// ========== 状态标签 ==========
const statusLabel = computed(() => {
  const s = (props.detail.status || '').toLowerCase()
  const map: Record<string, string> = {
    created: '已创建',
    running: '运行中',
    completed: '已完成',
    terminated: '已终止',
  }
  return map[s] || props.detail.status
})

const statusTagClass = computed(() => {
  const s = (props.detail.status || '').toLowerCase()
  const map: Record<string, string> = {
    created: 'status-tag--draft',
    running: 'status-tag--running',
    completed: 'status-tag--completed',
    terminated: 'status-tag--terminated',
  }
  return map[s] || ''
})

/** 归档状态标签（PRD §10.3：已归档灰色标签；V1 终审通过同步归档） */
const archiveLabel = computed(() => {
  if (props.detail.archive_status === 'archived') return '已归档'
  return null
})

// ========== 优先级 ==========
const priorityLabel = computed(() => {
  const map: Record<string, string> = {
    urgent: '紧急',
    high: '高',
    normal: '普通',
    low: '低',
  }
  return map[props.detail.priority] || props.detail.priority
})

// ========== 操作按钮可见性 ==========
/** 非终止状态时显示操作区 */
const showActions = computed(() => {
  const s = (props.detail.status || '').toLowerCase()
  return s !== 'terminated'
})

/** 仅发起人可终止 */
const canTerminate = computed(() => props.isInitiator)

/** 发起人可在 running 状态修改优先级 */
const canChangePriority = computed(() => {
  return props.isInitiator && (props.detail.status || '').toLowerCase() === 'running'
})

/** 除 Terminated 外均可补交（PRD §8.5：Completed 含已归档也可补交） */
const canSupplement = computed(() => {
  const s = (props.detail.status || '').toLowerCase()
  return s !== 'terminated'
})

// ========== 工具方法 ==========
function formatTime(val: string | null): string {
  if (!val) return '-'
  return val.replace('T', ' ').substring(0, 16)
}
</script>

<style lang="scss" scoped>
.sticky-head {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
  padding: 16px 20px;
  margin-bottom: 20px;
}

.sticky-head__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.sticky-head__left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1;
}

.sticky-head__name {
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sticky-head__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

// 归档状态标签样式
.status-tag--archived {
  background: var(--el-fill-color-dark);
  color: var(--el-text-color-placeholder);
  border: 1px solid var(--el-border-color);
}

// 优先级徽章
.priority-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  line-height: 20px;

  &.priority--urgent { color: #fff; background: var(--el-color-danger); }
  &.priority--high   { color: var(--el-color-warning); background: var(--el-color-warning-light-9); }
  &.priority--normal { color: var(--el-text-color-secondary); background: var(--el-fill-color); }
  &.priority--low    { color: var(--el-color-info); background: var(--el-color-info-light-9); }
}

// 数字等宽
.num {
  font-variant-numeric: tabular-nums;
}
</style>
