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

        <!-- 主导航 —— 纯 router-link，三个独立模块无层级 -->
        <nav class="app-nav">
          <router-link to="/dashboard" class="app-nav__item" :class="{ 'is-active': isActive('/dashboard') }">首页看板</router-link>
          <router-link to="/flows"     class="app-nav__item" :class="{ 'is-active': isActive('/flows') }">流程管理</router-link>
          <router-link v-if="!isAdmin" to="/profile" class="app-nav__item" :class="{ 'is-active': isActive('/profile') }">个人中心</router-link>
          <router-link v-if="isAdmin"  to="/admin/users" class="app-nav__item" :class="{ 'is-active': isActive('/admin') }">系统管理</router-link>
        </nav>
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
              <!-- 个人信息（含签名上传）（PRD §10.1） -->
              <el-dropdown-item @click="showUserInfoDialog = true">个人信息</el-dropdown-item>
              <!-- 修改密码（PRD §10.1） -->
              <el-dropdown-item @click="showPasswordDialog = true">修改密码</el-dropdown-item>
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

    <!-- ==================== 个人信息弹窗（PRD §10.1） ==================== -->
    <el-dialog
      v-model="showUserInfoDialog"
      title="个人信息"
      width="500px"
      :close-on-click-modal="false"
    >
      <div class="user-info-panel" v-if="userStore.userInfo">
        <!-- 基本信息系统只读展示 -->
        <el-descriptions :column="2" border size="default">
          <el-descriptions-item label="用户名">{{ userStore.userInfo.username }}</el-descriptions-item>
          <el-descriptions-item label="姓名">{{ userStore.userInfo.real_name }}</el-descriptions-item>
          <el-descriptions-item label="所属组织">{{ userStore.userInfo.organization_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="角色">
            <el-tag v-for="r in userStore.userInfo.roles" :key="r" size="small" style="margin-right:4px">
              {{ roleLabel(r) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="邮箱">{{ userStore.userInfo.email || '-' }}</el-descriptions-item>
          <el-descriptions-item label="手机号">{{ userStore.userInfo.phone || '-' }}</el-descriptions-item>
        </el-descriptions>

        <!-- 签名图片上传（PRD：用户上传签名后审批自动签名） -->
        <el-divider />
        <div class="signature-section">
          <h4 class="signature-section__title">个人签名</h4>
          <p class="signature-section__desc">
            上传透明底 PNG 签名图片（推荐 200×60px，≤500KB），审批通过时自动插入 PDF。
          </p>

          <!-- 签名预览 -->
          <div class="signature-preview" v-if="userInfoDetail?.has_signature">
            <img :src="signaturePreviewUrl" alt="签名预览" class="signature-img" />
            <span class="signature-status">已上传</span>
          </div>
          <div class="signature-preview signature-preview--empty" v-else>
            <span class="signature-status">未上传签名</span>
          </div>

          <!-- 上传按钮 -->
          <el-upload
            :show-file-list="false"
            :before-upload="handleSignatureUpload"
            accept="image/png,image/jpeg,image/gif,image/webp"
          >
            <el-button type="primary" size="small" :loading="uploadingSignature">
              {{ userInfoDetail?.has_signature ? '更换签名' : '上传签名' }}
            </el-button>
          </el-upload>
        </div>
      </div>
    </el-dialog>

    <!-- ==================== 修改密码弹窗（PRD §10.1） ==================== -->
    <el-dialog
      v-model="showPasswordDialog"
      title="修改密码"
      width="420px"
      :close-on-click-modal="false"
    >
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
  </el-container>
</template>

<script setup lang="ts">
/** 应用布局 —— 顶部导航 + 用户下拉（含个人信息/修改密码弹窗） */
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { getMeApi, changePasswordApi, uploadSignatureApi, toUserInfo } from '@/api/auth'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

/** 是否为系统管理员（不参与业务流程） */
const isAdmin = computed(() => userStore.userInfo?.roles.includes('system_admin') ?? false)

/** 判断导航项是否激活 */
function isActive(base: string): boolean {
  const p = route.path
  if (base === '/admin') return p.startsWith('/admin')
  return p === base || p.startsWith(base + '/')
}

/** 头像显示的文字（用户姓名首字） */
const avatarInitial = computed(() => {
  const name = userStore.userInfo?.real_name || ''
  return name.charAt(0) || '?'
})

async function handleLogout() {
  await userStore.logout()
  router.push('/login')
}

// ==================== 个人信息弹窗 ====================
const showUserInfoDialog = ref(false)
const userInfoDetail = ref<{
  user_id: number
  username: string
  real_name: string
  email: string | null
  phone: string | null
  roles: string[]
  organization_id: number | null
  organization_name: string | null
  has_signature: boolean
} | null>(null)
const uploadingSignature = ref(false)

/** 签名预览地址 */
const signaturePreviewUrl = computed(() => {
  if (!userInfoDetail.value?.user_id) return ''
  // 后端存储路径为 storage/signatures/{user_id}_{hash}.png
  // 需要后端提供静态文件服务，此处使用通用路径（带时间戳防缓存）
  return `/api/v1/storage/signatures/${userInfoDetail.value.user_id}.png?t=${Date.now()}`
})

/** 角色中文映射 */
function roleLabel(role: string): string {
  const map: Record<string, string> = {
    system_admin: '系统管理员',
    manager: '所长',
    user: '普通用户',
  }
  return map[role] || role
}

/** 打开个人信息弹窗时刷新用户详情 */
async function refreshUserInfoDetail() {
  try {
    const data = await getMeApi()
    userInfoDetail.value = data
    // 同步到 store
    userStore.userInfo = toUserInfo(data)
  } catch {
    // 使用 store 中已有数据
    if (userStore.userInfo) {
      userInfoDetail.value = {
        user_id: userStore.userInfo.id,
        username: userStore.userInfo.username,
        real_name: userStore.userInfo.real_name,
        email: userStore.userInfo.email,
        phone: userStore.userInfo.phone,
        roles: userStore.userInfo.roles,
        organization_id: userStore.userInfo.organization_id,
        organization_name: userStore.userInfo.organization_name,
        has_signature: false,
      }
    }
  }
}

// 监听弹窗打开，刷新数据
import { watch } from 'vue'
watch(showUserInfoDialog, async (val) => {
  if (val) await refreshUserInfoDetail()
})

/** 签名上传前校验 */
async function handleSignatureUpload(file: File): Promise<boolean> {
  // 校验大小
  if (file.size > 500 * 1024) {
    ElMessage.error('签名图片不能超过 500KB')
    return false
  }
  // 校验类型
  const allowed = ['image/png', 'image/jpeg', 'image/gif', 'image/webp']
  if (!allowed.includes(file.type)) {
    ElMessage.error('仅支持 PNG/JPG/GIF/WebP 格式')
    return false
  }

  uploadingSignature.value = true
  try {
    await uploadSignatureApi(file)
    ElMessage.success('签名图片已上传')
    // 刷新信息以更新 has_signature 状态
    await refreshUserInfoDetail()
  } catch (err: any) {
    const msg = err?.response?.data?.message || '上传失败'
    ElMessage.error(msg)
  } finally {
    uploadingSignature.value = false
  }
  // 阻止 el-upload 的默认上传行为
  return false
}

// ==================== 修改密码弹窗 ====================
const showPasswordDialog = ref(false)
const changingPwd = ref(false)
const pwdFormRef = ref<FormInstance>()

const pwdForm = ref({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

/** 自定义确认密码校验 */
const validateConfirmPassword = (_rule: any, value: string, callback: (err?: Error) => void) => {
  if (value !== pwdForm.value.new_password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
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

/** 提交修改密码 */
async function handleChangePassword() {
  const valid = await pwdFormRef.value?.validate().catch(() => false)
  if (!valid) return

  changingPwd.value = true
  try {
    await changePasswordApi({
      old_password: pwdForm.value.old_password,
      new_password: pwdForm.value.new_password,
    })
    ElMessage.success('密码修改成功，请重新登录')
    showPasswordDialog.value = false
    // 清空表单
    pwdForm.value = { old_password: '', new_password: '', confirm_password: '' }
    // 退出登录
    await userStore.logout()
    router.push('/login')
  } catch (err: any) {
    const msg = err?.response?.data?.message || '修改失败'
    ElMessage.error(msg)
  } finally {
    changingPwd.value = false
  }
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

/* 导航栏 —— 纯 router-link，扁平独立 */
.app-nav {
  display: flex; align-items: center; height: 100%; gap: 4px;

  &__item {
    display: inline-flex; align-items: center; height: 56px;
    padding: 0 18px; font-size: 14px; font-weight: 500;
    color: var(--el-text-color-regular); text-decoration: none;
    border-bottom: 2px solid transparent;
    transition: color 0.15s, border-color 0.15s;
    white-space: nowrap; flex-shrink: 0;

    &:hover { color: var(--el-color-primary); border-bottom-color: var(--el-color-primary-light-5); }
    &.is-active { color: var(--el-color-primary); font-weight: 600; border-bottom-color: var(--el-color-primary); }
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

/* ==================== 个人信息面板 ==================== */
.user-info-panel {
  // 内容样式
}

.signature-section {
  &__title {
    font-size: 14px;
    font-weight: 600;
    margin: 0 0 4px;
    color: var(--el-text-color-primary);
  }

  &__desc {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    margin: 0 0 12px;
  }
}

.signature-preview {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--el-bg-color-page);
  border-radius: 8px;
  margin-bottom: 12px;

  &--empty {
    justify-content: center;
    border: 1px dashed var(--el-border-color);
    background: transparent;
  }
}

.signature-img {
  max-width: 200px;
  max-height: 60px;
  object-fit: contain;
  background: #fff;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 4px;
  padding: 4px;
}

.signature-status {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
