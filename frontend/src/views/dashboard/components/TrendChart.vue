<template>
  <!-- 发起/归档趋势双折线 —— 手绘 SVG，无第三方图表库（与 PieChart/BarChart 风格一致） -->
  <div class="trend-wrap">
    <!-- 图例 -->
    <div class="trend-legend">
      <span class="trend-legend-item"><i class="trend-dot" style="background:#409EFF"></i>发起量</span>
      <span class="trend-legend-item"><i class="trend-dot" style="background:#67C23A"></i>归档量</span>
    </div>

    <!-- 空态 -->
    <div v-if="points.length === 0" class="trend-empty">暂无数据</div>

    <!-- 折线图：viewBox 定尺寸 + preserveAspectRatio 等比缩放，适配任意卡片宽度 -->
    <svg v-else class="trend-svg" :viewBox="`0 0 ${W} ${H}`" preserveAspectRatio="xMidYMid meet">
      <!-- 横向网格线 + Y 轴刻度 -->
      <g v-for="t in ticks" :key="'tick-' + t.value">
        <line :x1="padL" :x2="W - padR" :y1="t.y" :y2="t.y" :class="t.value === 0 ? 'trend-grid--base' : 'trend-grid'" />
        <text class="trend-y" :x="padL - 6" :y="t.y + 3" text-anchor="end">{{ t.value }}</text>
      </g>

      <!-- X 轴底部标签 -->
      <g v-for="(p, i) in points" :key="'x-' + i">
        <text class="trend-x" :x="xAt(i)" :y="H - 8" text-anchor="middle">{{ p.label }}</text>
      </g>

      <!-- 折线：发起量实线、归档量虚线 -->
      <polyline class="trend-line--init" :points="linePoints('initiated')" fill="none" />
      <polyline class="trend-line--comp" :points="linePoints('completed')" fill="none" />

      <!-- 数据点：圆点（hover 显示 title）+ 数值（发起量在上方、归档量在下方，避免重叠） -->
      <g v-for="(p, i) in points" :key="'pt-' + i">
        <g>
          <circle :cx="xAt(i)" :cy="yAt(p.initiated)" r="3" fill="#409EFF" stroke="#fff" stroke-width="1">
            <title>{{ p.label }} 发起 {{ p.initiated }}</title>
          </circle>
          <text class="trend-val" :x="xAt(i)" :y="yAt(p.initiated) - 9" text-anchor="middle">{{ p.initiated > 0 ? p.initiated : '' }}</text>
        </g>
        <g>
          <circle :cx="xAt(i)" :cy="yAt(p.completed)" r="3" fill="#67C23A" stroke="#fff" stroke-width="1">
            <title>{{ p.label }} 归档 {{ p.completed }}</title>
          </circle>
          <text class="trend-val" :x="xAt(i)" :y="yAt(p.completed) + 16" text-anchor="middle">{{ p.completed > 0 ? p.completed : '' }}</text>
        </g>
      </g>
    </svg>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { TrendPoint } from '@/api/dashboard'

const props = defineProps<{ points: TrendPoint[] }>()

// ─── SVG 画布尺寸（viewBox 单位，实际随容器等比缩放） ───
const W = 1000
const H = 260
const padL = 44   // 左：Y 轴刻度
const padR = 20   // 右：数值留白
const padT = 26   // 上：发起量数值
const padB = 30   // 下：X 轴标签

/** 向上取整到好读数（复用 BarChart niceMax 思路：4→4, 6→10, 12→20, 23→30, 45→50） */
function niceMax(val: number): number {
  if (val <= 0) return 4
  if (val <= 4) return Math.max(val, 4)
  const mag = 10 ** Math.floor(Math.log10(val))
  const n = val / mag
  if (n <= 2.5) return Math.ceil(val / mag) * mag
  if (n <= 5) return 5 * mag
  return 10 * mag
}

/** Y 轴上限（两条线的最大值向上取整，至少 4 防除零） */
const maxVal = computed(() => niceMax(Math.max(1, ...props.points.map(p => Math.max(p.initiated, p.completed)))))

/** Y 轴刻度：上限 / 2/3 / 1/3 / 0 四档 */
const ticks = computed(() => {
  const m = maxVal.value
  return [
    { value: m, y: yAt(m) },
    { value: Math.round((m * 2) / 3), y: yAt(Math.round((m * 2) / 3)) },
    { value: Math.round(m / 3), y: yAt(Math.round(m / 3)) },
    { value: 0, y: yAt(0) },
  ]
})

/** 第 i 个点的 X 坐标（首尾贴边，中间等分；单点时居中） */
function xAt(i: number): number {
  const n = props.points.length
  if (n <= 1) return (padL + W - padR) / 2
  return padL + ((W - padL - padR) * i) / (n - 1)
}

/** 值 → Y 像素坐标（值越大越靠上） */
function yAt(val: number): number {
  return padT + (1 - val / maxVal.value) * (H - padT - padB)
}

/** 折线点串 "x,y x,y ..."（单点退化为单点，polyline 仍可显示） */
function linePoints(key: 'initiated' | 'completed'): string {
  return props.points.map((p, i) => `${xAt(i)},${yAt(p[key])}`).join(' ')
}
</script>

<style lang="scss" scoped>
.trend-wrap {
  .trend-legend {
    display: flex; gap: 20px; margin-bottom: 12px; font-size: 12px; color: var(--el-text-color-secondary);
    .trend-dot {
      display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; vertical-align: -1px;
    }
  }

  .trend-empty {
    text-align: center; padding: 36px 0; color: var(--el-text-color-secondary); font-size: 13px;
  }
}

/* ─── SVG 图表 ─── */
.trend-svg { width: 100%; height: 260px; display: block; }

/* 网格线 */
.trend-grid { stroke: var(--el-border-color-lighter); stroke-dasharray: 4 4; }
.trend-grid--base { stroke: var(--el-border-color-light); }

/* 坐标轴文字 */
.trend-y { font-size: 11px; fill: var(--el-text-color-placeholder); }
.trend-x { font-size: 11px; fill: var(--el-text-color-secondary); }

/* 折线：发起量实线、归档量虚线 */
.trend-line--init { stroke: #409EFF; stroke-width: 2; }
.trend-line--comp { stroke: #67C23A; stroke-width: 2; stroke-dasharray: 6 4; }

/* 点旁数值 */
.trend-val { font-size: 11px; fill: var(--el-text-color-regular); font-variant-numeric: tabular-nums; }
</style>
