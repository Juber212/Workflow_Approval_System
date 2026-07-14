<template>
  <el-card shadow="never">
    <template #header>基础信息</template>
    <el-descriptions :column="2" border>
      <el-descriptions-item label="模板名称">{{ detail.name }}</el-descriptions-item>
      <el-descriptions-item label="所属组织">{{ detail.organization_name || '-' }}</el-descriptions-item>
      <el-descriptions-item label="节点数">{{ detail.node_count }}</el-descriptions-item>
      <el-descriptions-item label="运行中实例">{{ detail.instance_count }}</el-descriptions-item>
      <el-descriptions-item label="创建人">{{ detail.created_by_name || '-' }}</el-descriptions-item>
      <el-descriptions-item label="创建时间">{{ formatTime(detail.created_at) }}</el-descriptions-item>
      <el-descriptions-item label="描述" :span="2">{{ detail.description || '-' }}</el-descriptions-item>
    </el-descriptions>
  </el-card>
</template>

<script setup lang="ts">
import type { TemplateDetail } from '@/api/template'

defineProps<{ detail: TemplateDetail }>()

function formatTime(t: string | null) { return t ? new Date(t).toLocaleString('zh-CN') : '-' }
</script>
