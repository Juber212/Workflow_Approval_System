<template>
  <div class="role-management">
    <el-card shadow="never">
      <template #header>
        <span>预置角色列表</span>
        <el-tag type="info" size="small" style="margin-left: 12px">V1 不可新增/删除</el-tag>
      </template>

      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="角色名称" width="120" />
        <el-table-column prop="code" label="角色标识" width="160">
          <template #default="{ row }">
            <el-tag :type="roleTagType(row.code)">{{ row.code }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="200">
          <template #default="{ row }">
            {{ row.description || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="user_count" label="用户数" width="80" align="center" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getRoles, type RoleItem } from '@/api/admin'

const loading = ref(false)
const list = ref<RoleItem[]>([])

onMounted(async () => {
  loading.value = true
  try {
    list.value = await getRoles()
  } finally {
    loading.value = false
  }
})

/** 角色标识对应的 Tag 类型 */
function roleTagType(code: string) {
  if (code === 'system_admin') return 'danger'
  if (code === 'manager') return 'warning'
  return 'info'
}
</script>
