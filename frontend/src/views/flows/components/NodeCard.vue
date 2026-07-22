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
        <!-- 负责人 -->
        <span v-if="node.assignee_name" class="node-assignee">
          · {{ node.is_start ? '发起人 ' : '负责人 ' }}{{ node.assignee_name }}
        </span>
      </div>
      <div class="node-card__head-right">
        <!-- 补交文件按钮（仅已完成的工作节点显示） -->
        <el-button
          v-if="canSupplementNode"
          text type="primary" size="small"
          @click.stop="$emit('supplement', node.id)"
        >补交文件</el-button>
        <span v-if="node.completed_at" class="node-time">{{ formatTime(node.completed_at) }}</span>
        <span v-if="node.started_at && !node.completed_at" class="node-time">{{ formatTime(node.started_at) }}</span>
        <el-icon :class="{ 'is-rotated': expanded }" class="toggle-arrow">
          <ArrowDown />
        </el-icon>
      </div>
    </div>

    <!-- 卡片内容（可折叠） -->
    <div class="node-card__body" v-show="expanded">
      <!-- 阶段进度指示（非开始/结束/跳过节点显示） -->
      <div v-if="!node.is_start && !node.is_end" class="stage-progress">
        <div class="stage-steps">
          <template v-for="(label, idx) in ['处理', '校验', '审批', '完成']" :key="label">
            <div class="stage-step" :class="stageClass(idx)">{{ label }}</div>
            <div v-if="idx < 3" class="stage-line" :class="stageLineClass(idx)"></div>
          </template>
        </div>
      </div>

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
            {{ node.time_limit_days ? node.time_limit_days + ' 工作日' : '未设置' }}
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

      <!-- ===== 三栏布局：文件 / 校验 / 审批（非开始/结束节点） ===== -->
      <div v-if="!node.is_start && !node.is_end" class="node-columns">
        <!-- 文件栏（40%）—— 支持文件夹分组展示 -->
        <div class="node-col">
          <!-- 有文件夹配置：按文件夹分组 -->
          <template v-if="hasFolderConfig">
            <div v-for="group in folderFileGroups" :key="group.name" class="folder-file-group">
              <div class="node-col__title">📁 {{ group.name }}（{{ group.files.length }}）</div>
              <div v-if="group.files.length === 0" class="node-col__empty">暂无</div>
              <div v-else class="file-list">
                <div v-for="f in group.files" :key="f.id" class="file-item">
                  <div class="file-item__main">
                    <el-icon :size="14"><Document /></el-icon>
                    <span class="file-name" :title="f.original_name">{{ f.original_name }}</span>
                    <span v-if="f.round > 1" class="file-round">第{{ f.round }}轮</span>
                  </div>
                  <div class="file-item__meta">{{ f.uploader_name }} · {{ formatFileSize(f.file_size) }}</div>
                  <div class="file-item__actions">
                    <el-button text type="primary" size="small" @click="previewFile(f.id)">查看</el-button>
                    <el-button text type="primary" size="small" @click="downloadFile(f.id)">下载</el-button>
                  </div>
                </div>
              </div>
            </div>
          </template>
          <!-- 无文件夹配置：原有平面展示 -->
          <template v-else>
          <div class="node-col__title">📁 文件（{{ normalFiles.length }}）</div>
          <div v-if="normalFiles.length === 0" class="node-col__empty">暂无</div>
          <div v-else class="file-list">
            <div v-for="f in normalFiles" :key="f.id" class="file-item">
              <div class="file-item__main">
                <el-icon :size="14"><Document /></el-icon>
                <span class="file-name" :title="f.original_name">{{ f.original_name }}</span>
                <span v-if="f.round > 1" class="file-round">第{{ f.round }}轮</span>
              </div>
              <div class="file-item__meta">{{ f.uploader_name }} · {{ formatFileSize(f.file_size) }}</div>
              <div class="file-item__actions">
                <el-button text type="primary" size="small" @click="previewFile(f.id)">查看</el-button>
                <el-button text type="primary" size="small" @click="downloadFile(f.id)">下载</el-button>
              </div>
            </div>
          </div>
          </template>
          <!-- 补交文件 -->
          <template v-if="supplementFiles.length > 0">
            <div class="node-col__title node-col__title--supplement">📎 补交文件（{{ supplementFiles.length }}）</div>
            <div class="file-list">
              <div v-for="f in supplementFiles" :key="f.id" class="file-item file-item--supplement">
                <div class="file-item__main">
                  <el-icon :size="14"><Document /></el-icon>
                  <span class="file-name" :title="f.original_name">{{ f.original_name }}</span>
                  <el-tag size="small" type="warning" effect="dark">补交</el-tag>
                </div>
                <div class="file-item__meta">{{ f.uploader_name }} · {{ formatFileSize(f.file_size) }} · {{ formatTime(f.created_at) }}</div>
                <div class="file-item__actions">
                  <el-button text type="primary" size="small" @click="previewFile(f.id)">查看</el-button>
                  <el-button text type="primary" size="small" @click="downloadFile(f.id)">下载</el-button>
                </div>
              </div>
            </div>
          </template>
        </div>

        <!-- 校验栏（30%） -->
        <div class="node-col">
          <div class="node-col__title">✓ 校验记录（{{ node.checks.length }}）</div>
          <div v-if="node.checks.length === 0" class="node-col__empty">暂无</div>
          <div v-else class="record-list">
            <div
              v-for="c in node.checks"
              :key="c.id"
              class="record-item"
              :class="'record--' + (c.status || '').toLowerCase()"
            >
              <div class="record-item__main">
                <span class="record-user">{{ c.checker_name }}</span>
                <span class="record-status" :class="checkStatusClass(c.status)">{{ checkStatusLabel(c.status) }}</span>
                <span class="record-round" v-if="c.round > 1">#{{ c.round }}</span>
              </div>
              <div v-if="c.opinion" class="record-item__opinion">「{{ c.opinion }}」</div>
              <div class="record-item__time" v-if="c.decided_at">{{ formatTime(c.decided_at) }}</div>
            </div>
          </div>
        </div>

        <!-- 审批栏（30%） -->
        <div class="node-col">
          <div class="node-col__title">📝 审批记录（{{ node.approvals.length }}）</div>
          <div v-if="node.approvals.length === 0" class="node-col__empty">暂无</div>
          <div v-else class="record-list">
            <div
              v-for="a in node.approvals"
              :key="a.id"
              class="record-item"
              :class="'record--' + (a.status || '').toLowerCase()"
            >
              <div class="record-item__main">
                <span class="record-user">{{ a.approver_name }}</span>
                <span class="record-status" :class="approvalStatusClass(a.status)">{{ approvalStatusLabel(a.status) }}</span>
                <span class="record-round" v-if="a.round > 1">#{{ a.round }}</span>
                <el-tag v-if="a.signature_applied" size="small" type="success" effect="plain">已签名</el-tag>
              </div>
              <div v-if="a.opinion" class="record-item__opinion">「{{ a.opinion }}」</div>
              <div class="record-item__time" v-if="a.decided_at">{{ formatTime(a.decided_at) }}</div>
            </div>
          </div>
        </div>
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
import { ref, computed, watch } from 'vue'
import { ArrowDown, Document } from '@element-plus/icons-vue'
import type { DetailNodeInfo } from '@/api/instance'
import { previewFile, downloadFile } from '@/api/task'

const props = defineProps<{
  node: DetailNodeInfo
  isInitiator?: boolean
  /** 实例主状态（用于控制补交按钮可见性——仅 completed 实例可补交） */
  instanceStatus?: string
  /** 强制展开/折叠（null=默认行为，true=全部展开，false=全部折叠） */
  forceExpand?: boolean | null
}>()

defineEmits<{
  changePersonnel: [nodeId: number]
  supplement: [nodeId: number]
}>()

/** 是否可修改人员：发起人 + 非开始/结束节点 + 节点未完成 */
const canChangePersonnel = computed(() => {
  if (!props.isInitiator) return false
  if (props.node.is_start || props.node.is_end) return false
  const s = (props.node.status || '').toLowerCase()
  return !['finished', 'terminated'].includes(s)
})

/** 是否可补交：仅 completed 实例的 finished 节点（权限由后端最终校验） */
const canSupplementNode = computed(() => {
  if ((props.instanceStatus || '').toLowerCase() !== 'completed') return false
  if (props.node.is_start || props.node.is_end) return false
  return (props.node.status || '').toLowerCase() === 'finished'
})

// ========== 折叠状态 ==========
/** 活动状态集合 —— 这些状态的节点默认展开 */
const ACTIVE_STATUSES = ['arrived', 'running', 'waiting_check', 'waiting_approval']

/** 默认：仅展开进行中的节点（开始节点永远折叠，结束节点仅进行中时展开） */
const expanded = ref(getInitialExpand())

function getInitialExpand(): boolean {
  const s = (props.node.status || '').toLowerCase()
  // 开始节点永远不自动展开
  if (props.node.is_start) return false
  // 进行中的节点自动展开（含终审阶段的结束节点）
  return ACTIVE_STATUSES.includes(s)
}

/** 监听全局展开/折叠按钮 */
watch(() => props.forceExpand, (val) => {
  if (val === true) expanded.value = true
  else if (val === false) expanded.value = false
})

// ========== 节点序号 ==========
const indexLabel = computed(() => {
  const s = (props.node.status || '').toLowerCase()
  if (s === 'finished') return '✓'
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
  return s === 'finished'
})

// ========== 人员名称 ==========
/** 当前节点所处的阶段序号：-1=未到达, 0=处理, 1=校验, 2=审批, 3=完成 */
const currentStep = computed(() => {
  const s = (props.node.status || '').toLowerCase()
  if (s === 'finish' || s === 'finished') return 3
  if (s === 'waiting_approval') return 2
  if (s === 'waiting_check') return 1
  if (s === 'arrived' || s === 'running') return 0
  // waiting / terminated / rejected 等 → 不亮任何阶段
  return -1
})

/** 阶段步骤样式 */
function stageClass(step: number): string {
  const cur = currentStep.value
  if (step < cur) return 'stage-step--done'
  if (step === cur) return 'stage-step--active'
  return ''
}

/** 阶段连接线样式 */
function stageLineClass(step: number): string {
  return step < currentStep.value ? 'stage-line--done' : ''
}

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

/** 按 upload_type 分组：正常文件 vs 补交文件 */
const normalFiles = computed(() =>
  props.node.files.filter(f => (f.upload_type || '').toLowerCase() !== 'supplement')
)
const supplementFiles = computed(() =>
  props.node.files.filter(f => (f.upload_type || '').toLowerCase() === 'supplement')
)

/** 文件按文件夹分组（用于文件夹模式展示） */
const folderFileGroups = computed(() => {
  const groups: { name: string; files: typeof normalFiles.value }[] = []
  const seen = new Map<string, number>()
  for (const f of normalFiles.value) {
    const key = f.folder_name || '其他文件'
    if (seen.has(key)) {
      groups[seen.get(key)!].files.push(f)
    } else {
      seen.set(key, groups.length)
      groups.push({ name: key, files: [f] })
    }
  }
  // "其他文件"放在最后
  groups.sort((a, b) => {
    if (a.name === '其他文件') return 1
    if (b.name === '其他文件') return -1
    return 0
  })
  return groups
})
const hasFolderConfig = computed(() => {
  return props.node.file_folders && Array.isArray(props.node.file_folders) && props.node.file_folders.length > 0
})

// ========== 校验/审批状态 ==========
function checkStatusClass(status: string): string {
  const s = (status || '').toLowerCase()
  if (s === 'passed') return 'status--pass'
  if (s === 'returned') return 'status--reject'
  if (s === 'terminated') return 'status--terminated'
  return ''
}

function checkStatusLabel(status: string): string {
  const m: Record<string, string> = { pending: '待校验', passed: '已通过', returned: '已退回' }
  return m[(status || '').toLowerCase()] || status
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
  background: #fff;
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
  background: #fff;
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

/* 阶段进度指示 */
.stage-progress {
  margin-bottom: 14px;
}

.stage-steps {
  display: flex;
  align-items: center;
  gap: 0;
}

.stage-step {
  font-size: 12px;
  font-weight: 500;
  padding: 3px 10px;
  border-radius: 999px;
  color: var(--el-text-color-placeholder);
  background: var(--el-fill-color);
  transition: all 0.2s;
  flex-shrink: 0;

  &--active {
    color: #fff;
    background: var(--el-color-primary);
  }

  &--done {
    color: var(--el-color-success);
    background: var(--el-color-success-light-9);
  }
}

.stage-line {
  flex: 1;
  height: 2px;
  margin: 0 4px;
  background: var(--el-border-color);
  border-radius: 1px;
  transition: background 0.2s;

  &--done {
    background: var(--el-color-success);
  }
}

.node-desc {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  padding: 4px 0;
}

/* ===== 三栏容器（grid 4:3:3） ===== */
.node-columns {
  display: grid;
  grid-template-columns: 4fr 3fr 3fr;
  gap: 16px;
  margin-top: 14px;
}

.node-col {
  min-width: 0; /* 防止内容溢出 */

  &__title {
    font-size: 12px;
    font-weight: 600;
    color: var(--el-text-color-secondary);
    margin-bottom: 8px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--el-border-color-lighter);

    &--supplement {
      margin-top: 14px;
      color: var(--el-color-warning-dark-2);
      border-bottom-color: var(--el-color-warning-light-7);
    }
  }

  &__empty {
    font-size: 12px;
    color: var(--el-text-color-placeholder);
    text-align: center;
    padding: 16px 0;
  }
}

/* 文件列表 */
.file-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.file-item {
  display: flex;
  flex-direction: column;
  padding: 8px 10px;
  background: var(--el-bg-color-page);
  border-radius: 6px;

  &--supplement {
    border-left: 3px solid var(--el-color-warning);
  }

  &__main {
    display: flex;
    align-items: center;
    gap: 4px;

    .file-name {
      font-weight: 500;
      font-size: 13px;
      color: var(--el-text-color-primary);
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .file-round {
      font-size: 11px;
      color: var(--el-color-primary);
      background: var(--el-color-primary-light-9);
      padding: 0 5px;
      border-radius: 999px;
      flex-shrink: 0;
    }
  }

  &__meta {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    padding-left: 18px; /* 对齐文件名（图标14px + gap 4px） */
    margin-top: 3px;
  }

  &__actions {
    display: flex;
    gap: 4px;
    margin-top: 4px;
    justify-content: flex-end;
  }
}

/* 校验/审批记录列表 */
.record-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.record-item {
  display: flex;
  flex-direction: column;
  padding: 6px 8px;
  border-radius: 6px;
  font-size: 13px;
  border-left: 3px solid var(--el-border-color);

  &.record--passed, &.record--approved {
    border-left-color: var(--el-color-success);
    background: var(--el-color-success-light-9);
  }

  &.record--rejected, &.record--returned {
    border-left-color: var(--el-color-danger);
    background: var(--el-color-danger-light-9);
  }

  &__main {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;

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

    .record-round {
      font-size: 11px;
      font-weight: 500;
      color: var(--el-text-color-placeholder);
      background: var(--el-fill-color);
      padding: 0 5px;
      border-radius: 999px;
    }
  }

  &__opinion {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    margin-top: 2px;
  }

  &__time {
    font-size: 11px;
    color: var(--el-text-color-placeholder);
    margin-top: 2px;
  }
}

/* 节点操作区 */
.node-actions {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
}

// 时限
.deadline-info {
  display: block;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
}
</style>
