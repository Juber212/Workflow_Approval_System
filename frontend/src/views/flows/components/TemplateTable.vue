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
      <el-select v-model="statusFilter" placeholder="状态筛选" clearable style="width: 140px" @change="emitSearch">
        <el-option label="草稿" value="draft" />
        <el-option label="已发布" value="published" />
        <el-option label="已停用" value="disabled" />
      </el-select>
      <el-button type="primary" @click="$emit('create')">新建模板</el-button>
    </div>

    <!-- 表格 -->
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="模板名称" min-width="150" />
      <el-table-column prop="organization_name" label="所属组织" width="120" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="current_version" label="版本" width="70" align="center" />
      <el-table-column prop="node_count" label="节点数" width="80" align="center" />
      <el-table-column label="创建人" width="100">
        <template #default="{ row }">{{ row.created_by_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="更新时间" width="170">
        <template #default="{ row }">{{ row.updated_at ? new Date(row.updated_at).toLocaleString('zh-CN') : '-' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="320" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="$emit('detail', row.id)">详情</el-button>
          <el-button v-if="row.can_edit" size="small" @click="$emit('edit', row)">编辑</el-button>
          <el-button v-if="row.can_publish" size="small" type="success" @click="$emit('publish', row.id)">发布</el-button>
          <el-button v-if="row.status === 'published'" size="small" type="warning" @click="$emit('disable', row.id)">停用</el-button>
          <el-button v-if="row.status === 'published' || row.status === 'disabled'" size="small" plain @click="$emit('newVersion', row.id)">新版本</el-button>
          <el-button v-if="row.can_start" size="small" type="primary" @click="$emit('start', row.id)">发起</el-button>
          <el-popconfirm v-if="row.can_edit" title="确认删除？" @confirm="$emit('delete', row.id)">
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

const emit = defineEmits<{
  search: [params: { keyword: string; status: string }]
  create: []
  detail: [id: number]
  edit: [row: TemplateItem]
  publish: [id: number]
  disable: [id: number]
  newVersion: [id: number]
  start: [id: number]
  delete: [id: number]
  pageChange: [page: number]
}>()

const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')
const statusFilter = ref('')

function emitSearch() {
  emit('search', { keyword: keyword.value, status: statusFilter.value })
}

function statusTag(s: string) {
  if (s === 'published') return 'success'
  if (s === 'disabled') return 'danger'
  return 'info'
}

function statusLabel(s: string) {
  if (s === 'published') return '已发布'
  if (s === 'disabled') return '已停用'
  return '草稿'
}
</script>

<style lang="scss" scoped>
.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
