<template>
  <div class="org-management">
    <!-- 搜索栏 -->
    <div class="search-bar">
      <el-form :inline="true" :model="query">
        <el-form-item label="状态">
          <el-select v-model="query.is_active" placeholder="全部" clearable style="width: 120px" @change="handleSearch">
            <el-option label="启用" :value="true" />
            <el-option label="停用" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button type="success" @click="openCreate">新增组织</el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 组织列表 -->
    <div class="table-section">
      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="组织名称" min-width="150" />
        <el-table-column prop="description" label="描述" min-width="200">
          <template #default="{ row }">
            {{ row.description || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="所长" width="120">
          <template #default="{ row }">
            {{ row.manager_name || '未设置' }}
          </template>
        </el-table-column>
        <el-table-column prop="user_count" label="用户数" width="80" align="center" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">
            {{ row.created_at ? new Date(row.created_at).toLocaleString('zh-CN') : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-popconfirm
              :title="row.is_active ? '确认停用该组织？' : '确认启用该组织？'"
              @confirm="handleToggleStatus(row)"
            >
              <template #reference>
                <el-button size="small" :type="row.is_active ? 'warning' : 'success'">
                  {{ row.is_active ? '停用' : '启用' }}
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @change="fetchList"
        />
      </div>
    </div>

    <!-- 新增/编辑弹窗 -->
    <OrgFormDialog
      v-model="formVisible"
      :is-edit="!!editingOrg"
      :initial-data="editingOrg"
      @submit="handleFormSubmit"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getOrganizations, createOrganization, updateOrganization, toggleOrgStatus, type OrgItem } from '@/api/admin'
import OrgFormDialog from './components/OrgFormDialog.vue'

const loading = ref(false)
const list = ref<OrgItem[]>([])
const total = ref(0)

const query = reactive({
  page: 1,
  page_size: 20,
  is_active: null as boolean | null,
})

const formVisible = ref(false)
const editingOrg = ref<{ name: string; description: string | null } | null>(null)

onMounted(() => { fetchList() })

async function fetchList() {
  loading.value = true
  try {
    const data = await getOrganizations({
      page: query.page,
      page_size: query.page_size,
      is_active: query.is_active ?? undefined,
    })
    list.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  query.page = 1
  fetchList()
}

function openCreate() {
  editingOrg.value = null
  formVisible.value = true
}

function openEdit(row: OrgItem) {
  editingOrg.value = { name: row.name, description: row.description }
  formVisible.value = true
}

async function handleFormSubmit(data: { name: string; description: string | null }) {
  if (editingOrg.value) {
    const org = list.value.find(o => o.name === editingOrg.value?.name)
    if (org) {
      await updateOrganization(org.id, data)
      ElMessage.success('组织信息已更新')
    } else {
      ElMessage.error('组织不存在，可能已被删除')
    }
  } else {
    await createOrganization(data)
    ElMessage.success('组织创建成功')
  }
  fetchList()
}

async function handleToggleStatus(row: OrgItem) {
  await toggleOrgStatus(row.id, !row.is_active)
  ElMessage.success(row.is_active ? '已停用' : '已启用')
  fetchList()
}
</script>

<style lang="scss" scoped>
.org-management {
  .search-bar { display: flex; justify-content: center; margin-bottom: 16px; }
  .table-section {
    background: #fff;
    border: 1px solid var(--el-border-color-light);
    border-radius: 8px;
    overflow: hidden;
  }
  .pagination-wrap { display: flex; justify-content: flex-end; padding: 12px 16px; }
}
</style>
