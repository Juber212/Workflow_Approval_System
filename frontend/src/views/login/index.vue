<template>
  <div class="login-page">
    <div class="login-card">
      <!-- 品牌标识区 -->
      <div class="login-brand">
        <span class="login-logo-icon">流</span>
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

      <!-- 演示账号提示 -->
      <div class="login-demo">
        <b>演示账号</b><br>
        所长：张三 / 123456 → 通用所，可见「个人中心」<br>
        管理员：admin / admin123 → 可见「系统管理」<br>
        普通用户：李四 / 123456
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { useUserStore } from '@/stores/user'

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
})

/** 执行登录 */
async function handleLogin() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  errorMsg.value = ''

  try {
    await userStore.login(form.username, form.password)

    // 记住用户名
    if (form.remember) {
      localStorage.setItem('rememberedUsername', form.username)
    } else {
      localStorage.removeItem('rememberedUsername')
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
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 8px;
  background: var(--color-primary);
  color: #fff;
  font-size: 22px;
  font-weight: 700;
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

/* 演示账号提示 */
.login-demo {
  margin-top: 20px;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  border-radius: 8px;  /* 统一圆角 */
  padding: 12px 14px;
  font-size: 12px;
  line-height: 20px;

  b {
    font-weight: 600;
  }
}
</style>
