<template>
  <el-container class="app-layout">
    <!-- 顶部导航栏 -->
    <el-header class="app-header">
      <div class="app-header__left">
        <!-- 品牌 Logo -->
        <router-link to="/dashboard" class="app-brand">
          <span class="topnav-logo-icon">流</span>
          <span class="app-brand__text">企业流程审批系统</span>
        </router-link>

        <!-- 主导航菜单 -->
        <el-menu
          :default-active="activeMenu"
          mode="horizontal"
          router
          class="app-menu"
        >
          <el-menu-item index="/dashboard">Dashboard</el-menu-item>
          <el-menu-item index="/flows">流程管理</el-menu-item>
          <!-- 系统管理员不参与业务，隐藏个人中心菜单 -->
          <el-menu-item v-if="!isAdmin" index="/profile">个人中心</el-menu-item>
          <!-- 仅系统管理员可见系统管理菜单 -->
          <el-menu-item v-if="isAdmin" index="/admin/users">系统管理</el-menu-item>
        </el-menu>
      </div>

      <!-- 用户下拉 -->
      <div class="app-header__right">
        <el-dropdown v-if="userStore.isLoggedIn" trigger="click">
          <span class="user-dropdown">
            <span class="user-avatar">{{ avatarInitial }}</span>
            <span class="user-name">{{ userStore.userInfo?.real_name || '未登录' }}</span>
            <el-icon class="user-caret"><ArrowDown /></el-icon>
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

/** 头像显示的文字（用户姓名首字） */
const avatarInitial = computed(() => {
  const name = userStore.userInfo?.real_name || ''
  return name.charAt(0) || '?'
})

async function handleLogout() {
  await userStore.logout()
  router.push('/login')
}
</script>

<style lang="scss" scoped>
.app-layout {
  height: 100%;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  border-bottom: 1px solid var(--el-border-color-light);
  height: 56px;
  background: #fff;

  &__left {
    display: flex;
    align-items: center;
    gap: 32px;
    height: 100%;
  }

  &__right {
    display: flex;
    align-items: center;
  }
}

/* 品牌标识 */
.app-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  flex-shrink: 0;

  &__text {
    font-size: 16px;
    font-weight: 600;
    color: var(--el-text-color-primary);
    white-space: nowrap;
  }
}

/* 导航菜单 */
.app-menu {
  border-bottom: none !important;

  :deep(.el-menu-item) {
    height: 56px;
    line-height: 56px;
    font-size: 14px;
  }
}

/* 用户区域 */
.user-dropdown {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: 6px;
  transition: background 0.15s;

  &:hover {
    background: var(--el-fill-color-light);
  }
}

/* 用户头像（首字圆形） */
.user-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--el-color-primary);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}

.user-name {
  font-size: 14px;
  color: var(--el-text-color-regular);
}

.user-caret {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

/* 主内容区 */
.app-main {
  background: var(--el-bg-color-page);
  padding: 24px;
  min-height: calc(100vh - 56px);
}
</style>
