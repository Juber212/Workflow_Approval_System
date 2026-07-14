<template>
  <!-- 环形饼图 —— 任务状态分布（PRD §4.4） -->
  <div class="pie-wrap">
    <!-- 空态 -->
    <div v-if="total === 0" class="pie-empty">暂无数据</div>

    <template v-else>
      <!-- SVG 饼图 + 中心白圆 = 环形 -->
      <div class="pie-donut">
        <svg :viewBox="`0 0 ${sz} ${sz}`" :width="sz" :height="sz">
          <g :transform="`translate(${sz/2},${sz/2})`">
            <path
              v-for="(s, i) in slices"
              :key="i"
              :d="s.path"
              :fill="s.color"
              :opacity="hoverIdx === i ? 0.85 : 1"
              stroke="#fff" stroke-width="1.5"
              style="cursor:pointer; transition: opacity 0.15s"
              @mouseenter="hoverIdx = i"
              @mouseleave="hoverIdx = -1"
              @click="$emit('click', s.status)"
            >
              <title>{{ s.label }}: {{ s.count }} ({{ s.percent }}%)</title>
            </path>
          </g>
        </svg>
        <!-- 遮罩圆（CSS，模拟环形） -->
        <div class="pie-hole">
          <span class="pie-hole__num">{{ total }}</span>
          <span class="pie-hole__label">总任务</span>
        </div>
      </div>

      <!-- 图例 -->
      <div class="pie-legend">
        <div
          v-for="(item, i) in items"
          :key="i"
          class="lgd"
          :class="{ 'lgd--on': hoverIdx === i }"
          @mouseenter="hoverIdx = i"
          @mouseleave="hoverIdx = -1"
          @click="$emit('click', item.status)"
        >
          <span class="lgd-dot" :style="{ background: item.color }"></span>
          <span class="lgd-lab">{{ item.label }}</span>
          <span class="lgd-cnt">{{ item.count }}</span>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

interface PieItem { status: string; label: string; color: string; count: number }
const props = defineProps<{ items: PieItem[] }>()
defineEmits<{ click: [status: string] }>()

const sz = 200
const R = 98
const hoverIdx = ref(-1)
const total = computed(() => props.items.reduce((s, i) => s + i.count, 0))

const slices = computed(() => {
  if (total.value === 0) return []
  let a = -Math.PI / 2

  return props.items
    .filter(i => i.count > 0)
    .map(i => {
      const sa = a
      const ea = a + (i.count / total.value) * 2 * Math.PI
      a = ea

      const x1 = R * Math.cos(sa), y1 = R * Math.sin(sa)
      const x2 = R * Math.cos(ea), y2 = R * Math.sin(ea)
      const big = ea - sa > Math.PI ? 1 : 0

      // 单扇区时画整圆
      const path = total.value === i.count
        ? `M 0 ${-R} A ${R} ${R} 0 1 1 0 ${R} A ${R} ${R} 0 1 1 0 ${-R} Z`
        : `M 0 0 L ${x1} ${y1} A ${R} ${R} 0 ${big} 1 ${x2} ${y2} Z`

      const pct = Math.round((i.count / total.value) * 100)
      return { ...i, path, percent: pct }
    })
})
</script>

<style lang="scss" scoped>
.pie-wrap { display: flex; align-items: center; gap: 28px; }
.pie-empty { width: 200px; height: 160px; display: flex; align-items: center; justify-content: center; color: var(--el-text-color-placeholder); font-size: 14px; }

/* ─── 环形饼图 ─── */
.pie-donut { position: relative; width: 200px; height: 200px; flex-shrink: 0; }

.pie-hole {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  width: 120px; height: 120px; border-radius: 50%;
  background: var(--el-bg-color);
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  pointer-events: none;

  &__num { font-size: 24px; font-weight: 700; color: var(--el-text-color-primary); line-height: 1.2; }
  &__label { font-size: 11px; color: var(--el-text-color-secondary); }
}

/* ─── 图例 ─── */
.pie-legend { display: flex; flex-direction: column; gap: 5px; }

.lgd {
  display: flex; align-items: center; gap: 8px; font-size: 12px;
  padding: 3px 6px; border-radius: 4px; cursor: pointer; transition: background 0.12s;
  &:hover, &--on { background: var(--el-fill-color-light); }
}

.lgd-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.lgd-lab { color: var(--el-text-color-regular); min-width: 72px; }
.lgd-cnt { font-weight: 600; color: var(--el-text-color-primary); font-variant-numeric: tabular-nums; }
</style>
