<template>
  <!-- 侧边栏 + 内容区布局 —— 支持折叠为图标列，设计器全屏 -->
  <div class="app-shell" :class="{ 'app-shell--designer': isDesigner }">
    <!-- ==================== 侧边栏 ==================== -->
    <SidebarNav
      v-show="!isDesigner"
      @open-user-info="showUserInfoDialog = true"
      @open-password="showPasswordDialog = true"
    />

    <!-- ==================== 右侧区域 ==================== -->
    <div class="app-right">
      <main class="app-content">
        <!-- 面包屑导航栏 -->
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
          <div class="breadcrumb-bar__right">
            <NotificationBell />
          </div>
        </div>
        <router-view />
      </main>
    </div>

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
            <img :src="signatureBlobUrl" alt="签名预览" class="signature-img" />
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
    <ChangePasswordDialog v-model="showPasswordDialog" />
  </div>
</template>

<script setup lang="ts">
/** 应用布局 —— 侧边栏 + 内容区（飞书风格） */
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { useNotificationStore } from '@/stores/notification'
import NotificationBell from '@/components/NotificationBell.vue'
import SidebarNav from '@/layouts/components/SidebarNav.vue'
import ChangePasswordDialog from '@/layouts/components/ChangePasswordDialog.vue'
import { getMeApi, uploadSignatureApi, toUserInfo } from '@/api/auth'
import { getTasks } from '@/api/task'
import { getChecks } from '@/api/check'
import { getApprovals } from '@/api/approval'
import { useBreadcrumb } from '@/composables/useBreadcrumb'

const route = useRoute()
const userStore = useUserStore()
const notifyStore = useNotificationStore()

// ==================== 面包屑 ====================
const { items: breadcrumbItems } = useBreadcrumb()
const isDesigner = computed(() => route.path.startsWith('/flows/designer/'))

const showBreadcrumb = computed(() => {
  if (route.path === '/dashboard') return false
  if (isDesigner.value) return false
  return true
})

// ==================== 角色标签 ====================
function roleTagLabel(role: string): string {
  const m: Record<string, string> = { system_admin: '系统管理员', manager: '所长', user: '普通用户' }
  return m[role] || role
}

// ==================== 通知计数 ====================
const isAdmin = computed(() => userStore.userInfo?.roles.includes('system_admin') ?? false)

async function refreshNotifyCounts() {
  if (isAdmin.value) return
  try {
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
    notifyStore.setTypedCounts(
      projectTasks.total + checks.total + projectApprovals.total,
      proposalTasks.total + proposalApprovals.total,
    )
  } catch (e) { console.error('通知数量刷新失败:', e) }
}

onMounted(refreshNotifyCounts)
watch(() => route.path, () => { refreshNotifyCounts() })

// ==================== 个人信息弹窗 ====================
const showUserInfoDialog = ref(false)
const showPasswordDialog = ref(false)
const userInfoDetail = ref<{
  user_id: number; username: string; real_name: string
  email: string | null; phone: string | null; roles: string[]
  organization_id: number | null; organization_name: string | null
  has_signature: boolean
} | null>(null)
const uploadingSignature = ref(false)
const signatureBlobUrl = ref('')

async function loadSignatureBlob() {
  if (signatureBlobUrl.value) {
    URL.revokeObjectURL(signatureBlobUrl.value)
    signatureBlobUrl.value = ''
  }
  const uid = userInfoDetail.value?.user_id
  if (!uid || !userInfoDetail.value?.has_signature) return
  try {
    const token = localStorage.getItem('token')
    const resp = await fetch(`/api/v1/auth/users/${uid}/signature-image`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!resp.ok) return
    const blob = await resp.blob()
    signatureBlobUrl.value = URL.createObjectURL(blob)
  } catch { /* 静默失败 */ }
}

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

watch(showUserInfoDialog, async (val) => {
  if (val) {
    await refreshUserInfoDetail()
    await loadSignatureBlob()
  } else {
    if (signatureBlobUrl.value) {
      URL.revokeObjectURL(signatureBlobUrl.value)
      signatureBlobUrl.value = ''
    }
  }
})

/** Canvas 压缩签名图片 */
function compressSignatureImage(file: File): Promise<File> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      URL.revokeObjectURL(img.src)
      const maxW = 400, maxH = 120
      let w = img.width, h = img.height
      const needRotate = h > w
      if (needRotate) { ;[w, h] = [h, w] }
      const ratio = Math.min(maxW / w, maxH / h, 1.0)
      w = Math.round(w * ratio)
      h = Math.round(h * ratio)
      const canvas = document.createElement('canvas')
      canvas.width = w; canvas.height = h
      const ctx = canvas.getContext('2d')!
      if (needRotate) {
        const tmp = document.createElement('canvas')
        tmp.width = img.height; tmp.height = img.width
        const tctx = tmp.getContext('2d')!
        tctx.translate(img.height, 0)
        tctx.rotate(Math.PI / 2)
        tctx.drawImage(img, 0, 0)
        ctx.drawImage(tmp, 0, 0, w, h)
      } else {
        ctx.drawImage(img, 0, 0, w, h)
      }
      canvas.toBlob((blob) => {
        if (!blob) return reject(new Error('压缩失败'))
        resolve(new File([blob], file.name.replace(/\.[^.]+$/, '.png'), { type: 'image/png' }))
      }, 'image/png')
    }
    img.onerror = () => { URL.revokeObjectURL(img.src); reject(new Error('图片加载失败')) }
    img.src = URL.createObjectURL(file)
  })
}

async function handleSignatureUpload(file: File): Promise<boolean> {
  if (file.size > 500 * 1024) { ElMessage.error('签名图片不能超过 500KB'); return false }
  const allowed = ['image/png', 'image/jpeg', 'image/gif', 'image/webp']
  if (!allowed.includes(file.type)) { ElMessage.error('仅支持 PNG/JPG/GIF/WebP 格式'); return false }
  uploadingSignature.value = true
  try {
    const compressed = await compressSignatureImage(file)
    const result = await uploadSignatureApi(compressed)
    if (result.signature_url) { userInfoDetail.value!.has_signature = true }
    ElMessage.success('签名图片已上传')
    await refreshUserInfoDetail()
    await loadSignatureBlob()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '上传失败')
  } finally { uploadingSignature.value = false }
  return false
}
</script>

<style lang="scss" scoped>
/* ==================== 整体外壳 ==================== */
.app-shell {
  display: flex; height: 100vh; overflow: hidden;
  background: var(--page-bg);

  &--designer {
    .app-content {
      padding: 0;
      > * { max-width: none; margin: 0; }
      :deep(.flow-designer) { margin: 0; width: 100%; height: 100%; }
    }
  }
}

/* ==================== 右侧区域 ==================== */
.app-right {
  flex: 1; display: flex; flex-direction: column;
  min-width: 0; overflow: hidden;
}

/* ==================== 内容区 ==================== */
.app-content {
  flex: 1; overflow-y: auto;
  padding: var(--content-padding-y) var(--content-padding-x);
  > * { max-width: var(--content-max-width); margin: 0 auto; }
  :deep(.flow-designer) {
    max-width: none;
    margin: calc(-1 * var(--content-padding-y)) calc(-1 * var(--content-padding-x));
    width: auto; height: calc(100% + 2 * var(--content-padding-y));
  }
}

/* ==================== 面包屑导航栏 ==================== */
.breadcrumb-bar {
  max-width: var(--content-max-width);
  margin: 0 auto 12px; padding: 0;
  display: flex; justify-content: space-between; align-items: center;
  :deep(.el-breadcrumb) { font-size: 13px; }
  :deep(.el-breadcrumb__item) {
    .el-breadcrumb__inner {
      color: var(--el-text-color-secondary); font-weight: 400;
      transition: color 0.15s;
      &:hover { color: var(--color-primary); }
    }
  }
  :deep(.el-breadcrumb__item:last-child) {
    .el-breadcrumb__inner {
      color: var(--el-text-color-primary); font-weight: 500;
      cursor: default;
      &:hover { color: var(--el-text-color-primary); }
    }
  }
  :deep(.el-breadcrumb__separator) {
    color: var(--el-text-color-placeholder); font-weight: 400; margin: 0 6px;
  }
}

.breadcrumb-bar__right {
  display: flex; align-items: center; gap: 8px;
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
