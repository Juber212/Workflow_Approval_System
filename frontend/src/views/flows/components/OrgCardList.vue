<template>
  <div class="org-card-list">
    <el-card
      v-for="org in orgs"
      :key="org.id"
      :class="['org-card', { 'is-active': org.id === activeOrgId }]"
      shadow="hover"
      @click="$emit('select', org.id)"
    >
      <div class="org-card__name">{{ org.name }}</div>
      <div class="org-card__stats">
        <span>模板 {{ org.template_count }}</span>
        <span class="stat-divider">|</span>
        <span>运行中 {{ org.running_instance_count }}</span>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import type { OrgCardItem } from '@/api/template'

defineProps<{
  orgs: OrgCardItem[]
  activeOrgId: number | null
}>()

defineEmits<{
  select: [orgId: number]
}>()
</script>

<style lang="scss" scoped>
.org-card-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}

.org-card {
  cursor: pointer;
  transition: border-color 0.2s;

  &.is-active {
    border-color: var(--el-color-primary);
  }

  &__name {
    font-size: 15px;
    font-weight: 600;
    margin-bottom: 8px;
  }

  &__stats {
    font-size: 13px;
    color: var(--el-text-color-secondary);
  }
}

.stat-divider {
  margin: 0 8px;
}
</style>
