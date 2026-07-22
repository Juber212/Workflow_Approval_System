<template>
  <!-- 侧边栏 + 内容区布局 —— 支持折叠为图标列，设计器全屏 -->
  <div class="app-shell" :class="{ 'app-shell--designer': isDesigner }">
    <!-- ==================== 侧边栏 ==================== -->
    <aside v-show="!isDesigner" class="sidebar" :class="{ 'is-collapsed': isCollapsed }">
      <!-- 品牌 Logo 行（折叠态：logo 可点击展开） -->
      <div class="sidebar-brand">
        <!-- 折叠态：logo 图标切换为展开按钮，hover 时显示折叠图标 -->
        <el-tooltip v-if="isCollapsed" content="展开侧边栏" placement="right">
          <span
            class="sidebar-brand__icon sidebar-brand__icon--toggle"
            @click="isCollapsed = false"
            @mouseenter="isBrandHovered = true"
            @mouseleave="isBrandHovered = false"
          >
            <svg v-if="isBrandHovered" width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round">
              <rect x="1.5" y="3.5" width="17" height="13" rx="3" />
              <line x1="6" y1="3.5" x2="6" y2="16.5" />
            </svg>
            <img v-else src="/favicon.svg?v=7" alt="logo" class="sidebar-brand__logo" />
          </span>
        </el-tooltip>
        <!-- 展开态：logo 正常链接 -->
        <template v-else>
          <router-link to="/dashboard" class="sidebar-brand__icon sidebar-brand__icon--link">
            <img src="/favicon.svg?v=7" alt="logo" class="sidebar-brand__logo" />
          </router-link>
          <div class="sidebar-brand__text">
            <router-link to="/dashboard" class="sidebar-brand__title">项目审批系统</router-link>
            <span class="sidebar-brand__sub">Workflow Approval</span>
          </div>
          <!-- 折叠按钮（展开态显示在 logo 行右侧） -->
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
        <el-tooltip
          v-for="item in menuItems" :key="item.path"
          :content="item.label" placement="right" :disabled="!isCollapsed"
        >
          <router-link
            :to="item.path"
            class="sidebar-nav__item"
            :class="{ 'is-active': isMenuActive(item.path) }"
          >
            <el-icon :size="20"><component :is="item.icon" /></el-icon>
            <span class="sidebar-nav__label">{{ item.label }}</span>
            <!-- 个人中心通知红点 -->
            <!-- 折叠态：无数字小红点（绝对定位到图标右上角） -->
            <span v-if="item.path === '/profile' && notifyStore.hasPending && isCollapsed" class="sidebar-nav__dot" />
            <!-- 展开态：带数字红色圆形徽章 -->
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
    </aside>

    <!-- ==================== 右侧区域 ==================== -->
    <div class="app-right">
      <main class="app-content">
        <!-- 面包屑导航栏（设计器 & 有返回按钮的页面隐藏） -->
        <div v-if="showBreadcrumb" class="breadcrumb-bar">
          <el-breadcrumb separator="›">
            <el-breadcrumb-item
              v-for="(item, idx) in breadcrumbItems"
              :key="idx"
              :to="idx < breadcrumbItems.length - 1 && item.to ? item.to : undefined"
            >
              {{ item.label }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
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
/** 应用布局 —— 侧边栏 + 内容区（飞书风格） */
import { ref, computed, watch, onMounted, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { Monitor, Document, Setting, User, Files } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { useNotificationStore } from '@/stores/notification'
import { getMeApi, changePasswordApi, uploadSignatureApi, toUserInfo } from '@/api/auth'
import { getTasks } from '@/api/task'
import { getChecks } from '@/api/check'
import { getApprovals } from '@/api/approval'
import { useBreadcrumb } from '@/composables/useBreadcrumb'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const notifyStore = useNotificationStore()

// ==================== 侧边栏状态 ====================
/** 侧边栏是否折叠为图标列 */
const isCollapsed = ref(false)
/** 折叠态下鼠标是否悬停在 logo 上（切换显示折叠图标） */
const isBrandHovered = ref(false)
/** 是否在项目设计器页面（隐藏侧边栏，占满全屏） */
const isDesigner = computed(() => route.path.startsWith('/flows/designer/'))

// ==================== 面包屑 ====================
const { items: breadcrumbItems } = useBreadcrumb()

/** 面包屑可见条件：首页/设计器不显示 */
const showBreadcrumb = computed(() => {
  if (route.path === '/dashboard') return false
  if (isDesigner.value) return false
  return true
})

/** 折叠侧边栏，同时重置 hover 状态避免图标残留 */
function handleCollapse() {
  isCollapsed.value = true
  isBrandHovered.value = false
}

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

/** 菜单项图标映射（Element Plus 线框风格） */
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

/** 判断菜单项是否激活 */
function isMenuActive(base: string): boolean {
  const p = route.path
  if (base === '/admin/users') return p.startsWith('/admin')
  if (base === '/profile') return p.startsWith('/profile')
  if (base === '/proposals') return p.startsWith('/proposals')
  return p === base || p.startsWith(base + '/')
}

// ==================== 通知计数 ====================

/** 页面加载时主动拉取通知计数（非管理员），确保侧边栏徽章始终显示 */
async function refreshNotifyCounts() {
  if (isAdmin.value) return // 管理员无个人中心，无需拉取
  try {
    // 并行拉取：合计用于侧边栏徽章，分类型用于项目/方案 radio-button 徽章
    const [tasks, checks, approvals, projectTasks, proposalTasks, projectApprovals, proposalApprovals] = await Promise.all([
      getTasks({ page_size: 1 }),
      getChecks({ page_size: 1 }),
      getApprovals({ page_size: 1 }),
      getTasks({ page_size: 1, type: 'project' }),
      getTasks({ page_size: 1, type: 'proposal' }),
      getApprovals({ page_size: 1, type: 'project' }),
      getApprovals({ page_size: 1, type: 'proposal' }),
    ])
    notifyStore.setCounts(tasks.total, checks.total, approvals.total)
    // 方案无校验步骤，项目待处理 = 项目任务 + 校验 + 项目审批
    notifyStore.setTypedCounts(
      projectTasks.total + checks.total + projectApprovals.total,
      proposalTasks.total + proposalApprovals.total,
    )
  } catch { /* 失败不影响页面使用 */ }
}

onMounted(refreshNotifyCounts)

/** 路由变化时自动刷新徽章数字（用户操作后跳转时及时更新） */
watch(() => route.path, () => {
  refreshNotifyCounts()
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
  notifyStore.clearAll() // 清空通知计数
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

/** 签名预览 URL：通过后端 API 获取（自动查找用户真实签名文件路径） */
const signaturePreviewUrl = computed(() => {
  if (!userInfoDetail.value?.user_id) return ''
  return `/api/v1/auth/users/${userInfoDetail.value.user_id}/signature-image?t=${Date.now()}`
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

/** Canvas 压缩签名图片到 400×120 范围内（高清存储，CSS 缩小后预览清晰），返回压缩后的 File
 *
 * 关键改进：
 * - 不涂白底（canvas 默认透明），保留签名透明背景
 * - 检测竖图（高度 > 宽度）自动旋转 90° 转为横条
 */
function compressSignatureImage(file: File): Promise<File> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      const maxW = 400, maxH = 120
      let w = img.width, h = img.height

      // 竖图检测：高度 > 宽度 → 旋转 90° 转为横条（EXIF 旋转信息在 Canvas 中丢失后的补偿）
      const needRotate = h > w
      if (needRotate) {
        ;[w, h] = [h, w]  // 交换宽高
      }

      const ratio = Math.min(maxW / w, maxH / h, 1.0)  // 只缩小不放大
      w = Math.round(w * ratio)
      h = Math.round(h * ratio)

      const canvas = document.createElement('canvas')
      canvas.width = w; canvas.height = h
      const ctx = canvas.getContext('2d')!

      // 透明背景（canvas 默认透明，不 fillRect 白底）
      if (needRotate) {
        // 两步法：先旋转绘制到临时 canvas，再缩放到目标 canvas（避免坐标变换出错）
        const tmp = document.createElement('canvas')
        tmp.width = img.height; tmp.height = img.width  // 交换宽高作为旋转后尺寸
        const tctx = tmp.getContext('2d')!
        tctx.translate(img.height, 0)
        tctx.rotate(Math.PI / 2)
        tctx.drawImage(img, 0, 0)  // 自然尺寸绘制，填满旋转后的临时 canvas
        // 缩放至目标尺寸（维持比例，无白底）
        ctx.drawImage(tmp, 0, 0, w, h)
      } else {
        ctx.drawImage(img, 0, 0, w, h)
      }

      canvas.toBlob((blob) => {
        if (!blob) return reject(new Error('压缩失败'))
        resolve(new File([blob], file.name.replace(/\.[^.]+$/, '.png'), { type: 'image/png' }))
      }, 'image/png')
    }
    img.onerror = () => reject(new Error('图片加载失败'))
    img.src = URL.createObjectURL(file)
  })
}

async function handleSignatureUpload(file: File): Promise<boolean> {
  if (file.size > 500 * 1024) { ElMessage.error('签名图片不能超过 500KB'); return false }
  const allowed = ['image/png', 'image/jpeg', 'image/gif', 'image/webp']
  if (!allowed.includes(file.type)) { ElMessage.error('仅支持 PNG/JPG/GIF/WebP 格式'); return false }
  uploadingSignature.value = true
  try {
    // 前端先压缩到 200×60 范围，统一转为 PNG
    const compressed = await compressSignatureImage(file)
    const result = await uploadSignatureApi(compressed)
    // 使用后端返回的签名 URL 更新预览
    if (result.signature_url) {
      userInfoDetail.value!.has_signature = true
    }
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

  // 设计器模式：侧边栏隐藏，内容区占满全屏
  &--designer {
    .app-content {
      padding: 0;
      > * { max-width: none; margin: 0; }
      :deep(.flow-designer) {
        margin: 0; width: 100%; height: 100%;
      }
    }
  }
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
  transition: width 0.2s ease;
  position: relative;

  // 折叠状态：窄图标列
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

/* 折叠切换按钮（展开态，放在品牌行右侧） */
.sidebar-toggle {
  display: flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; padding: 0; margin-left: auto; flex-shrink: 0;
  border: none; background: transparent; border-radius: 6px;
  cursor: pointer; color: var(--el-text-color-secondary);
  transition: background 0.15s, color 0.15s;
  &:hover { background: #f2f3f5; color: var(--el-text-color-primary); }
}

/* 侧边栏品牌标识 */
.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 16px 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  margin-bottom: 8px;
  transition: padding 0.2s ease;

  &__icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 36px; height: 36px;
    border-radius: 8px;
    flex-shrink: 0;

    // logo 链接重置
    &--link { text-decoration: none; }

    // 折叠态：logo 可点击展开
    &--toggle {
      cursor: pointer; transition: background 0.15s;
      &:hover { background: var(--el-fill-color); }
    }
  }

  &__logo {
    display: block;
    width: 32px;
    height: 32px;
  }

  &__text {
    display: flex; flex-direction: column;
    min-width: 0;
  }

  &__title {
    font-size: 15px; font-weight: 600;
    color: var(--el-text-color-primary);
    text-decoration: none;
    white-space: nowrap;
    &:hover { color: var(--color-primary); }
  }

  &__sub {
    font-size: 11px; color: var(--el-text-color-placeholder);
    margin-top: 1px; letter-spacing: 0.3px;
  }
}

/* 侧边栏导航菜单 */
.sidebar-nav {
  flex: 1;
  padding: 4px 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  transition: padding 0.2s ease;

  &__item {
    position: relative; /* 为小圆点提供定位锚 */
    display: flex;
    align-items: center;
    gap: 10px;
    height: 40px;
    padding: 0 12px;
    border-radius: 6px;
    font-size: 14px; font-weight: 500;
    color: var(--el-text-color-regular);
    text-decoration: none;
    white-space: nowrap;
    transition: all 0.15s;

    &:hover { background: #f2f3f5; }

    &.is-active {
      color: var(--color-primary);
      background: #e8f0fe;
      box-shadow: inset 3px 0 0 var(--color-primary);
    }
  }

  &__label { transition: opacity 0.15s; }

  /** 个人中心红色圆形数字徽章（展开态） */
  &__badge {
    width: 20px; height: 20px;
    border-radius: 50%;
    background: var(--el-color-danger);
    color: #fff;
    font-size: 11px; font-weight: 700;
    display: inline-flex; align-items: center; justify-content: center;
    flex-shrink: 0;
    line-height: 1;
    margin-left: auto;
  }

  /** 无数字小红点（折叠态，绝对定位到图标右上角） */
  &__dot {
    position: absolute;
    top: 6px;
    right: 6px;
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--el-color-danger);
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
  transition: all 0.2s;

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

/* ==================== 内容区 ==================== */
.app-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--content-padding-y) var(--content-padding-x);
  > * {
    max-width: var(--content-max-width);
    margin: 0 auto;
  }
  // 项目设计器占满整个内容区
  :deep(.flow-designer) {
    max-width: none;
    margin: calc(-1 * var(--content-padding-y)) calc(-1 * var(--content-padding-x));
    width: auto;
    height: calc(100% + 2 * var(--content-padding-y));
  }
}

/* ==================== 面包屑导航栏 ==================== */
.breadcrumb-bar {
  max-width: var(--content-max-width);
  margin: 0 auto 12px;
  padding: 0;
  :deep(.el-breadcrumb) {
    font-size: 13px;
  }
  :deep(.el-breadcrumb__item) {
    // 非最后一项（可点击跳转）
    .el-breadcrumb__inner {
      color: var(--el-text-color-secondary);
      font-weight: 400;
      transition: color 0.15s;
      &:hover { color: var(--color-primary); }
    }
  }
  :deep(.el-breadcrumb__item:last-child) {
    .el-breadcrumb__inner {
      color: var(--el-text-color-primary);
      font-weight: 500;
      cursor: default;
      &:hover { color: var(--el-text-color-primary); }
    }
  }
  :deep(.el-breadcrumb__separator) {
    color: var(--el-text-color-placeholder);
    font-weight: 400;
    margin: 0 6px;
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
