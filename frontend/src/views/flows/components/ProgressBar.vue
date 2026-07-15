<template>
  <!-- 流程进度条 —— 横向步骤指示器，自动识别并行节点分叉汇合 -->
  <div class="progress-bar">
    <div class="progress-track">
      <template v-for="(group, gIdx) in nodeGroups" :key="gIdx">
        <!-- 分叉线（fork）—— 单节点 → 并行组 -->
        <div v-if="gIdx > 0 && group.length > 1" class="step-line step-line--fork" :class="{ 'is-active': isForkActive(gIdx) }" />

        <!-- 汇合线（join）—— 并行组 → 单节点 -->
        <div v-else-if="gIdx > 0 && nodeGroups[gIdx - 1].length > 1" class="step-line step-line--join" :class="{ 'is-active': isJoinActive(gIdx) }" />

        <!-- 普通连接线（两组都是单节点） -->
        <div v-else-if="gIdx > 0" class="step-line" :class="{ 'is-active': isLineActive(gIdx) }" />

        <!-- 单节点步骤 -->
        <div v-if="group.length === 1" class="progress-step" :class="stepClass(group[0])">
          <div class="step-dot">
            <el-icon v-if="group[0].status === 'finished' || group[0].status === 'skipped'" :size="14">
              <Check />
            </el-icon>
            <span v-else-if="['arrived','running','waiting_check','waiting_approval'].includes(group[0].status)" class="dot-inner" />
          </div>
          <div class="step-label">
            <span class="step-name" :title="group[0].name">{{ group[0].name }}</span>
            <span class="step-status-text">{{ statusText(group[0]) }}</span>
          </div>
        </div>

        <!-- 并行节点组（同 sort_order，垂直叠放，左右竖线标识分叉/汇合） -->
        <div v-else class="parallel-group">
          <div
            v-for="node in group"
            :key="node.id"
            class="progress-step"
            :class="stepClass(node)"
          >
            <div class="step-dot">
              <el-icon v-if="node.status === 'finished' || node.status === 'skipped'" :size="14">
                <Check />
              </el-icon>
              <span v-else-if="['arrived','running','waiting_check','waiting_approval'].includes(node.status)" class="dot-inner" />
            </div>
            <div class="step-label">
              <span class="step-name" :title="node.name">{{ node.name }}</span>
              <span class="step-status-text">{{ statusText(node) }}</span>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
/** 流程进度条 —— 横向步骤指示器，按 sort_order 分组，并行节点垂直叠放 */
import { computed } from 'vue'
import { Check } from '@element-plus/icons-vue'
import type { DetailNodeInfo } from '@/api/instance'

const props = defineProps<{
  nodes: DetailNodeInfo[]
}>()

/** 将节点按 sort_order 分组，同 sort_order 的为并行节点 */
const nodeGroups = computed(() => {
  const groups: DetailNodeInfo[][] = []
  if (!props.nodes.length) return groups

  const sorted = [...props.nodes].sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))

  // 向后兼容：所有节点 sort_order 相同时（旧数据），退化为逐个显示
  const uniqueOrders = new Set(sorted.map(n => n.sort_order ?? 0))
  if (uniqueOrders.size <= 1) {
    return sorted.map(n => [n])
  }

  let current: DetailNodeInfo[] = [sorted[0]]
  for (let i = 1; i < sorted.length; i++) {
    if ((sorted[i].sort_order ?? 0) === (sorted[i - 1].sort_order ?? 0)) {
      current.push(sorted[i])
    } else {
      groups.push(current)
      current = [sorted[i]]
    }
  }
  groups.push(current)
  return groups
})

function isLineActive(gIdx: number): boolean {
  const prevGroup = nodeGroups.value[gIdx - 1]
  if (!prevGroup?.length) return false
  return prevGroup.every(n => {
    const s = (n.status || '').toLowerCase()
    return s === 'finished' || s === 'skipped'
  })
}

function isForkActive(gIdx: number): boolean { return isLineActive(gIdx) }
function isJoinActive(gIdx: number): boolean { return isLineActive(gIdx) }

function stepClass(node: DetailNodeInfo) {
  const s = (node.status || '').toLowerCase()
  if (s === 'finished' || s === 'skipped') return 'is-done'
  // 进行中：处理 / 待校验 / 待审批 都视为当前活跃节点
  if (s === 'arrived' || s === 'running' || s === 'waiting_check' || s === 'waiting_approval') return 'is-current'
  return 'is-wait'
}

function statusText(node: DetailNodeInfo) {
  const s = (node.status || '').toLowerCase()
  if (s === 'finished') return '已完成'
  if (s === 'skipped') return '已跳过'
  if (s === 'arrived' || s === 'running') return '进行中'
  if (s === 'waiting_check') return '待校验'
  if (s === 'waiting_approval') return '待审批'
  if (node.is_start) return '开始'
  if (node.is_end) return '结束'
  return '待处理'
}
</script>

<style lang="scss" scoped>
.progress-bar {
  padding: 8px 0;
}

.progress-track {
  display: flex;
  align-items: flex-start;
}

/* ===== 普通连接线 ===== */
.step-line {
  flex: 1;
  min-width: 16px;
  height: 2px;
  background: var(--el-border-color);
  margin-top: 13px;
  transition: background 0.3s;

  &.is-active { background: var(--el-color-primary); }

  /* 分叉线：横线 + 右侧竖线段 */
  &--fork {
    position: relative;
    background: transparent;
    margin-right: 4px;

    &::before {
      content: '';
      position: absolute;
      left: 0; right: 4px; top: 0;
      height: 2px;
      background: var(--el-border-color);
      transition: background 0.3s;
    }

    &::after {
      content: '';
      position: absolute;
      right: 4px; top: 0;
      width: 2px;
      /* 竖线高度通过 bottom 撑满至并行组中心 */
      bottom: -18px;
      background: var(--el-border-color);
      transition: background 0.3s;
    }

    &.is-active::before,
    &.is-active::after { background: var(--el-color-primary); }
  }

  /* 汇合线：左侧竖线段 + 横线 */
  &--join {
    position: relative;
    background: transparent;
    margin-left: 4px;

    &::before {
      content: '';
      position: absolute;
      left: 4px; right: 0; top: 0;
      height: 2px;
      background: var(--el-border-color);
      transition: background 0.3s;
    }

    &::after {
      content: '';
      position: absolute;
      left: 4px; top: -18px;
      width: 2px;
      bottom: 0;
      background: var(--el-border-color);
      transition: background 0.3s;
    }

    &.is-active::before,
    &.is-active::after { background: var(--el-color-primary); }
  }
}

/* ===== 并行节点组（左右竖线标识分叉汇合） ===== */
.parallel-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  gap: 8px;
  padding: 0 8px;
  position: relative;

  /* 左竖线（fork bracket） */
  &::before {
    content: '';
    position: absolute;
    left: 0;
    top: 14px;
    bottom: 14px;
    width: 2px;
    background: var(--el-border-color);
    border-radius: 1px;
  }

  /* 右竖线（join bracket） */
  &::after {
    content: '';
    position: absolute;
    right: 0;
    top: 14px;
    bottom: 14px;
    width: 2px;
    background: var(--el-border-color);
    border-radius: 1px;
  }
}

/* ===== 步骤圆点 + 标签 ===== */
.progress-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
}

/* 圆点 */
.step-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s;

  .is-done & {
    background: var(--el-color-primary);
    color: #fff;
  }

  .is-current & {
    background: #fff;
    border: 2.5px solid var(--el-color-primary);
    box-shadow: 0 0 0 4px var(--el-color-primary-light-8);
  }

  .is-wait & {
    background: #fff;
    border: 2px solid var(--el-border-color);
  }

  .dot-inner {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: var(--el-color-primary);
  }
}

/* 标签 */
.step-label {
  margin-top: 6px;
  text-align: center;
  max-width: 80px;

  .step-name {
    display: block;
    font-size: 12px;
    font-weight: 500;
    color: var(--el-text-color-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;

    .is-wait & { color: var(--el-text-color-placeholder); }
  }

  .step-status-text {
    display: block;
    font-size: 11px;
    color: var(--el-text-color-secondary);
    margin-top: 1px;

    .is-current & { color: var(--el-color-primary); font-weight: 500; }
  }
}
</style>
