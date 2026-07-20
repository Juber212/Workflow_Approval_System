<template>
  <!-- 方案组织卡片列表 -->
  <div class="org-card-list">
    <div
      v-for="org in orgs"
      :key="org.id"
      class="org-card"
      @click="$emit('select', org.id)"
    >
      <div class="org-card__head">
        <span class="org-card__name">{{ org.name }}</span>
      </div>

      <!-- 大号数字：方案总数 -->
      <div class="org-card__metric">
        <span class="org-card__num">{{ org.total_count }}</span>
        <span class="org-card__unit">个方案</span>
      </div>

      <!-- 底部：各状态细分 -->
      <div class="org-card__meta">
        <span class="meta-item meta-item--running">运行中 {{ org.running_count }}</span>
        <span class="meta-divider">·</span>
        <span class="meta-item meta-item--completed">已完成 {{ org.completed_count }}</span>
        <span class="meta-divider">·</span>
        <span class="meta-item">已终止 {{ org.terminated_count }}</span>
      </div>
      <div class="org-card__time" v-if="org.latest_update_time">
        最近更新：{{ fmtTime(org.latest_update_time) }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ProposalOrgCardItem } from '@/api/proposal'

defineProps<{ orgs: ProposalOrgCardItem[] }>()
defineEmits<{ select: [orgId: number] }>()

function fmtTime(val: string): string {
  return val.replace('T', ' ').substring(5, 16)
}
</script>

<style lang="scss" scoped>
.org-card-list {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
  margin-top: 0;
}

.org-card {
  background: #fff;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 24px;
  cursor: pointer;
  transition: box-shadow 0.15s, transform 0.15s;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
  gap: 12px;

  &:hover {
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
    transform: translateY(-2px);
  }

  &__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  &__name {
    font-size: 16px;
    font-weight: 600;
  }

  &__metric {
    display: flex;
    align-items: baseline;
    gap: 8px;
  }

  &__num {
    font-size: 28px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }

  &__unit {
    font-size: 13px;
    color: var(--el-text-color-secondary);
  }

  &__meta {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
    border-top: 1px solid var(--el-border-color-lighter);
    padding-top: 10px;
  }

  &__time {
    font-size: 11px;
    color: var(--el-text-color-placeholder);
  }
}

.meta-item {
  &--running { color: var(--el-color-primary); }
  &--completed { color: var(--el-color-success); }
}

.meta-divider {
  color: var(--el-border-color);
}
</style>
