<template>
  <!-- 侧边栏 + 用户 Popover -->
  <aside class="sidebar" :class="{ 'is-collapsed': isCollapsed }">
    <!-- 品牌 Logo 行 -->
    <div class="sidebar-brand">
      <el-tooltip v-if="isCollapsed" content="展开侧边栏" placement="right">
        <span class="sidebar-brand__icon sidebar-brand__icon--toggle"
              @click="isCollapsed = false"
              @mouseenter="isBrandHovered = true"
              @mouseleave="isBrandHovered = false">
          <svg v-if="isBrandHovered" width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round">
            <rect x="1.5" y="3.5" width="17" height="13" rx="3" />
            <line x1="6" y1="3.5" x2="6" y2="16.5" />
          </svg>
          <img v-else src="/favicon.svg?v=7" alt="logo" class="sidebar-brand__logo" />
        </span>
      </el-tooltip>
      <template v-else>
        <router-link to="/dashboard" class="sidebar-brand__icon sidebar-brand__icon--link">
          <img src="/favicon.svg?v=7" alt="logo" class="sidebar-brand__logo" />
        </router-link>
        <div class="sidebar-brand__text">
          <router-link to="/dashboard" class="sidebar-brand__title">项目审批系统</router-link>
          <span class="sidebar-brand__sub">Workflow Approval</span>
        </div>
        <button class="sidebar-toggle" @click="handleCollapse" title="折叠侧边栏">
          <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round">
            <rect x="1.5" y="3.5" width="17" height="13" rx="3" />
            <line x1="6" y1="3.5" x2="6" y2="16.5" />
          </svg>
        </button>
      </template>
    </div>

    <!-- 导航菜单 -->
    <nav class="sidebar-nav">
      <el-tooltip v-for="item in menuItems" :key="item.path"
                  :content="item.label" placement="right" :disabled="!isCollapsed">
        <router-link :to="item.path" class="sidebar-nav__item"
                     :class="{ 'is-active': isMenuActive(item.path) }">
          <el-icon :size="20"><component :is="item.icon" /></el-icon>
          <span class="sidebar-nav__label">{{ item.label }}</span>
          <!-- 个人中心通知红点 -->
          <span v-if="item.path === '/profile' && notifyStore.hasPending && isCollapsed" class="sidebar-nav__dot" />
          <span v-if="item.path === '/profile' && notifyStore.totalPending > 0 && !isCollapsed" class="sidebar-nav__badge">
            {{ notifyStore.totalPending > 99 ? '99+' : notifyStore.totalPending }}
          </span>
        </router-link>
      </el-tooltip>
    </nav>

    <!-- 底部用户区 -->
    <div class="sidebar-user" @click="showUserPopover = !showUserPopover" ref="userBtnRef">
      <span class="sidebar-user__avatar">{{ avatarInitial }}</span>
      <div class="sidebar-user__info">
        <span class="sidebar-user__name">{{ userStore.userInfo?.real_name || '未登录' }}</span>
        <span class="sidebar-user__role">{{ roleLabel }}</span>
      </div>
    </div>

    <!-- 用户操作 Popover -->
    <Teleport to="body">
      <div v-if="showUserPopover" class="user-popover-mask" @click="showUserPopover = false" />
      <div v-if="showUserPopover" class="user-popover" :style="popoverStyle">
        <div class="user-popover__head">
          <span class="user-popover__avatar">{{ avatarInitial }}</span>
          <div>
            <div class="user-popover__name">{{ userStore.userInfo?.real_name || '未登录' }}</div>
            <div class="user-popover__org">{{ userStore.userInfo?.organization_name || '-' }}</div>
          </div>
        </div>
        <div class="user-popover__divider" />
        <button class="user-popover__item" @click="openUserInfo">个人信息</button>
        <button class="user-popover__item" @click="openPassword">修改密码</button>
        <div class="user-popover__divider" />
        <button class="user-popover__item user-popover__item--danger" @click="handleLogout">退出登录</button>
      </div>
    </Teleport>
  </aside>
</template>

<script setup lang="ts">
/** 侧边栏导航 + 用户操作 popover */
import { ref, computed, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Monitor, Document, Setting, User, Files } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { useNotificationStore } from '@/stores/notification'

const emit = defineEmits<{
  'open-user-info': []
  'open-password': []
}>()

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const notifyStore = useNotificationStore()

// ==================== 侧边栏折叠状态 ====================
const isCollapsed = ref(false)
const isBrandHovered = ref(false)

function handleCollapse() {
  isCollapsed.value = true
  isBrandHovered.value = false
}

// ==================== 菜单项 ====================
const isAdmin = computed(() => userStore.userInfo?.roles.includes('system_admin') ?? false)

const roleLabel = computed(() => {
  const roles = userStore.userInfo?.roles || []
  if (roles.includes('system_admin')) return '系统管理员'
  if (roles.includes('manager')) return '所长'
  return '用户'
})

const MENU_ICONS: Record<string, Component> = {
  '/dashboard': Monitor,
  '/flows': Document,
  '/proposals': Files,
  '/admin/users': Setting,
  '/profile': User,
}

interface MenuItem { path: string; label: string; icon: Component }

const menuItems = computed<MenuItem[]>(() => {
  const items: MenuItem[] = [
    { path: '/dashboard', label: '首页', icon: MENU_ICONS['/dashboard'] },
    { path: '/flows', label: '项目管理', icon: MENU_ICONS['/flows'] },
    { path: '/proposals', label: '方案管理', icon: MENU_ICONS['/proposals'] },
  ]
  if (isAdmin.value) {
    items.push({ path: '/admin/users', label: '系统管理', icon: MENU_ICONS['/admin/users'] })
  } else {
    items.push({ path: '/profile', label: '个人中心', icon: MENU_ICONS['/profile'] })
  }
  return items
})

function isMenuActive(base: string): boolean {
  const p = route.path
  if (base === '/admin/users') return p.startsWith('/admin')
  if (base === '/profile') return p.startsWith('/profile')
  if (base === '/proposals') return p.startsWith('/proposals')
  return p === base || p.startsWith(base + '/')
}

// ==================== 用户 Popover ====================
const showUserPopover = ref(false)
const userBtnRef = ref<HTMLElement | null>(null)

const avatarInitial = computed(() => {
  const name = userStore.userInfo?.real_name || ''
  return name.charAt(0) || '?'
})

const popoverStyle = computed(() => {
  if (!userBtnRef.value) return {}
  const rect = userBtnRef.value.getBoundingClientRect()
  return {
    position: 'fixed' as const,
    left: '16px',
    bottom: `${window.innerHeight - rect.top + 12}px`,
    width: '208px',
  }
})

function openUserInfo() {
  showUserPopover.value = false
  emit('open-user-info')
}

function openPassword() {
  showUserPopover.value = false
  emit('open-password')
}

async function handleLogout() {
  showUserPopover.value = false
  await userStore.logout()
  notifyStore.clearAll()
  router.push('/login')
}
</script>

<style lang="scss" scoped>
/* ==================== 侧边栏 ==================== */
.sidebar {
  width: var(--sidebar-width);
  flex-shrink: 0;
  background: #fff;
  border-right: 1px solid var(--el-border-color-lighter);
  display: flex;
  flex-direction: column;
  user-select: none;
  z-index: 10;
  transition: width 0.2s ease;
  position: relative;

  &.is-collapsed {
    width: 60px;
    .sidebar-brand { justify-content: center; padding: 16px 8px 12px; }
    .sidebar-nav { padding: 4px 8px; }
    .sidebar-nav__item { justify-content: center; padding: 0; border-radius: 8px; height: 44px; }
    .sidebar-nav__label { display: none; }
    .sidebar-nav__item.is-active { box-shadow: none; }
    .sidebar-user { justify-content: center; padding: 12px 8px; }
    .sidebar-user__info { display: none; }
  }
}

.sidebar-toggle {
  display: flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; padding: 0; margin-left: auto; flex-shrink: 0;
  border: none; background: transparent; border-radius: 6px;
  cursor: pointer; color: var(--el-text-color-secondary);
  transition: background 0.15s, color 0.15s;
  &:hover { background: #f2f3f5; color: var(--el-text-color-primary); }
}

.sidebar-brand {
  display: flex; align-items: center; gap: 12px;
  padding: 16px 16px 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  margin-bottom: 8px;
  transition: padding 0.2s ease;

  &__icon {
    display: inline-flex; align-items: center; justify-content: center;
    width: 36px; height: 36px; border-radius: 8px; flex-shrink: 0;
    &--link { text-decoration: none; }
    &--toggle { cursor: pointer; transition: background 0.15s; &:hover { background: var(--el-fill-color); } }
  }
  &__logo { display: block; width: 32px; height: 32px; }
  &__text { display: flex; flex-direction: column; min-width: 0; }
  &__title {
    font-size: 15px; font-weight: 600; color: var(--el-text-color-primary);
    text-decoration: none; white-space: nowrap;
    &:hover { color: var(--color-primary); }
  }
  &__sub {
    font-size: 11px; color: var(--el-text-color-placeholder);
    margin-top: 1px; letter-spacing: 0.3px;
  }
}

/* 侧边栏导航菜单 */
.sidebar-nav {
  flex: 1; padding: 4px 12px;
  display: flex; flex-direction: column; gap: 2px;
  transition: padding 0.2s ease;

  &__item {
    position: relative; display: flex; align-items: center; gap: 10px;
    height: 40px; padding: 0 12px; border-radius: 6px;
    font-size: 14px; font-weight: 500;
    color: var(--el-text-color-regular); text-decoration: none;
    white-space: nowrap; transition: all 0.15s;
    &:hover { background: #f2f3f5; }
    &.is-active {
      color: var(--color-primary); background: #e8f0fe;
      box-shadow: inset 3px 0 0 var(--color-primary);
    }
  }
  &__label { transition: opacity 0.15s; }

  &__badge {
    width: 20px; height: 20px; border-radius: 50%;
    background: var(--el-color-danger); color: #fff;
    font-size: 11px; font-weight: 700;
    display: inline-flex; align-items: center; justify-content: center;
    flex-shrink: 0; line-height: 1; margin-left: auto;
  }
  &__dot {
    position: absolute; top: 6px; right: 6px;
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--el-color-danger);
  }
}

/* 侧边栏底部用户区 */
.sidebar-user {
  display: flex; align-items: center; gap: 10px; padding: 12px 16px;
  border-top: 1px solid var(--el-border-color-lighter);
  cursor: pointer; transition: all 0.2s;
  &:hover { background: #f2f3f5; }
  &__avatar {
    display: inline-flex; align-items: center; justify-content: center;
    width: 32px; height: 32px; border-radius: 50%;
    background: var(--color-primary); color: #fff;
    font-size: 14px; font-weight: 600; flex-shrink: 0;
  }
  &__info { display: flex; flex-direction: column; min-width: 0; }
  &__name {
    font-size: 13px; font-weight: 500; color: var(--el-text-color-primary);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  &__role { font-size: 11px; color: var(--el-text-color-placeholder); }
}
</style>
