<template>
  <el-container class="app-layout">
    <!-- 顶部导航栏 -->
    <el-header class="app-header">
      <div class="app-header__left">
        <span class="app-logo">企业流程审批系统</span>
        <el-menu
          :default-active="activeMenu"
          mode="horizontal"
          router
          class="app-menu"
        >
          <el-menu-item index="/dashboard">首页看板</el-menu-item>
          <el-menu-item index="/flows">流程管理</el-menu-item>
          <!-- 系统管理员不参与业务，隐藏个人中心菜单 -->
          <el-menu-item v-if="!isAdmin" index="/profile">个人中心</el-menu-item>
          <!-- 仅系统管理员可见系统管理菜单 -->
          <el-menu-item v-if="isAdmin" index="/admin/users">系统管理</el-menu-item>
        </el-menu>
      </div>
      <div class="app-header__right">
        <el-dropdown v-if="userStore.isLoggedIn">
          <span class="user-dropdown">
            {{ userStore.userInfo?.real_name || '未登录' }}
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item>个人信息</el-dropdown-item>
              <el-dropdown-item>修改密码</el-dropdown-item>
              <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-header>

    <!-- 主内容区 -->
    <el-main class="app-main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowDown } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

/** 是否为系统管理员（不参与业务流程） */
const isAdmin = computed(() => userStore.userInfo?.roles.includes('system_admin') ?? false)

/** 当前激活菜单项 */
const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/admin')) return '/admin/users'
  return '/' + path.split('/')[1]
})

async function handleLogout() {
  await userStore.logout()
  router.push('/login')
}
</script>

<style lang="scss" scoped>
.app-layout { height: 100%; }

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  border-bottom: 1px solid var(--el-border-color-light);
  height: 56px;

  &__left {
    display: flex;
    align-items: center;
    gap: 32px;
  }

  &__right {
    display: flex;
    align-items: center;
  }
}

.app-logo { font-size: 16px; font-weight: 600; color: var(--el-color-primary); white-space: nowrap; }
.app-menu { border-bottom: none; }
.user-dropdown { cursor: pointer; display: flex; align-items: center; gap: 4px; }
.app-main { background: var(--el-bg-color-page); padding: 24px; }
</style>
