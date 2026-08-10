<template>
  <!-- 各所项目负载竖柱图 —— 运行中为主轴（当前负载），完成/终止为辅助数字 -->
  <!-- 改版动机：原三状态共轴，运行久后已完成累计值撑满 Y 轴、运行中/终止矮到不可见；改为只对比「当前运行中」 -->
  <div class="vbar-wrap">
    <!-- 图例 -->
    <div class="vbar-legend">
      <span class="vbar-legend-item"><i class="vbar-legend-dot" style="background:#67C23A"></i>运行中</span>
      <span class="vbar-legend-note">柱高 = 各所当前运行中项目数（当前负载）</span>
    </div>

    <!-- 四栏卡片网格 -->
    <div class="vbar-grid" v-if="items.length > 0">
      <div
        v-for="item in items"
        :key="item.org_id"
        class="vbar-card"
        :class="{ 'vbar-card--empty': item.total_count === 0 }"
        @click="$emit('org-click', item.org_id)"
      >
        <!-- 卡片头部 -->
        <div class="vbar-card__header">
          <span class="vbar-card__name" :title="item.org_name">{{ item.org_name }}</span>
          <span class="vbar-card__total">共 {{ item.total_count }} 个</span>
        </div>

        <!-- 图表区：Y轴 + 运行中柱 + 网格线 -->
        <div class="vbar-card__chart">
          <!-- Y 轴刻度（按运行中最大值） -->
          <div class="vbar-y">
            <span v-for="tick in cardTicks(item)" :key="tick" class="vbar-y__tick">{{ tick }}</span>
          </div>
          <!-- 柱子区域 -->
          <div class="vbar-bars">
            <!-- 网格线（与 Y 轴刻度对齐） -->
            <div class="vbar-grid-lines">
              <span
                v-for="(tick, i) in cardTicks(item)"
                :key="tick"
                class="vbar-grid-line"
                :class="{ 'is-base': i === cardTicks(item).length - 1 }"
              />
            </div>
            <!-- 运行中柱（单柱居中） -->
            <div class="vbar-col">
              <div class="vbar-col__bar-wrap">
                <div
                  class="vbar-col__bar"
                  :style="{ height: barPct(item.running_count, cardMax(item)) }"
                  :title="`运行中：${item.running_count}`"
                >
                  <!-- 数字锚定柱顶上方外侧：柱矮时上浮显示，杜绝向下溢出落到横轴下方 -->
                  <span v-if="item.running_count > 0" class="vbar-col__num">{{ item.running_count }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 底部：完成/终止辅助数字（不占柱高，避免累计值拉高 Y 轴） -->
        <div class="vbar-sub">
          <span>完成 {{ item.completed_count }}</span>
          <span>终止 {{ item.terminated_count }}</span>
        </div>
      </div>
    </div>
    <div v-else class="bar-empty">暂无数据</div>
  </div>
</template>

<script setup lang="ts">
import type { OrgOverview } from '@/api/dashboard'

const props = defineProps<{ items: OrgOverview[] }>()
defineEmits<{ 'org-click': [orgId: number] }>()

/** 向上取整到好读数（如 6→10, 12→20, 23→30, 45→50） */
function niceMax(val: number): number {
  if (val <= 0) return 2
  if (val <= 4) return Math.max(val, 2)
  const mag = 10 ** Math.floor(Math.log10(val))
  const n = val / mag
  if (n <= 2.5) return Math.ceil(val / mag) * mag
  if (n <= 5) return 5 * mag
  return 10 * mag
}

/** 计算单个卡片的 Y 轴信息（按运行中最大值，缓存避免重复计算） */
const scaleCache = new Map<number, { max: number; ticks: number[] }>()

function getScale(item: OrgOverview) {
  const rawMax = Math.max(item.running_count, 1)
  let s = scaleCache.get(rawMax)
  if (!s) {
    const max = niceMax(rawMax)
    const ticks = [max, Math.round(max * 2 / 3), Math.round(max / 3), 0]
    s = { max, ticks }
    scaleCache.set(rawMax, s)
  }
  return s
}

function cardMax(item: OrgOverview) { return getScale(item).max }
function cardTicks(item: OrgOverview) { return getScale(item).ticks }

/** 柱子高度百分比（基于该卡片运行中 Y 轴上限） */
function barPct(val: number, max: number): string {
  if (val <= 0 || max <= 0) return '0'
  return ((val / max) * 100).toFixed(1) + '%'
}
</script>

<style lang="scss" scoped>
.vbar-wrap {
  .vbar-legend {
    display: flex; align-items: center; gap: 20px; margin-bottom: 14px; font-size: 12px; color: var(--el-text-color-secondary);
    .vbar-legend-dot {
      display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; vertical-align: -1px;
    }
    &-note { color: var(--el-text-color-placeholder); font-size: 12px; }
  }
}

/* ─── 四栏卡片网格 ─── */
.vbar-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

/* ─── 单个组织卡片 ─── */
.vbar-card {
  background: #fff;
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
  padding: 14px 12px 12px;
  cursor: pointer;
  transition: box-shadow .2s, transform .2s;
  min-width: 0;

  &:hover { box-shadow: 0 4px 16px rgba(0,0,0,.08); transform: translateY(-1px); }

  &--empty { opacity: .5; cursor: default; &:hover { box-shadow: none; transform: none; } }

  &__header {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 6px; gap: 6px;
  }
  &__name {
    font-size: 14px; font-weight: 600; color: var(--el-text-color-primary);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  &__total {
    font-size: 12px; color: var(--el-text-color-placeholder);
    white-space: nowrap; flex-shrink: 0;
  }

  // 图表区：Y轴 + 柱子
  &__chart {
    display: flex; gap: 4px; height: 126px;
  }
}

/* ─── Y 轴刻度 ─── */
.vbar-y {
  display: flex; flex-direction: column; justify-content: space-between;
  width: 28px; flex-shrink: 0;

  &__tick {
    font-size: 11px; color: var(--el-text-color-placeholder);
    line-height: 1; text-align: right;
  }
}

/* ─── 柱子区域 ─── */
.vbar-bars {
  flex: 1; position: relative; min-width: 0;
}

/* ─── 横向网格线 ─── */
.vbar-grid-lines {
  position: absolute; inset: 0;
  display: flex; flex-direction: column; justify-content: space-between;
  pointer-events: none;

  .vbar-grid-line {
    border-top: 1px dashed var(--el-border-color-lighter);
    &.is-base { border-top-style: solid; border-color: var(--el-border-color-light); }
  }
}

/* ─── 单柱列：运行中柱 + 顶部数字 ─── */
.vbar-col {
  position: relative;
  height: 100%;
  display: flex; justify-content: center;

  &__bar-wrap {
    height: 100%;
    width: 100%; max-width: 60px;
    display: flex; align-items: flex-end; // 柱子从底部向上生长
  }

  &__bar {
    position: relative; // 数字 absolute 锚定柱顶
    width: 100%;
    border-radius: 4px 4px 0 0;
    background: #67C23A; // 运行中绿色
    transition: height .5s ease;
    overflow: visible;
  }

  &__num {
    // 锚定柱顶上方外侧：柱矮时数字上浮、不向下溢出，杜绝落到横轴下方
    position: absolute;
    bottom: calc(100% + 4px); // 数字底部 = 柱顶上方 4px
    left: 50%;
    transform: translateX(-50%);
    font-size: 12px; font-weight: 700;
    color: var(--el-text-color-primary); // 数字在柱顶上方、卡片白色背景上，用深色字保证可读
    line-height: 1; white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }
}

/* ─── 底部辅助数字（完成/终止，左缩进对齐柱子区） ─── */
.vbar-sub {
  display: flex; justify-content: space-around;
  padding-left: 32px; // 28px Y轴 + 4px gap
  margin-top: 4px; gap: 6px;
  font-size: 12px; color: var(--el-text-color-secondary);
  span { flex: 1; text-align: center; white-space: nowrap; }
}

.bar-empty {
  text-align: center; padding: 36px 0; color: var(--el-text-color-secondary); font-size: 13px;
}
</style>
