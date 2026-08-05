<template>
  <div class="user-management">
    <!-- 搜索栏 -->
    <div class="search-bar">
      <div class="search-bar__filters">
        <el-form :inline="true" :model="query" @submit.prevent="handleSearch" style="margin-bottom:0">
          <el-form-item label="关键词">
            <el-input v-model="query.keyword" placeholder="用户名/姓名" clearable @clear="handleSearch" />
          </el-form-item>
          <el-form-item label="组织">
            <el-select v-model="query.organization_id" placeholder="全部" clearable style="width: 160px" @change="handleSearch">
              <el-option v-for="org in orgOptions" :key="org.id" :label="org.name" :value="org.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="query.is_active" placeholder="全部" clearable style="width: 120px" @change="handleSearch">
              <el-option label="启用" :value="true" />
              <el-option label="禁用" :value="false" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSearch">搜索</el-button>
          </el-form-item>
        </el-form>
      </div>
      <div class="search-bar__actions">
        <el-button type="success" @click="openCreate">新增用户</el-button>
      </div>
    </div>

    <!-- 用户列表 -->
    <div class="table-section">
      <el-table border :data="list" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column prop="real_name" label="姓名" width="100" />
        <el-table-column label="角色" min-width="120">
          <template #default="{ row }">
            <el-tag
              v-for="role in row.roles"
              :key="role"
              :type="role === 'system_admin' ? 'danger' : role === 'manager' ? 'warning' : 'info'"
              size="small"
              style="margin-right: 4px"
            >
              {{ roleNameMap[role] || role }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="organization_name" label="所属组织" width="120" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">
            {{ row.created_at ? new Date(row.created_at).toLocaleString('zh-CN') : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" @click="openResetPassword(row)">重置密码</el-button>
            <el-popconfirm
              :title="row.is_active ? '确认禁用该用户？' : '确认启用该用户？'"
              @confirm="handleToggleStatus(row)"
            >
              <template #reference>
                <el-button size="small" :type="row.is_active ? 'warning' : 'success'">
                  {{ row.is_active ? '禁用' : '启用' }}
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
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
    <UserFormDialog
      v-model="formVisible"
      :is-edit="!!editingUser"
      :initial-data="editingUser"
      :org-options="orgOptions"
      :role-options="roleOptions"
      @submit="handleFormSubmit"
    />

    <!-- 重置密码弹窗 -->
    <ResetPasswordDialog
      v-model="resetPwdVisible"
      :username="resetPwdUsername"
      @submit="handleResetPwdSubmit"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getUsers,
  createUser,
  updateUser,
  toggleUserStatus,
  resetUserPassword,
  getOrgOptions,
  getRoleOptions,
  type UserItem,
  type OrgOption,
  type RoleOption,
} from '@/api/admin'
import UserFormDialog from './components/UserFormDialog.vue'
import ResetPasswordDialog from './components/ResetPasswordDialog.vue'

/** 角色名称映射 */
const roleNameMap: Record<string, string> = {
  system_admin: '系统管理员',
  manager: '所长',
  user: '普通用户',
}

// ========== 数据状态 ==========
const loading = ref(false)
const list = ref<UserItem[]>([])
const total = ref(0)
const orgOptions = ref<OrgOption[]>([])
const roleOptions = ref<RoleOption[]>([])

const query = reactive({
  page: 1,
  page_size: 20,
  keyword: '',
  organization_id: null as number | null,
  is_active: null as boolean | null,
})

// ========== 弹窗状态 ==========
const formVisible = ref(false)
/** 正在编辑的用户初始数据 */
interface EditUserData {
  username: string
  real_name: string
  organization_id: number | null  // 管理员可为空
  roles: string[]
  email: string | null
  phone: string | null
}

const editingUser = ref<EditUserData | null>(null)
const resetPwdVisible = ref(false)
const resetPwdUsername = ref('')
const resetPwdUserId = ref(0)

// ========== 初始化 ==========
onMounted(async () => {
  await Promise.all([fetchList(), fetchOptions()])
})

async function fetchList() {
  loading.value = true
  try {
    const data = await getUsers({
      page: query.page,
      page_size: query.page_size,
      keyword: query.keyword || undefined,
      organization_id: query.organization_id ?? undefined,
      is_active: query.is_active ?? undefined,
    })
    list.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function fetchOptions() {
  try {
    const [orgs, roles] = await Promise.all([getOrgOptions(), getRoleOptions()])
    orgOptions.value = orgs
    roleOptions.value = roles
  } catch {
    // 选项加载失败时用户会看到空下拉框
  }
}

function handleSearch() {
  query.page = 1
  fetchList()
}

// ========== 新增/编辑 ==========
function openCreate() {
  editingUser.value = null
  formVisible.value = true
}

function openEdit(row: UserItem) {
  editingUser.value = {
    username: row.username,
    real_name: row.real_name,
    organization_id: row.organization_id,
    roles: row.roles,
    email: row.email,
    phone: row.phone,
  }
  formVisible.value = true
}

async function handleFormSubmit(data: any) {
  if (editingUser.value) {
    // 编辑 —— 从列表中查找用户 ID 并更新
    const target = list.value.find(u => u.username === editingUser.value?.username)
    if (!target) {
      ElMessage.error('用户不存在，可能已被删除')
      return
    }
    await updateUser(target.id, {
      real_name: data.real_name,
      organization_id: data.organization_id,
      role_id: data.role_id,
      email: data.email,
      phone: data.phone,
    })
    ElMessage.success('用户信息已更新')
  } else {
    await createUser({
      username: data.username,
      real_name: data.real_name,
      organization_id: data.organization_id,
      role_id: data.role_id,
      email: data.email,
      phone: data.phone,
    })
    ElMessage.success('用户创建成功，初始密码为系统默认密码')
  }
  fetchList()
  formVisible.value = false  // M22：提交成功后才关闭弹窗（失败时保留输入）
}

// ========== 启禁用 ==========
async function handleToggleStatus(row: UserItem) {
  try {
    await toggleUserStatus(row.id, !row.is_active)
    ElMessage.success(row.is_active ? '已禁用' : '已启用')
    fetchList()
  } catch {
    // 拦截器已统一弹错（P1-35），无需重复提示
  }
}

// ========== 重置密码 ==========
function openResetPassword(row: UserItem) {
  resetPwdUserId.value = row.id
  resetPwdUsername.value = row.username
  resetPwdVisible.value = true
}

async function handleResetPwdSubmit() {
  await resetUserPassword(resetPwdUserId.value)
  ElMessage.success('密码已重置为默认初始密码')
  resetPwdVisible.value = false  // M22：提交成功后才关闭弹窗
}
</script>

<style lang="scss" scoped>
.user-management {
  .search-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;

    :deep(.el-form),
    :deep(.el-form-item) { margin-bottom: 0; }
  }

  .table-section {
    background: #fff;
    border: 1px solid var(--el-border-color-light);
    border-radius: 8px;
    overflow: hidden;
  }

  .pagination-wrap {
    display: flex;
    justify-content: flex-end;
    padding: 12px 16px;
  }
}
</style>
