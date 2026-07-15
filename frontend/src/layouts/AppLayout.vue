<template>
  <!-- 侧边栏 + 顶栏 + 内容区布局（飞书风格） -->
  <div class="app-shell">
    <!-- ==================== 侧边栏 ==================== -->
    <aside class="sidebar">
      <!-- 品牌 Logo -->
      <router-link to="/dashboard" class="sidebar-brand">
        <span class="sidebar-brand__icon">流</span>
        <div class="sidebar-brand__text">
          <span class="sidebar-brand__title">流程审批系统</span>
          <span class="sidebar-brand__sub">Workflow Approval</span>
        </div>
      </router-link>

      <!-- 导航菜单（纯文字，无图标） -->
      <nav class="sidebar-nav">
        <router-link
          v-for="item in menuItems"
          :key="item.path"
          :to="item.path"
          class="sidebar-nav__item"
          :class="{ 'is-active': isMenuActive(item.path) }"
        >
          {{ item.label }}
        </router-link>
      </nav>

      <!-- 底部用户区 -->
      <div class="sidebar-user" @click="showUserPopover = !showUserPopover" ref="userBtnRef">
        <span class="sidebar-user__avatar">{{ avatarInitial }}</span>
        <div class="sidebar-user__info">
          <span class="sidebar-user__name">{{ userStore.userInfo?.real_name || '未登录' }}</span>
          <span class="sidebar-user__role">{{ roleLabel }}</span>
        </div>
      </div>
    </aside>

    <!-- ==================== 右侧区域 ==================== -->
    <div class="app-right">
      <!-- 窄顶栏：面包屑导航 -->
      <header class="topbar">
        <nav class="topbar-breadcrumb">
          <template v-for="(item, i) in breadcrumbs" :key="i">
            <span v-if="i > 0" class="breadcrumb-sep">/</span>
            <router-link v-if="item.to" :to="item.to" class="breadcrumb-link">{{ item.label }}</router-link>
            <span v-else class="breadcrumb-current">{{ item.label }}</span>
          </template>
        </nav>
      </header>

      <!-- 主内容区 -->
      <main class="app-content">
        <router-view />
      </main>
    </div>

    <!-- ==================== 用户操作 Popover ==================== -->
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

    <!-- ==================== 个人信息弹窗 ==================== -->
    <el-dialog v-model="showUserInfoDialog" title="个人信息" width="500px" :close-on-click-modal="false">
      <div class="user-info-panel" v-if="userStore.userInfo">
        <el-descriptions :column="2" border size="default">
          <el-descriptions-item label="用户名">{{ userStore.userInfo.username }}</el-descriptions-item>
          <el-descriptions-item label="姓名">{{ userStore.userInfo.real_name }}</el-descriptions-item>
          <el-descriptions-item label="所属组织">{{ userStore.userInfo.organization_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="角色">
            <el-tag v-for="r in userStore.userInfo.roles" :key="r" size="small" style="margin-right:4px">
              {{ roleTagLabel(r) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="邮箱">{{ userStore.userInfo.email || '-' }}</el-descriptions-item>
          <el-descriptions-item label="手机号">{{ userStore.userInfo.phone || '-' }}</el-descriptions-item>
        </el-descriptions>

        <!-- 签名上传 -->
        <el-divider />
        <div class="signature-section">
          <h4 class="signature-section__title">个人签名</h4>
          <p class="signature-section__desc">上传透明底 PNG 签名图片（推荐 200×60px，≤500KB），审批通过时自动插入 PDF。</p>
          <div class="signature-preview" v-if="userInfoDetail?.has_signature">
            <img :src="signaturePreviewUrl" alt="签名预览" class="signature-img" />
            <span class="signature-status">已上传</span>
          </div>
          <div class="signature-preview signature-preview--empty" v-else>
            <span class="signature-status">未上传签名</span>
          </div>
          <el-upload :show-file-list="false" :before-upload="handleSignatureUpload" accept="image/png,image/jpeg,image/gif,image/webp">
            <el-button type="primary" size="small" :loading="uploadingSignature">
              {{ userInfoDetail?.has_signature ? '更换签名' : '上传签名' }}
            </el-button>
          </el-upload>
        </div>
      </div>
    </el-dialog>

    <!-- ==================== 修改密码弹窗 ==================== -->
    <el-dialog v-model="showPasswordDialog" title="修改密码" width="420px" :close-on-click-modal="false">
      <el-form ref="pwdFormRef" :model="pwdForm" :rules="pwdRules" label-width="80px">
        <el-form-item label="原密码" prop="old_password">
          <el-input v-model="pwdForm.old_password" type="password" show-password placeholder="请输入原密码" />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="pwdForm.new_password" type="password" show-password placeholder="6-32位新密码" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm_password">
          <el-input v-model="pwdForm.confirm_password" type="password" show-password placeholder="再次输入新密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPasswordDialog = false">取消</el-button>
        <el-button type="primary" :loading="changingPwd" @click="handleChangePassword">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
/** 应用布局 —— 侧边栏 + 顶栏面包屑 + 内容区（飞书风格） */
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { getMeApi, changePasswordApi, uploadSignatureApi, toUserInfo } from '@/api/auth'
import { usePageBreadcrumb } from '@/composables/useBreadcrumb'
import type { BreadcrumbItem } from '@/router'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

// ==================== 菜单项 ====================
/** 是否为系统管理员 */
const isAdmin = computed(() => userStore.userInfo?.roles.includes('system_admin') ?? false)

/** 角色简写（侧边栏底部显示） */
const roleLabel = computed(() => {
  const roles = userStore.userInfo?.roles || []
  if (roles.includes('system_admin')) return '系统管理员'
  if (roles.includes('manager')) return '所长'
  return '用户'
})

/** 角色中文映射 */
function roleTagLabel(role: string): string {
  const m: Record<string, string> = { system_admin: '系统管理员', manager: '所长', user: '普通用户' }
  return m[role] || role
}

interface MenuItem { path: string; label: string }

const menuItems = computed<MenuItem[]>(() => {
  const items: MenuItem[] = [
    { path: '/dashboard', label: '首页' },
    { path: '/flows', label: '流程管理' },
  ]
  if (isAdmin.value) {
    items.push({ path: '/admin/users', label: '系统管理' })
  } else {
    items.push({ path: '/profile', label: '个人中心' })
  }
  return items
})

/** 判断菜单项是否激活 */
function isMenuActive(base: string): boolean {
  const p = route.path
  if (base === '/admin/users') return p.startsWith('/admin')
  if (base === '/profile') return p.startsWith('/profile')
  return p === base || p.startsWith(base + '/')
}

// ==================== 面包屑 ====================
/** 页面临时注入的动态面包屑 */
const injectedBreadcrumb = usePageBreadcrumb()

/** 面包屑：优先使用页面注入的动态值，否则用 route meta */
const breadcrumbs = computed<BreadcrumbItem[]>(() => {
  if (injectedBreadcrumb?.value) return injectedBreadcrumb.value
  const metaBreadcrumb = route.meta.breadcrumb as BreadcrumbItem[] | undefined
  if (metaBreadcrumb && metaBreadcrumb.length > 0) return metaBreadcrumb
  // 兜底：用页面 title
  const title = route.meta.title as string
  if (title) return [{ label: title }]
  return [{ label: '首页' }]
})

// ==================== 用户 Popover ====================
const showUserPopover = ref(false)
const userBtnRef = ref<HTMLElement | null>(null)

/** 用户头像首字 */
const avatarInitial = computed(() => {
  const name = userStore.userInfo?.real_name || ''
  return name.charAt(0) || '?'
})

/** Popover 定位在侧边栏底部用户按钮上方 */
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

function openUserInfo() { showUserPopover.value = false; showUserInfoDialog.value = true }
function openPassword() { showUserPopover.value = false; showPasswordDialog.value = true }

async function handleLogout() {
  showUserPopover.value = false
  await userStore.logout()
  router.push('/login')
}

// ==================== 个人信息弹窗 ====================
const showUserInfoDialog = ref(false)
const userInfoDetail = ref<{
  user_id: number; username: string; real_name: string
  email: string | null; phone: string | null; roles: string[]
  organization_id: number | null; organization_name: string | null
  has_signature: boolean
} | null>(null)
const uploadingSignature = ref(false)

const signaturePreviewUrl = computed(() => {
  if (!userInfoDetail.value?.user_id) return ''
  return `/api/v1/storage/signatures/${userInfoDetail.value.user_id}.png?t=${Date.now()}`
})

async function refreshUserInfoDetail() {
  try {
    const data = await getMeApi()
    userInfoDetail.value = data
    userStore.userInfo = toUserInfo(data)
  } catch {
    if (userStore.userInfo) {
      userInfoDetail.value = {
        user_id: userStore.userInfo.id, username: userStore.userInfo.username,
        real_name: userStore.userInfo.real_name, email: userStore.userInfo.email,
        phone: userStore.userInfo.phone, roles: userStore.userInfo.roles,
        organization_id: userStore.userInfo.organization_id,
        organization_name: userStore.userInfo.organization_name,
        has_signature: false,
      }
    }
  }
}

watch(showUserInfoDialog, async (val) => { if (val) await refreshUserInfoDetail() })

async function handleSignatureUpload(file: File): Promise<boolean> {
  if (file.size > 500 * 1024) { ElMessage.error('签名图片不能超过 500KB'); return false }
  const allowed = ['image/png', 'image/jpeg', 'image/gif', 'image/webp']
  if (!allowed.includes(file.type)) { ElMessage.error('仅支持 PNG/JPG/GIF/WebP 格式'); return false }
  uploadingSignature.value = true
  try {
    await uploadSignatureApi(file)
    ElMessage.success('签名图片已上传')
    await refreshUserInfoDetail()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '上传失败')
  } finally { uploadingSignature.value = false }
  return false
}

// ==================== 修改密码弹窗 ====================
const showPasswordDialog = ref(false)
const changingPwd = ref(false)
const pwdFormRef = ref<FormInstance>()
const pwdForm = ref({ old_password: '', new_password: '', confirm_password: '' })

const validateConfirmPassword = (_rule: any, value: string, callback: (err?: Error) => void) => {
  callback(value !== pwdForm.value.new_password ? new Error('两次输入的密码不一致') : undefined)
}

const pwdRules: FormRules = {
  old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 32, message: '密码长度 6-32 位', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
}

async function handleChangePassword() {
  const valid = await pwdFormRef.value?.validate().catch(() => false)
  if (!valid) return
  changingPwd.value = true
  try {
    await changePasswordApi({ old_password: pwdForm.value.old_password, new_password: pwdForm.value.new_password })
    ElMessage.success('密码修改成功，请重新登录')
    showPasswordDialog.value = false
    pwdForm.value = { old_password: '', new_password: '', confirm_password: '' }
    await userStore.logout()
    router.push('/login')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '修改失败')
  } finally { changingPwd.value = false }
}
</script>

<style lang="scss" scoped>
/* ==================== 整体外壳 ==================== */
.app-shell {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: var(--page-bg);
}

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
}

/* 侧边栏品牌标识 */
.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 20px 16px;
  text-decoration: none;
  border-bottom: 1px solid var(--el-border-color-lighter);
  margin-bottom: 8px;

  &__icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 36px; height: 36px;
    border-radius: 8px;
    background: var(--color-primary);
    color: #fff;
    font-size: 18px; font-weight: 700;
    flex-shrink: 0;
  }

  &__text {
    display: flex; flex-direction: column;
    min-width: 0;
  }

  &__title {
    font-size: 15px; font-weight: 600;
    color: var(--el-text-color-primary);
    white-space: nowrap;
  }

  &__sub {
    font-size: 11px; color: var(--el-text-color-placeholder);
    margin-top: 1px; letter-spacing: 0.3px;
  }
}

/* 侧边栏导航菜单（无图标纯文字） */
.sidebar-nav {
  flex: 1;
  padding: 4px 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;

  &__item {
    display: flex;
    align-items: center;
    height: 40px;
    padding: 0 12px;
    border-radius: 6px;
    font-size: 14px; font-weight: 500;
    color: var(--el-text-color-regular);
    text-decoration: none;
    white-space: nowrap;
    transition: background 0.15s, color 0.15s;

    &:hover { background: #f2f3f5; }

    &.is-active {
      color: var(--color-primary);
      background: #e8f0fe;
      box-shadow: inset 3px 0 0 var(--color-primary);
    }
  }
}

/* 侧边栏底部用户区 */
.sidebar-user {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-top: 1px solid var(--el-border-color-lighter);
  cursor: pointer;
  transition: background 0.15s;

  &:hover { background: #f2f3f5; }

  &__avatar {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px; height: 32px;
    border-radius: 50%;
    background: var(--color-primary);
    color: #fff;
    font-size: 14px; font-weight: 600;
    flex-shrink: 0;
  }

  &__info {
    display: flex; flex-direction: column;
    min-width: 0;
  }

  &__name {
    font-size: 13px; font-weight: 500;
    color: var(--el-text-color-primary);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }

  &__role {
    font-size: 11px; color: var(--el-text-color-placeholder);
  }
}

/* ==================== 右侧区域 ==================== */
.app-right {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

/* 窄顶栏：面包屑 */
.topbar {
  height: var(--topbar-height);
  flex-shrink: 0;
  background: #fff;
  border-bottom: 1px solid var(--el-border-color-lighter);
  display: flex;
  align-items: center;
  padding: 0 32px;
  z-index: 5;
}

.topbar-breadcrumb {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1;
}

.breadcrumb-link {
  color: var(--el-text-color-secondary);
  text-decoration: none;
  &:hover { color: var(--color-primary); }
}

.breadcrumb-sep {
  color: var(--el-text-color-placeholder);
  margin: 0 2px;
}

.breadcrumb-current {
  color: var(--el-text-color-primary);
  font-weight: 500;
}

/* ==================== 内容区 ==================== */
.app-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--content-padding-y) var(--content-padding-x);
  // 默认页面有最大宽度并居中
  > * {
    max-width: var(--content-max-width);
    margin: 0 auto;
  }
  // 流程设计器占满整个内容区，不受 max-width 和 padding 限制
  :deep(.flow-designer) {
    max-width: none;
    margin: calc(-1 * var(--content-padding-y)) calc(-1 * var(--content-padding-x));
    width: auto;
    height: calc(100% + 2 * var(--content-padding-y));
  }
}

/* ==================== 用户 Popover ==================== */
.user-popover-mask {
  position: fixed; inset: 0; z-index: 1999;
}

.user-popover {
  position: fixed;
  z-index: 2000;
  background: #fff;
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  padding: 8px;
  min-width: 180px;

  &__head {
    display: flex; align-items: center; gap: 10px;
    padding: 6px 8px 10px;
  }

  &__avatar {
    display: inline-flex;
    align-items: center; justify-content: center;
    width: 36px; height: 36px;
    border-radius: 50%;
    background: var(--color-primary);
    color: #fff;
    font-size: 16px; font-weight: 600;
    flex-shrink: 0;
  }

  &__name {
    font-size: 14px; font-weight: 500;
    color: var(--el-text-color-primary);
  }

  &__org {
    font-size: 12px; color: var(--el-text-color-secondary);
    margin-top: 1px;
  }

  &__divider {
    height: 1px;
    background: var(--el-border-color-lighter);
    margin: 4px 0;
  }

  &__item {
    display: block; width: 100%;
    padding: 8px 12px;
    border: none; background: transparent;
    border-radius: 6px;
    font-size: 13px; color: var(--el-text-color-regular);
    text-align: left; cursor: pointer;
    line-height: 1.4;
    &:hover { background: #f2f3f5; }

    &--danger {
      color: var(--el-color-danger);
      &:hover { background: var(--el-color-danger-light-9); }
    }
  }
}

/* ==================== 弹窗内复用样式 ==================== */
.user-info-panel { /* 容器 */ }

.signature-section {
  &__title { font-size: 14px; font-weight: 600; margin: 0 0 4px; color: var(--el-text-color-primary); }
  &__desc  { font-size: 12px; color: var(--el-text-color-secondary); margin: 0 0 12px; }
}

.signature-preview {
  display: flex; align-items: center; gap: 12px;
  padding: 12px; background: var(--page-bg);
  border-radius: 8px; margin-bottom: 12px;

  &--empty {
    justify-content: center;
    border: 1px dashed var(--el-border-color);
    background: transparent;
  }
}

.signature-img {
  max-width: 200px; max-height: 60px; object-fit: contain;
  background: #fff; border: 1px solid var(--el-border-color-lighter);
  border-radius: 4px; padding: 4px;
}

.signature-status { font-size: 12px; color: var(--el-text-color-secondary); }
</style>
