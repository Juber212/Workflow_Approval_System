<template>
  <div class="template-table">
    <!-- 操作栏 -->
    <div class="toolbar">
      <el-input
        v-model="keyword"
        placeholder="搜索模板名称"
        clearable
        style="width: 220px"
        @change="emitSearch"
      />
      <el-button type="primary" @click="$emit('create')">新建模板</el-button>
    </div>

    <!-- 表格 -->
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="模板名称" min-width="150" />
      <el-table-column prop="organization_name" label="所属组织" width="120" />
      <el-table-column prop="node_count" label="节点数" width="80" align="center" />
      <el-table-column label="创建人" width="100">
        <template #default="{ row }">{{ row.created_by_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="更新时间" width="170">
        <template #default="{ row }">{{ row.updated_at ? new Date(row.updated_at).toLocaleString('zh-CN') : '-' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="$emit('detail', row.id)">详情</el-button>
          <el-button size="small" type="primary" @click="$emit('design', row.id)">设计</el-button>
          <el-button size="small" @click="$emit('edit', row)">编辑</el-button>
          <el-popconfirm title="确认删除？" @confirm="$emit('delete', row.id)">
            <template #reference>
              <el-button size="small" type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="pagination-wrap">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @change="$emit('pageChange', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { TemplateItem } from '@/api/template'

defineProps<{
  items: TemplateItem[]
  loading: boolean
  total: number
}>()

defineEmits<{
  search: [params: { keyword: string }]
  create: []
  detail: [id: number]
  design: [id: number]
  edit: [row: TemplateItem]
  delete: [id: number]
  pageChange: [page: number]
}>()

const keyword = ref('')
const page = ref(1)
const pageSize = ref(20)

function emitSearch() {
  ;(getCurrentInstance()?.emit as any)('search', { keyword: keyword.value })
}

import { getCurrentInstance } from 'vue'
</script>

<style lang="scss" scoped>
.toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.pagination-wrap { display: flex; justify-content: flex-end; margin-top: 16px; }
</style>
