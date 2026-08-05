<template>
  <!-- 详情页顶部摘要条 —— Task/Check/Approval/Endorse 四页共用（P2-2 抽取） -->
  <!-- 用法：title prop + 默认 slot 放 meta 项（meta 项间分隔符用 <span class="top-summary__sep">·</span>） -->
  <div class="top-summary">
    <h2 class="top-summary__title">
      {{ title }}
      <slot name="title-extra" />
    </h2>
    <div class="top-summary__meta">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  /** 摘要标题（实例名 / 实例名 · 节点名） */
  title: string
}>()
</script>

<style lang="scss" scoped>
.top-summary {
  background: #fff;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  padding: 20px 24px;
  margin-bottom: 16px;

  &__title {
    font-size: 20px; font-weight: 600;
    color: var(--el-text-color-primary);
    margin: 0 0 8px;
  }

  &__meta {
    display: flex; align-items: center; gap: 4px;
    font-size: 13px; color: var(--el-text-color-secondary);
    flex-wrap: wrap;
    /* slot 内容由父组件提供，样式在此统一 */
    :slotted(b) { color: var(--el-text-color-primary); }
    :slotted(.top-summary__sep) { color: var(--el-text-color-placeholder); margin: 0 4px; }
  }
}
</style>
