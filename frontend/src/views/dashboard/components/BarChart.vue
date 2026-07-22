<template>
  <!-- 各所项目概览横向分组柱状图 -->
  <div class="bar-chart-wrap">
    <div class="bar-chart__legend">
      <span class="bar-legend-item"><i class="bar-legend-dot" style="background:#5470C6"></i>全部项目</span>
      <span class="bar-legend-item"><i class="bar-legend-dot" style="background:#91CC75"></i>运行中</span>
      <span class="bar-legend-item"><i class="bar-legend-dot" style="background:#FAC858"></i>已完成</span>
    </div>
    <div class="bar-chart" v-if="items.length > 0">
      <div
        v-for="item in items"
        :key="item.org_id"
        class="bar-row"
        @click="$emit('org-click', item.org_id)"
      >
        <span class="bar-row__label" :title="item.org_name">{{ item.org_name }}</span>
        <div class="bar-row__bars">
          <div
            class="bar-row__bar bar--total"
            :style="{ width: barPct(item.total_count, maxTotal) }"
            :title="'全部：' + item.total_count"
          >
            <span class="bar-row__num" v-if="item.total_count > 0">{{ item.total_count }}</span>
          </div>
          <div
            class="bar-row__bar bar--running"
            :style="{ width: barPct(item.running_count, maxTotal) }"
            :title="'运行中：' + item.running_count"
          >
            <span class="bar-row__num" v-if="item.running_count > 0">{{ item.running_count }}</span>
          </div>
          <div
            class="bar-row__bar bar--completed"
            :style="{ width: barPct(item.completed_count, maxTotal) }"
            :title="'已完成：' + item.completed_count"
          >
            <span class="bar-row__num" v-if="item.completed_count > 0">{{ item.completed_count }}</span>
          </div>
        </div>
      </div>
    </div>
    <div v-else class="bar-empty">暂无数据</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { OrgOverview } from '@/api/dashboard'

const props = defineProps<{ items: OrgOverview[] }>()
defineEmits<{ 'org-click': [orgId: number] }>()

/** 最大总数（用于百分比基准） */
const maxTotal = computed(() => {
  const max = Math.max(...props.items.map(i => i.total_count), 1)
  return max
})

/** 百分比宽度 */
function barPct(val: number, max: number): string {
  if (val <= 0) return '0'
  return Math.max((val / max) * 100, 3).toFixed(1) + '%'
}
</script>

<style lang="scss" scoped>
.bar-chart-wrap {
  // 图例
  .bar-chart__legend {
    display: flex; gap: 20px; margin-bottom: 14px; font-size: 12px; color: var(--el-text-color-secondary);
    .bar-legend-dot { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; vertical-align: -1px; }
  }
}

.bar-chart {
  display: flex; flex-direction: column; gap: 10px;
}

.bar-row {
  display: flex; align-items: center; cursor: pointer; gap: 12px;
  padding: 4px 0; border-radius: 4px; transition: background .15s;
  &:hover { background: var(--el-fill-color-light); }

  &__label {
    width: 80px; flex-shrink: 0; text-align: right; font-size: 13px; font-weight: 500;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    color: var(--el-text-color-primary);
  }

  &__bars {
    flex: 1; display: flex; gap: 3px; height: 28px; align-items: center;
    min-width: 0; // 允许 flex 收缩
  }

  &__bar {
    height: 100%; border-radius: 4px; display: flex; align-items: center;
    justify-content: flex-end; min-width: 0; transition: width .4s ease;
    position: relative;
    &.bar--total    { background: #5470C6; }
    &.bar--running  { background: #91CC75; }
    &.bar--completed { background: #FAC858; }
  }

  &__num {
    font-size: 11px; font-weight: 600; color: #fff; padding: 0 6px;
    white-space: nowrap; line-height: 1;
    text-shadow: 0 1px 2px rgba(0,0,0,.25);
  }
}

.bar-empty {
  text-align: center; padding: 36px 0; color: var(--el-text-color-secondary); font-size: 13px;
}
</style>
