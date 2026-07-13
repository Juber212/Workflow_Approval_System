<template>
  <el-card shadow="never">
    <template #header>版本历史</template>

    <el-timeline v-if="versions.length > 0">
      <el-timeline-item
        v-for="v in versions"
        :key="v.id"
        :timestamp="formatTime(v.published_at)"
        placement="top"
        :color="v.status === 'published' ? '#67c23a' : '#f56c6c'"
      >
        <div class="version-item">
          <p class="version-title">
            <strong>v{{ v.version_number }}</strong>
            <el-tag :type="v.status === 'published' ? 'success' : 'danger'" size="small" style="margin-left: 8px">
              {{ v.status === 'published' ? '已发布' : '已停用' }}
            </el-tag>
            <el-tag v-if="v.has_soft_overrides" type="warning" size="small" style="margin-left: 4px">
              有软修改
            </el-tag>
          </p>
          <p class="version-meta">
            {{ v.node_count }} 节点 · {{ v.edge_count }} 连线
            <template v-if="v.published_by_name"> · 发布人：{{ v.published_by_name }}</template>
          </p>
        </div>
      </el-timeline-item>
    </el-timeline>

    <el-empty v-else description="暂无发布版本" :image-size="60" />
  </el-card>
</template>

<script setup lang="ts">
import type { VersionItem } from '@/api/template'

defineProps<{ versions: VersionItem[] }>()

function formatTime(t: string | null) { return t ? new Date(t).toLocaleString('zh-CN') : '-' }
</script>

<style lang="scss" scoped>
.version-item {
  .version-title {
    margin-bottom: 4px;
  }
  .version-meta {
    color: var(--el-text-color-secondary);
    font-size: 13px;
    margin: 0;
  }
}
</style>
