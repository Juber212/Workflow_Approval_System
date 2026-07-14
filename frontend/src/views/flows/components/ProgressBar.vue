<template>
  <!-- 流程进度条 —— 节点步骤指示器 -->
  <div class="progress-bar">
    <div class="progress-track">
      <template v-for="(node, index) in nodes" :key="node.id">
        <!-- 连接线（第一个节点前无线） -->
        <div
          v-if="index > 0"
          class="step-line"
          :class="{ 'is-active': isPrevDone(index) }"
        />
        <!-- 步骤圆点 + 标签 -->
        <div class="progress-step" :class="stepClass(node)">
          <div class="step-dot">
            <el-icon v-if="node.status === 'finished' || node.status === 'skipped'" :size="14">
              <Check />
            </el-icon>
            <span v-else-if="node.status === 'arrived' || node.status === 'running'" class="dot-inner" />
          </div>
          <div class="step-label">
            <span class="step-name" :title="node.name">{{ node.name }}</span>
            <span class="step-status-text">{{ statusText(node) }}</span>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
/** 流程进度条 —— 横向步骤指示器，展示节点流程推进状态 */
import { Check } from '@element-plus/icons-vue'
import type { DetailNodeInfo } from '@/api/instance'

const props = defineProps<{
  nodes: DetailNodeInfo[]
}>()

/** 前一个节点是否已完成（决定连接线颜色） */
function isPrevDone(index: number): boolean {
  const prev = props.nodes[index - 1]
  if (!prev) return false
  const s = (prev.status || '').toLowerCase()
  return s === 'finished' || s === 'skipped'
}

/** 步骤圆点样式 */
function stepClass(node: DetailNodeInfo) {
  const s = (node.status || '').toLowerCase()
  if (s === 'finished' || s === 'skipped') return 'is-done'
  if (s === 'arrived' || s === 'running') return 'is-current'
  return 'is-wait'
}

/** 状态文字 */
function statusText(node: DetailNodeInfo) {
  const s = (node.status || '').toLowerCase()
  if (s === 'finished') return '已完成'
  if (s === 'skipped') return '已跳过'
  if (s === 'arrived' || s === 'running') return '进行中'
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

/* 连接线 */
.step-line {
  flex: 1;
  min-width: 16px;
  height: 2px;
  background: var(--el-border-color);
  margin-top: 13px;
  transition: background 0.3s;

  &.is-active {
    background: var(--el-color-primary);
  }
}

/* 步骤 */
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

    .is-wait & {
      color: var(--el-text-color-placeholder);
    }
  }

  .step-status-text {
    display: block;
    font-size: 11px;
    color: var(--el-text-color-secondary);
    margin-top: 1px;

    .is-current & {
      color: var(--el-color-primary);
      font-weight: 500;
    }
  }
}
</style>
