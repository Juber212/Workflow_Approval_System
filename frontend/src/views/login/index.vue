<template>
  <div class="login-page">
    <div class="login-card">
      <!-- 品牌标识区 -->
      <div class="login-brand">
        <img src="/favicon.svg?v=7" alt="logo" class="login-logo-icon" />
        <div>
          <h1 class="login-title">企业项目审批系统</h1>
          <p class="login-subtitle">Enterprise Workflow Approval System</p>
        </div>
      </div>

      <!-- 登录表单 -->
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @keyup.enter="handleLogin"
        class="login-form"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            :prefix-icon="User"
            size="large"
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            size="large"
            show-password
          />
        </el-form-item>

        <el-form-item>
          <el-checkbox v-model="form.remember">记住用户名</el-checkbox>
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            class="login-btn"
            @click="handleLogin"
          >
            {{ loading ? '登录中…' : '登 录' }}
          </el-button>
        </el-form-item>
      </el-form>

      <!-- 错误提示 -->
      <el-alert
        v-if="errorMsg"
        :title="errorMsg"
        type="error"
        show-icon
        :closable="false"
        class="login-error"
      />

      <!-- 首次登录强制改密码对话框（不可关闭） -->
      <el-dialog
        v-model="showForcePwdDialog"
        title="首次登录 — 请修改密码"
        width="420px"
        :close-on-click-modal="false"
        :show-close="false"
        :close-on-press-escape="false"
      >
        <p class="force-pwd-tip">为确保账户安全，首次登录请设置新密码（≥8位，必须包含字母和数字）</p>
        <el-form ref="forcePwdFormRef" :model="forcePwdForm" :rules="forcePwdRules" label-width="80px" class="force-pwd-form">
          <el-form-item label="新密码" prop="new_password">
            <el-input v-model="forcePwdForm.new_password" type="password" show-password placeholder="≥8位，含字母和数字" />
          </el-form-item>
          <el-form-item label="确认密码" prop="confirm_password">
            <el-input v-model="forcePwdForm.confirm_password" type="password" show-password placeholder="再次输入新密码" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button type="primary" :loading="changingPwd" @click="handleForceChangePassword" style="width:100%">
            确认修改并进入系统
          </el-button>
        </template>
      </el-dialog>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { changePasswordApi } from '@/api/auth'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const errorMsg = ref('')

/** 登录表单数据 */
const form = reactive({
  username: '',
  password: '',
  remember: false,
})

/** 表单校验规则 */
const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

/** 页面挂载时恢复记住的用户名 */
onMounted(() => {
  const saved = localStorage.getItem('rememberedUsername')
  if (saved) {
    form.username = saved
    form.remember = true
  }
  // 注意：被重置密码的用户被守卫踢回本页时，不自动弹改密窗，
  // 需先输入重置后的密码重新登录，登录成功后（must_change_password=true）再弹改密窗
})

// ========== 首次登录强制改密码 ==========
const showForcePwdDialog = ref(false)
const changingPwd = ref(false)
const forcePwdFormRef = ref<FormInstance>()
const forcePwdForm = reactive({ new_password: '', confirm_password: '' })

const validateForceConfirm = (_rule: any, value: string, callback: (err?: Error) => void) => {
  callback(value !== forcePwdForm.new_password ? new Error('两次输入的密码不一致') : undefined)
}

const validateForceStrength = (_rule: any, value: string, callback: (err?: Error) => void) => {
  if (value.length < 8) { callback(new Error('密码长度不能少于8位')); return }
  if (!/[a-zA-Z]/.test(value)) { callback(new Error('密码必须包含字母')); return }
  if (!/\d/.test(value)) { callback(new Error('密码必须包含数字')); return }
  if (form.username && value.toLowerCase() === form.username.toLowerCase()) {
    callback(new Error('密码不能与用户名相同')); return
  }
  callback()
}

const forcePwdRules: FormRules = {
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { validator: validateForceStrength, trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateForceConfirm, trigger: 'blur' },
  ],
}

/** 首次登录强制改密码 */
async function handleForceChangePassword() {
  // 防并发双提交：按钮 loading 的 DOM 更新有延迟，双击会在第二次请求时因
  // must_change_password 已置 False（缺少旧密码）触发 400，弹「修改失败」
  if (changingPwd.value) return
  changingPwd.value = true
  const valid = await forcePwdFormRef.value?.validate().catch(() => false)
  if (!valid) {
    changingPwd.value = false
    return
  }
  try {
    const data = await changePasswordApi({
      // 强制改密场景（首次登录/管理员重置后）无需旧密码：
      // 后端在 must_change_password=True 时允许省略，这里不依赖登录表单的密码值
      new_password: forcePwdForm.new_password,
    })
    ElMessage.success('密码修改成功')
    showForcePwdDialog.value = false
    // 更新 store 中的标记
    if (userStore.userInfo) {
      userStore.userInfo.must_change_password = false
    }
    // 改密成功后端重新签发 token：替换本地会话，避免被新密码版本号吊销
    if (data.token) {
      userStore.setToken(data.token)
    }
    // 跳转
    const redirect = (route.query.redirect as string) || '/dashboard'
    router.push(redirect)
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '修改失败')
  } finally {
    changingPwd.value = false
  }
}

/** 执行登录 */
async function handleLogin() {
  // 防并发双提交：双击会发两次登录请求，重复占用登录限流配额（20 次/分钟/IP）
  if (loading.value) return
  loading.value = true
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) {
    loading.value = false
    return
  }
  errorMsg.value = ''

  try {
    const data = await userStore.login(form.username, form.password)

    // 记住用户名
    if (form.remember) {
      localStorage.setItem('rememberedUsername', form.username)
    } else {
      localStorage.removeItem('rememberedUsername')
    }

    // 首次登录 → 弹出强制改密码对话框
    if (data.must_change_password) {
      forcePwdForm.new_password = ''
      forcePwdForm.confirm_password = ''
      showForcePwdDialog.value = true
      return
    }

    // 跳转到重定向页面或默认 Dashboard
    const redirect = (route.query.redirect as string) || '/dashboard'
    router.push(redirect)
  } catch (err: any) {
    errorMsg.value = err?.message || '登录失败，请检查用户名和密码'
  } finally {
    loading.value = false
  }
}
</script>

<style lang="scss" scoped>
.login-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: #f5f6f8;  /* 与主应用背景统一 */
}

.login-card {
  width: 420px;
  background: #fff;
  border-radius: 12px;  /* 更大的圆角，更现代 */
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);  /* 更克制的阴影 */
  padding: 40px 36px;
}

/* 品牌标识 */
.login-brand {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 8px;
}

.login-logo-icon {
  display: block;
  width: 48px;
  height: 48px;
  flex-shrink: 0;
}

.login-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0;
  line-height: 1.3;
}

.login-subtitle {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin: 2px 0 0;
  letter-spacing: 0.5px;
}

/* 表单 */
.login-form {
  margin-top: 24px;
}

.login-btn {
  width: 100%;
  letter-spacing: 4px;
  font-size: 15px;
}

.login-error {
  margin-top: 4px;
}

/* 强制改密码弹窗 */
.force-pwd-tip {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 16px;
  line-height: 1.6;
}
.force-pwd-form {
  :deep(.el-form-item) {
    margin-bottom: 16px;
  }
}
</style>
