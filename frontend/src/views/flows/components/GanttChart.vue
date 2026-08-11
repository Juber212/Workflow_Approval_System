<template>
  <!-- 排产计划甘特图 —— 手绘 SVG（复用 TrendChart viewBox/坐标模式，无第三方图表库）
       X 轴日期刻度，Y 轴节点泳道，条 = 每道工序计划区间 -->
  <div v-if="items.length === 0" class="gantt-empty">暂无排产计划</div>
  <svg v-else class="gantt-svg" :viewBox="`0 0 ${W} ${H}`" preserveAspectRatio="xMidYMid meet">
    <!-- 日期刻度竖线 + 顶部标签 -->
    <g v-for="t in ticks" :key="'tk-' + t.label">
      <line :x1="xAt(t.date)" :x2="xAt(t.date)" :y1="padT" :y2="H - padB" class="gantt-grid" />
      <text :x="xAt(t.date)" :y="padT - 6" text-anchor="middle" class="gantt-x">{{ t.label }}</text>
    </g>

    <!-- 节点泳道：节点名 + 计划条 + 负责人 -->
    <g v-for="(item, i) in sortedItems" :key="item.node_id">
      <text :x="padL - 8" :y="rowY(i) + rowH / 2 + 4" text-anchor="end" class="gantt-label">{{ item.node_name }}</text>
      <rect
        :x="xAt(parseDate(item.plan_start))"
        :y="rowY(i) + 4"
        :width="barW(item)"
        :height="rowH - 8"
        rx="4"
        class="gantt-bar"
      >
        <title>{{ item.node_name }} · {{ item.assignee_name }} · {{ item.plan_start }} ~ {{ item.plan_end }}</title>
      </rect>
      <text :x="xAt(parseDate(item.plan_end)) + 6" :y="rowY(i) + rowH / 2 + 4" class="gantt-val">{{ item.assignee_name }}</text>
    </g>
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ScheduleItem } from '@/api/instance'

const props = defineProps<{ items: ScheduleItem[] }>()

// ─── SVG 画布常量 ───
const W = 1000
const padL = 150   // 左：节点名
const padR = 120   // 右：负责人名留白
const padT = 30    // 上：日期刻度
const padB = 20    // 下
const rowH = 36    // 每道工序行高

/** 解析 ISO 日期 'YYYY-MM-DD' → Date */
function parseDate(s: string): Date {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, m - 1, d)
}

/** 格式化 Date → 'M/D'（短标签） */
function fmtDay(d: Date): string {
  return `${d.getMonth() + 1}/${d.getDate()}`
}

/** 日期范围（最早开始 ~ 最晚结束，含首尾） */
const minDate = computed(() => parseDate(props.items[0]?.plan_start || ''))
const maxDate = computed(() => {
  let max = parseDate(props.items[0]?.plan_end || '')
  props.items.forEach(i => {
    const e = parseDate(i.plan_end)
    if (e > max) max = e
  })
  return max
})

/** 总天数（至少 1） */
const totalDays = computed(() => {
  const ms = maxDate.value.getTime() - minDate.value.getTime()
  return Math.max(1, Math.round(ms / 86400000) + 1)
})

/** 排序：按 sort_order */
const sortedItems = computed(() => [...props.items].sort((a, b) => a.sort_order - b.sort_order))

/** SVG 高度 = 刻度 + 节点行 + 底部 */
const H = computed(() => padT + sortedItems.value.length * rowH + padB)

/** 日期 → X 像素 */
function xAt(d: Date): number {
  const day = Math.round((d.getTime() - minDate.value.getTime()) / 86400000)
  return padL + (day / totalDays.value) * (W - padL - padR)
}

/** 第 i 行 → Y 像素 */
function rowY(i: number): number {
  return padT + i * rowH
}

/** 计划条宽度（结束 - 开始 的天数跨度，至少 4px） */
function barW(item: ScheduleItem): number {
  const w = xAt(parseDate(item.plan_end)) - xAt(parseDate(item.plan_start))
  return Math.max(w, 4)
}

/** 日期刻度：总天数 ≤14 按天标，否则每周标一次 */
const ticks = computed(() => {
  const res: { date: Date; label: string }[] = []
  const step = totalDays.value <= 14 ? 1 : 7
  for (let day = 0; day < totalDays.value; day += step) {
    const d = new Date(minDate.value)
    d.setDate(d.getDate() + day)
    res.push({ date: d, label: fmtDay(d) })
  }
  return res
})
</script>

<style lang="scss" scoped>
.gantt-svg {
  width: 100%;
  display: block;
}

.gantt-empty {
  padding: 20px 0;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

/* 日期刻度竖线 */
.gantt-grid {
  stroke: var(--el-border-color-lighter);
  stroke-dasharray: 2 3;
}

/* 日期刻度文字 */
.gantt-x {
  font-size: 11px;
  fill: var(--el-text-color-placeholder);
}

/* 节点名（右对齐在泳道左侧） */
.gantt-label {
  font-size: 12px;
  fill: var(--el-text-color-primary);
  font-weight: 600;
}

/* 计划条 */
.gantt-bar {
  fill: #409EFF;
  opacity: 0.85;
}

/* 条右侧负责人名 */
.gantt-val {
  font-size: 11px;
  fill: var(--el-text-color-secondary);
}
</style>
