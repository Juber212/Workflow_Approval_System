<template>
  <!-- 组织卡片列表（PRD P03） -->
  <div class="org-card-list">
    <div
      v-for="org in orgs"
      :key="org.id"
      :class="['org-card', { 'is-current': org.is_current_user_org }]"
      @click="$emit('select', org.id)"
    >
      <!-- 顶部：组织名 + 当前所属标记 -->
      <div class="org-card__head">
        <span class="org-card__name">{{ org.name }}</span>
        <span v-if="org.is_current_user_org" class="org-card__badge">当前所属</span>
      </div>

      <!-- 中间：大号数字 -->
      <div class="org-card__metric">
        <span class="org-card__num" :class="{ 'is-warn': org.running_instance_count > 5 }">
          {{ org.running_instance_count }}
        </span>
        <span class="org-card__unit">个运行中实例</span>
      </div>

      <!-- 底部：更新时间 + 模板数 -->
      <div class="org-card__meta">
        最近更新：{{ org.latest_update_time ? fmtTime(org.latest_update_time) : '—' }} · 模板 {{ org.template_count }} 个
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { OrgCardItem } from '@/api/template'

defineProps<{ orgs: OrgCardItem[] }>()
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
  transition: box-shadow 0.15s, border-color 0.15s, transform 0.15s;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
  gap: 14px;

  &:hover {
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
    transform: translateY(-2px);
  }

  // 当前所属：蓝色边框（P03 规范）
  &.is-current {
    border-color: var(--el-color-primary);
    border-width: 2px;
    padding: 23px; // 补偿 border 增加的 2px
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

  &__badge {
    font-size: 12px;
    color: var(--el-color-primary);
    background: var(--el-color-primary-light-9);
    padding: 2px 10px;
    border-radius: 999px;
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

    &.is-warn {
      color: var(--el-color-danger);
    }
  }

  &__unit {
    font-size: 13px;
    color: var(--el-text-color-secondary);
  }

  &__meta {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    border-top: 1px solid var(--el-border-color-lighter);
    padding-top: 12px;
  }
}
</style>
