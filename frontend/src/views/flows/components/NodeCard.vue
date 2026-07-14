<template>
  <!-- 节点卡片 —— 折叠面板，展示节点文件/校验/审批详情 -->
  <div
    class="node-card"
    :class="{
      'is-active': isActive,
      'is-wait': isWait,
      'is-done': isDone,
    }"
  >
    <!-- 卡片头部（可点击折叠） -->
    <div class="node-card__head" @click="expanded = !expanded">
      <div class="node-card__head-left">
        <span class="node-index">{{ indexLabel }}</span>
        <span class="node-name">{{ node.name }}</span>
        <!-- 节点状态标签 -->
        <span class="status-tag" :class="nodeStatusClass">{{ nodeStatusLabel }}</span>
        <!-- 跳过标识 -->
        <el-tag v-if="node.is_skipped" size="small" type="info" effect="plain">已跳过</el-tag>
        <!-- 可选节点标识 -->
        <el-tag v-if="node.is_optional" size="small" type="info" effect="plain">可选</el-tag>
        <!-- 负责人 -->
        <span v-if="node.assignee_name" class="node-assignee">
          · {{ node.is_start ? '发起人 ' : '负责人 ' }}{{ node.assignee_name }}
        </span>
      </div>
      <div class="node-card__head-right">
        <span v-if="node.completed_at" class="node-time">{{ formatTime(node.completed_at) }}</span>
        <span v-if="node.started_at && !node.completed_at" class="node-time">{{ formatTime(node.started_at) }}</span>
        <el-icon :class="{ 'is-rotated': expanded }" class="toggle-arrow">
          <ArrowDown />
        </el-icon>
      </div>
    </div>

    <!-- 卡片内容（可折叠） -->
    <div class="node-card__body" v-show="expanded">
      <!-- 节点配置信息 -->
      <div class="info-grid" v-if="!node.is_start && !node.is_end">
        <div class="info-grid__item">
          <div class="k">负责人</div>
          <div class="v">{{ node.assignee_name || '未设置' }}</div>
        </div>
        <div class="info-grid__item">
          <div class="k">校验人</div>
          <div class="v">{{ checkerNames }}</div>
        </div>
        <div class="info-grid__item">
          <div class="k">审批人 / 策略</div>
          <div class="v">{{ approverNames }} · {{ strategyLabel }}</div>
        </div>
        <div class="info-grid__item">
          <div class="k">完成时限</div>
          <div class="v">
            {{ node.time_limit_days ? node.time_limit_days + ' 天' : '未设置' }}
            <span v-if="node.deadline" class="deadline-info">
              {{ formatDeadline(node.deadline) }}
            </span>
          </div>
        </div>
      </div>
      <!-- 开始/结束节点简洁说明 -->
      <div v-else class="node-desc">
        {{ node.is_start ? '系统默认开始节点，显示发起人姓名，发起后自动跳过。' : '发起人终审节点，查看全部文件后通过则归档。' }}
      </div>

      <!-- 文件列表 -->
      <div v-if="node.files.length > 0" class="node-section">
        <div class="node-section__title">文件（{{ node.files.length }}）</div>
        <div class="file-list">
          <div v-for="f in node.files" :key="f.id" class="file-item">
            <el-icon :size="16"><Document /></el-icon>
            <span class="file-name">{{ f.original_name }}</span>
            <span class="file-meta">{{ f.uploader_name }} · {{ formatFileSize(f.file_size) }}</span>
            <span v-if="f.round > 1" class="file-round">第{{ f.round }}轮</span>
          </div>
        </div>
      </div>

      <!-- 校验记录 -->
      <div v-if="node.checks.length > 0" class="node-section">
        <div class="node-section__title">校验记录（{{ node.checks.length }}）</div>
        <div class="record-list">
          <div
            v-for="c in node.checks"
            :key="c.id"
            class="record-item"
            :class="'record--' + (c.status || '').toLowerCase()"
          >
            <span class="record-user">{{ c.checker_name }}</span>
            <span class="record-status" :class="checkStatusClass(c.status)">{{ c.status === 'passed' ? '已通过' : c.status === 'rejected' ? '已退回' : c.status }}</span>
            <span v-if="c.opinion" class="record-opinion">「{{ c.opinion }}」</span>
            <span class="record-time" v-if="c.decided_at">{{ formatTime(c.decided_at) }}</span>
          </div>
        </div>
      </div>

      <!-- 审批记录 -->
      <div v-if="node.approvals.length > 0" class="node-section">
        <div class="node-section__title">审批记录（{{ node.approvals.length }}）</div>
        <div class="record-list">
          <div
            v-for="a in node.approvals"
            :key="a.id"
            class="record-item"
            :class="'record--' + (a.status || '').toLowerCase()"
          >
            <span class="record-user">{{ a.approver_name }}</span>
            <span class="record-status" :class="approvalStatusClass(a.status)">{{ approvalStatusLabel(a.status) }}</span>
            <span v-if="a.opinion" class="record-opinion">「{{ a.opinion }}」</span>
            <el-tag v-if="a.signature_applied" size="small" type="success" effect="plain" style="margin-left:4px">已签名</el-tag>
            <span class="record-time" v-if="a.decided_at">{{ formatTime(a.decided_at) }}</span>
          </div>
        </div>
      </div>

      <!-- 无内容的占位提示 -->
      <div
        v-if="node.files.length === 0 && node.checks.length === 0 && node.approvals.length === 0 && !node.is_start && !node.is_end"
        class="node-empty"
      >
        暂无操作记录
      </div>

      <!-- 修改人员按钮（仅发起人可见，未完成节点可操作） -->
      <div v-if="canChangePersonnel" class="node-actions">
        <el-button text type="primary" size="small" @click.stop="$emit('changePersonnel', node.id)">
          修改人员
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/** 节点卡片 —— 折叠展示节点配置、文件、校验、审批详情 */
import { ref, computed } from 'vue'
import { ArrowDown, Document } from '@element-plus/icons-vue'
import type { DetailNodeInfo } from '@/api/instance'

const props = defineProps<{
  node: DetailNodeInfo
  isInitiator?: boolean
}>()

defineEmits<{
  changePersonnel: [nodeId: number]
}>()

/** 是否可修改人员：发起人 + 非开始/结束节点 + 节点未完成 */
const canChangePersonnel = computed(() => {
  if (!props.isInitiator) return false
  if (props.node.is_start || props.node.is_end) return false
  const s = (props.node.status || '').toLowerCase()
  return !['finished', 'skipped', 'terminated'].includes(s)
})

// ========== 折叠状态 ==========
/** 默认展开当前节点和已完成节点，折叠未开始节点 */
const expanded = ref(getInitialExpand())

function getInitialExpand(): boolean {
  const s = (props.node.status || '').toLowerCase()
  return s === 'arrived' || s === 'running' || s === 'finished' || props.node.is_start
}

// ========== 节点序号 ==========
const indexLabel = computed(() => {
  const s = (props.node.status || '').toLowerCase()
  if (s === 'finished' || s === 'skipped') return '✓'
  return props.node.sort_order
})

// ========== 状态标签 ==========
/** 节点状态中文映射（含中间状态 waiting_check / waiting_approval） */
const nodeStatusLabel = computed(() => {
  const s = (props.node.status || '').toLowerCase()
  const map: Record<string, string> = {
    arrived: '进行中',
    running: '处理中',
    waiting_check: '待校验',
    waiting_approval: '待审批',
    finished: '已完成',
    skipped: '已跳过',
    rejected: '已驳回',
    terminated: '已终止',
  }
  return map[s] || '未开始'
})

const nodeStatusClass = computed(() => {
  const s = (props.node.status || '').toLowerCase()
  const map: Record<string, string> = {
    arrived: 'status-tag--running',
    running: 'status-tag--running',
    waiting_check: 'status-tag--running',
    waiting_approval: 'status-tag--running',
    finished: 'status-tag--completed',
    skipped: 'status-tag--draft',
    rejected: 'status-tag--terminated',
    terminated: 'status-tag--terminated',
  }
  return map[s] || 'status-tag--draft'
})

/** 当前活跃节点（有蓝色边框和阴影） */
const isActive = computed(() => {
  const s = (props.node.status || '').toLowerCase()
  return ['arrived', 'running', 'waiting_check', 'waiting_approval'].includes(s)
})

/** 等待中的节点（降低透明度） */
const isWait = computed(() => {
  const s = (props.node.status || '').toLowerCase()
  return s === 'waiting' || s === ''
})

/** 已完成/跳过的节点（绿色对勾） */
const isDone = computed(() => {
  const s = (props.node.status || '').toLowerCase()
  return s === 'finished' || s === 'skipped'
})

// ========== 人员名称 ==========
const checkerNames = computed(() => {
  if (!props.node.checkers || props.node.checkers.length === 0) return '未设置'
  return props.node.checkers.map(c => c.user_name || `ID:${c.user_id}`).join('、')
})

const approverNames = computed(() => {
  if (!props.node.approvers || props.node.approvers.length === 0) return '未设置'
  return props.node.approvers.map(a => a.user_name || `ID:${a.user_id}`).join('、')
})

const strategyLabel = computed(() => {
  return props.node.approval_strategy === 'all_approve' ? '全部通过' : props.node.approval_strategy
})

// ========== 校验/审批状态 ==========
function checkStatusClass(status: string): string {
  const s = (status || '').toLowerCase()
  if (s === 'passed') return 'status--pass'
  if (s === 'rejected') return 'status--reject'
  if (s === 'terminated') return 'status--terminated'
  return ''
}

function approvalStatusClass(status: string): string {
  const s = (status || '').toLowerCase()
  if (s === 'approved') return 'status--pass'
  if (s === 'rejected') return 'status--reject'
  if (s === 'terminated') return 'status--terminated'
  return ''
}

function approvalStatusLabel(status: string): string {
  const s = (status || '').toLowerCase()
  const map: Record<string, string> = {
    approved: '已通过',
    rejected: '已退回',
    pending: '待审批',
    terminated: '已终止',
  }
  return map[s] || status
}

// ========== 工具方法 ==========
function formatTime(val: string | null): string {
  if (!val) return ''
  return val.replace('T', ' ').substring(0, 16)
}

function formatDeadline(val: string): string {
  if (!val) return ''
  // deadline 可能是 ISO 格式
  const d = val.replace('T', ' ').substring(0, 16)
  return `截止 ${d}`
}

function formatFileSize(bytes: number | null): string {
  if (bytes == null) return ''
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}
</script>

<style lang="scss" scoped>
.node-card {
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  margin-bottom: 14px;
  overflow: hidden;
  transition: border-color 0.2s, box-shadow 0.2s;

  &.is-active {
    border-color: var(--el-color-primary);
    box-shadow: 0 1px 6px rgba(var(--el-color-primary-rgb, 26, 111, 181), 0.12);
  }

  &.is-wait {
    opacity: 0.65;
  }
}

/* 头部 */
.node-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--el-bg-color-page);
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;

  &:hover {
    background: var(--el-fill-color-light);
  }

  .is-active & {
    background: var(--el-color-primary-light-9);
  }
}

.node-card__head-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.node-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--el-bg-color);
  font-size: 11px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
  flex-shrink: 0;

  .is-active & {
    background: var(--el-color-primary);
    color: #fff;
  }

  .is-done & {
    background: var(--el-color-success);
    color: #fff;
  }
}

.node-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.node-assignee {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.node-card__head-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.node-time {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

.toggle-arrow {
  font-size: 14px;
  color: var(--el-text-color-secondary);
  transition: transform 0.2s;

  &.is-rotated {
    transform: rotate(180deg);
  }
}

/* 内容区 */
.node-card__body {
  padding: 16px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.node-desc {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  padding: 4px 0;
}

/* 子分区 */
.node-section {
  margin-top: 14px;

  &:first-child {
    margin-top: 0;
  }

  &__title {
    font-size: 13px;
    font-weight: 600;
    color: var(--el-text-color-primary);
    margin-bottom: 8px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--el-border-color-lighter);
  }
}

.node-empty {
  font-size: 13px;
  color: var(--el-text-color-placeholder);
  padding: 8px 0;
  text-align: center;
}

/* 节点操作区 */
.node-actions {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
}

/* 文件列表 */
.file-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: var(--el-bg-color-page);
  border-radius: 6px;
  font-size: 13px;

  .file-name {
    font-weight: 500;
    color: var(--el-text-color-primary);
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .file-meta {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    flex-shrink: 0;
  }

  .file-round {
    font-size: 11px;
    color: var(--el-color-primary);
    background: var(--el-color-primary-light-9);
    padding: 0 6px;
    border-radius: 999px;
    flex-shrink: 0;
  }
}

/* 校验/审批记录 */
.record-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.record-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border-radius: 6px;
  font-size: 13px;
  border-left: 3px solid var(--el-border-color);

  &.record--passed, &.record--approved {
    border-left-color: var(--el-color-success);
    background: var(--el-color-success-light-9);
  }

  &.record--rejected {
    border-left-color: var(--el-color-danger);
    background: var(--el-color-danger-light-9);
  }
}

.record-user {
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.record-status {
  font-size: 12px;
  font-weight: 500;

  &.status--pass { color: var(--el-color-success); }
  &.status--reject { color: var(--el-color-danger); }
  &.status--terminated { color: var(--el-color-info); }
}

.record-opinion {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.record-time {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
  flex-shrink: 0;
  margin-left: auto;
}

// 时限
.deadline-info {
  display: block;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
}
</style>
