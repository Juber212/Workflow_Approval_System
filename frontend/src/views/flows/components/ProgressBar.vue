<template>
  <!-- 流程进度条 —— 横向步骤指示器，并行节点 N 条 SVG 贝塞尔曲线分叉/汇合 -->
  <div class="progress-bar">
    <div class="progress-track" ref="trackRef">
      <template v-for="(group, gIdx) in nodeGroups" :key="gIdx">
        <!-- ===== 分叉曲线：源节点 → 每个并行节点 ===== -->
        <svg
          v-if="gIdx > 0 && group.length > 1"
          class="conn-svg"
          :viewBox="`0 0 40 ${(forkData[gIdx]?.height) || 120}`"
          preserveAspectRatio="none"
          :style="{ height: `${(forkData[gIdx]?.height) || 120}px` }"
        >
          <path
            v-for="(nodeY, i) in (forkData[gIdx]?.nodeDotYs || [30, 90])"
            :key="i"
            :d="`M 0,${forkData[gIdx]?.srcDotY || 30} C 16,${forkData[gIdx]?.srcDotY || 30} 24,${nodeY} 40,${nodeY}`"
            fill="none"
            :stroke="isForkActive(gIdx) ? 'var(--el-color-primary)' : 'var(--el-border-color)'"
            stroke-width="2"
            vector-effect="non-scaling-stroke"
          />
        </svg>

        <!-- ===== 汇合曲线：每个并行节点 → 目标节点 ===== -->
        <svg
          v-else-if="gIdx > 0 && nodeGroups[gIdx - 1].length > 1"
          class="conn-svg"
          :viewBox="`0 0 40 ${(joinData[gIdx]?.height) || 120}`"
          preserveAspectRatio="none"
          :style="{ height: `${(joinData[gIdx]?.height) || 120}px` }"
        >
          <path
            v-for="(nodeY, i) in (joinData[gIdx]?.nodeDotYs || [30, 90])"
            :key="i"
            :d="`M 0,${nodeY} C 16,${nodeY} 24,${joinData[gIdx]?.dstDotY || 60} 40,${joinData[gIdx]?.dstDotY || 60}`"
            fill="none"
            :stroke="isJoinActive(gIdx) ? 'var(--el-color-primary)' : 'var(--el-border-color)'"
            stroke-width="2"
            vector-effect="non-scaling-stroke"
          />
        </svg>

        <!-- ===== 普通连接线 ===== -->
        <div v-else-if="gIdx > 0" class="step-line" :class="{ 'is-active': isLineActive(gIdx) }" />

        <!-- ===== 单节点步骤 ===== -->
        <div v-if="group.length === 1" class="progress-step" :class="stepClass(group[0])"
          :ref="el => { if (el) stepRefs[gIdx] = el as HTMLElement }">
          <div class="step-dot">
            <el-icon v-if="group[0].status === 'finished'" :size="14"><Check /></el-icon>
            <span v-else-if="['arrived','running','waiting_check','waiting_approval'].includes(group[0].status)" class="dot-inner" />
          </div>
          <div class="step-label">
            <span class="step-name" :title="group[0].name">{{ group[0].name }}</span>
            <span class="step-status-text">{{ statusText(group[0]) }}</span>
          </div>
        </div>

        <!-- ===== 并行节点组 ===== -->
        <div v-else class="parallel-group"
          :ref="el => { if (el) parallelRefs[gIdx] = el as HTMLElement }">
          <div v-for="node in group" :key="node.id" class="progress-step" :class="stepClass(node)">
            <div class="step-dot">
              <el-icon v-if="node.status === 'finished'" :size="14"><Check /></el-icon>
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
/** 流程进度条 —— N 条 SVG 贝塞尔曲线分叉/汇合 + 单节点自动居中 */
import { ref, computed, onMounted, nextTick } from 'vue'
import { Check } from '@element-plus/icons-vue'
import type { DetailNodeInfo } from '@/api/instance'

const props = defineProps<{ nodes: DetailNodeInfo[] }>()

// ========== DOM 引用 ==========
const trackRef = ref<HTMLElement | null>(null)
const stepRefs: Record<number, HTMLElement> = {}
const parallelRefs: Record<number, HTMLElement> = {}

// ========== SVG 数据 ==========
interface ForkData { height: number; srcDotY: number; nodeDotYs: number[] }
interface JoinData { height: number; dstDotY: number; nodeDotYs: number[] }

const forkData = ref<Record<number, ForkData>>({})
const joinData = ref<Record<number, JoinData>>({})

// ========== 分组逻辑（不变） ==========
const nodeGroups = computed(() => {
  const groups: DetailNodeInfo[][] = []
  if (!props.nodes.length) return groups
  const sorted = [...props.nodes].sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))
  const uniqueOrders = new Set(sorted.map(n => n.sort_order ?? 0))
  if (uniqueOrders.size <= 1) return sorted.map(n => [n])
  let current: DetailNodeInfo[] = [sorted[0]]
  for (let i = 1; i < sorted.length; i++) {
    if ((sorted[i].sort_order ?? 0) === (sorted[i - 1].sort_order ?? 0)) {
      current.push(sorted[i])
    } else { groups.push(current); current = [sorted[i]] }
  }
  groups.push(current)
  return groups
})

function isLineActive(gIdx: number): boolean {
  const prev = nodeGroups.value[gIdx - 1]
  if (!prev?.length) return false
  return prev.every(n => (n.status || '').toLowerCase() === 'finished')
}
function isForkActive(gIdx: number): boolean { return isLineActive(gIdx) }
function isJoinActive(gIdx: number): boolean { return isLineActive(gIdx) }

function stepClass(node: DetailNodeInfo) {
  const s = (node.status || '').toLowerCase()
  if (s === 'finished') return 'is-done'
  if (['arrived', 'running', 'waiting_check', 'waiting_approval'].includes(s)) return 'is-current'
  return 'is-wait'
}

function statusText(node: DetailNodeInfo) {
  const s = (node.status || '').toLowerCase()
  const m: Record<string, string> = { finished: '已完成', arrived: '进行中', running: '进行中', waiting_check: '待校验', waiting_approval: '待审批' }
  if (m[s]) return m[s]
  if (node.is_start) return '开始'
  if (node.is_end) return '结束'
  return '待处理'
}

// ========== 挂载后测量 + 居中 + 建 SVG 数据 ==========
onMounted(() => {
  nextTick(() => {
    const groups = nodeGroups.value

    // --- Step 1: 读所有高度 ---
    const pH: Record<number, number> = {}  // parallel group heights
    const sH: Record<number, number> = {}  // single step heights
    Object.entries(parallelRefs).forEach(([k, el]) => { pH[Number(k)] = el.offsetHeight })
    Object.entries(stepRefs).forEach(([k, el]) => { sH[Number(k)] = el.offsetHeight })

    // --- Step 2: 存在并行组时，所有单节点统一居中到最高并行组高度 ---
    const hasParallel = groups.some(g => g.length > 1)
    if (hasParallel) {
      const maxPH = Math.max(...Object.values(pH))
      groups.forEach((group, gIdx) => {
        if (group.length !== 1) return
        const sh = sH[gIdx]
        if (maxPH && sh && maxPH > sh) {
          stepRefs[gIdx].style.marginTop = `${Math.round((maxPH - sh) / 2)}px`
        }
      })
    }

    // --- 同步普通连接线 margin-top，使横线对齐居中后的圆点 ---
    let lineMargin = 0
    groups.forEach((group, gIdx) => {
      if (group.length !== 1) return
      const mt = parseInt(stepRefs[gIdx].style.marginTop || '0')
      if (mt > lineMargin) lineMargin = mt
    })
    trackRef.value?.querySelectorAll('.step-line').forEach(el => {
      (el as HTMLElement).style.marginTop = `${lineMargin + 13}px`
    })

    // --- Step 3: 读 offsetTop，计算 SVG 数据 ---
    const fd: Record<number, ForkData> = {}
    const jd: Record<number, JoinData> = {}

    groups.forEach((group, gIdx) => {
      // Fork: 单节点 gIdx-1 → 并行组 gIdx
      if (gIdx > 0 && group.length > 1) {
        const data = calcFork(gIdx)
        if (data) fd[gIdx] = data
      }
      // Join: 并行组 gIdx-1 → 单节点 gIdx
      if (gIdx > 0 && groups[gIdx - 1].length > 1) {
        const data = calcJoin(gIdx)
        if (data) jd[gIdx] = data
      }
    })

    forkData.value = fd
    joinData.value = jd
  })
})

/** 计算 fork SVG 数据 */
function calcFork(gIdx: number): ForkData | null {
  const srcEl = stepRefs[gIdx - 1]
  const parEl = parallelRefs[gIdx]
  if (!srcEl || !parEl) return null

  const srcDotY = srcEl.offsetTop + 14  // 源节点圆心
  const nodeEls = parEl.querySelectorAll<HTMLElement>('.progress-step')
  const nodeDotYs = Array.from(nodeEls).map(el => el.offsetTop + 14)

  const allY = [srcDotY, ...nodeDotYs]
  const minY = Math.min(...allY)
  const maxY = Math.max(...allY)
  const pad = 10
  const height = maxY - minY + pad * 2
  const offset = minY - pad

  return {
    height,
    srcDotY: srcDotY - offset,
    nodeDotYs: nodeDotYs.map(y => y - offset),
  }
}

/** 计算 join SVG 数据 */
function calcJoin(gIdx: number): JoinData | null {
  const dstEl = stepRefs[gIdx]
  const parEl = parallelRefs[gIdx - 1]
  if (!dstEl || !parEl) return null

  const dstDotY = dstEl.offsetTop + 14  // 目标节点圆心
  const nodeEls = parEl.querySelectorAll<HTMLElement>('.progress-step')
  const nodeDotYs = Array.from(nodeEls).map(el => el.offsetTop + 14)

  const allY = [dstDotY, ...nodeDotYs]
  const minY = Math.min(...allY)
  const maxY = Math.max(...allY)
  const pad = 10
  const height = maxY - minY + pad * 2
  const offset = minY - pad

  return {
    height,
    dstDotY: dstDotY - offset,
    nodeDotYs: nodeDotYs.map(y => y - offset),
  }
}
</script>

<style lang="scss" scoped>
.progress-bar { padding: 8px 0; }

.progress-track { display: flex; align-items: flex-start; position: relative; }

/* SVG 曲线 */
.conn-svg { flex: 1; min-width: 16px; overflow: visible; }

/* 普通连接线 */
.step-line {
  flex: 1; min-width: 16px; height: 2px;
  background: var(--el-border-color); margin-top: 13px;
  transition: background 0.3s;
  &.is-active { background: var(--el-color-primary); }
}

/* 并行组（无竖线边框） */
.parallel-group {
  display: flex; flex-direction: column; align-items: center;
  flex-shrink: 0; gap: 8px;
  position: relative; /* 子元素 offsetTop 参照物 */
}

/* 步骤 */
.progress-step { display: flex; flex-direction: column; align-items: center; flex-shrink: 0; }

.step-dot {
  width: 28px; height: 28px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center; transition: all 0.3s;
  .is-done & { background: var(--el-color-primary); color: #fff; }
  .is-current & { background: #fff; border: 2.5px solid var(--el-color-primary); box-shadow: 0 0 0 4px var(--el-color-primary-light-8); }
  .is-wait & { background: #fff; border: 2px solid var(--el-border-color); }
}
.dot-inner { width: 9px; height: 9px; border-radius: 50%; background: var(--el-color-primary); }

.step-label {
  margin-top: 6px; text-align: center; max-width: 80px;
  .step-name { display: block; font-size: 12px; font-weight: 500; color: var(--el-text-color-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    .is-wait & { color: var(--el-text-color-placeholder); }
  }
  .step-status-text { display: block; font-size: 11px; color: var(--el-text-color-secondary); margin-top: 1px;
    .is-current & { color: var(--el-color-primary); font-weight: 500; }
  }
}
</style>
