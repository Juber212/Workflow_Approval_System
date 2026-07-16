<template>
  <div class="admin-page">
    <!-- 面包屑导航 -->
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="page-header__info">
        <h1 class="page-header__title">系统管理</h1>
        <p class="page-header__subtitle">用户、组织、角色及系统配置维护（仅系统管理员可见）</p>
      </div>
    </div>

    <!-- Tab 切换 -->
    <el-tabs :model-value="activeTab" @update:model-value="handleTabChange" class="admin-tabs">
      <el-tab-pane label="用户管理" name="users" />
      <el-tab-pane label="组织管理" name="organizations" />
      <el-tab-pane label="角色管理" name="roles" />
      <el-tab-pane label="系统配置" name="config" />
    </el-tabs>

    <!-- 根据当前 Tab 渲染对应组件 -->
    <UserManagement v-if="activeTab === 'users'" />
    <OrganizationManagement v-else-if="activeTab === 'organizations'" />
    <RoleManagement v-else-if="activeTab === 'roles'" />
    <ConfigManagement v-else-if="activeTab === 'config'" />
    <el-empty v-else :description="tabPlaceholder[activeTab] || '即将实现'" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useBreadcrumb } from '@/composables/useBreadcrumb'
import UserManagement from './UserManagement.vue'
import OrganizationManagement from './OrganizationManagement.vue'
import RoleManagement from './RoleManagement.vue'
import ConfigManagement from './ConfigManagement.vue'

const route = useRoute()
const router = useRouter()
const { setBreadcrumb } = useBreadcrumb()

onMounted(() => {
  setBreadcrumb([{ label: '首页', to: '/dashboard' }, { label: '系统管理' }])
})

/** 当前激活的 Tab（从路由路径推断） */
const activeTab = computed(() => {
  const path = route.path
  if (path.includes('/organizations')) return 'organizations'
  if (path.includes('/roles')) return 'roles'
  if (path.includes('/config')) return 'config'
  return 'users'
})

/** Tab 占位提示 */
const tabPlaceholder: Record<string, string> = {
  organizations: '组织管理',
  roles: '角色管理',
  config: '系统配置',
}

/** Tab 切换 → 路由跳转 */
function handleTabChange(tab: string) {
  router.push(`/admin/${tab}`)
}
</script>

<style lang="scss" scoped>
.admin-page {
  /* max-width 由 AppLayout 内容区统一控制 */

  .admin-tabs {
    margin-bottom: 20px;
  }
}
</style>
