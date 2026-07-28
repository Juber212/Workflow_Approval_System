<template>
  <!-- 修改密码弹窗 -->
  <el-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    title="修改密码"
    width="420px"
    :close-on-click-modal="false"
  >
    <el-form ref="pwdFormRef" :model="pwdForm" :rules="pwdRules" label-width="80px">
      <el-form-item label="原密码" prop="old_password">
        <el-input v-model="pwdForm.old_password" type="password" show-password placeholder="请输入原密码" />
      </el-form-item>
      <el-form-item label="新密码" prop="new_password">
        <el-input v-model="pwdForm.new_password" type="password" show-password placeholder="≥8位，必须包含字母和数字" />
      </el-form-item>
      <el-form-item label="确认密码" prop="confirm_password">
        <el-input v-model="pwdForm.confirm_password" type="password" show-password placeholder="再次输入新密码" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="changingPwd" @click="handleChangePassword">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/** 修改密码弹窗 —— 独立组件，通过 v-model 控制显隐 */
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { changePasswordApi } from '@/api/auth'
import { useUserStore } from '@/stores/user'

defineProps<{ modelValue: boolean }>()
defineEmits<{ 'update:modelValue': [value: boolean] }>()

const router = useRouter()
const userStore = useUserStore()

const changingPwd = ref(false)
const pwdFormRef = ref<FormInstance>()
const pwdForm = reactive({ old_password: '', new_password: '', confirm_password: '' })

const validateConfirmPassword = (_rule: any, value: string, callback: (err?: Error) => void) => {
  callback(value !== pwdForm.new_password ? new Error('两次输入的密码不一致') : undefined)
}

/** 校验新密码强度：≥8位 + 必须包含字母和数字 + 不能与用户名相同 */
const validatePasswordStrength = (_rule: any, value: string, callback: (err?: Error) => void) => {
  if (value.length < 8) { callback(new Error('密码长度不能少于8位')); return }
  if (!/[a-zA-Z]/.test(value)) { callback(new Error('密码必须包含字母')); return }
  if (!/\d/.test(value)) { callback(new Error('密码必须包含数字')); return }
  const username = userStore.userInfo?.username
  if (username && value.toLowerCase() === username.toLowerCase()) {
    callback(new Error('密码不能与用户名相同')); return
  }
  callback()
}

const pwdRules: FormRules = {
  old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, max: 128, message: '密码长度 8-128 位', trigger: 'blur' },
    { validator: validatePasswordStrength, trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
}

/** 修改密码 —— 成功后退出登录 */
async function handleChangePassword() {
  const valid = await pwdFormRef.value?.validate().catch(() => false)
  if (!valid) return
  changingPwd.value = true
  try {
    await changePasswordApi({
      old_password: pwdForm.old_password,
      new_password: pwdForm.new_password,
    })
    ElMessage.success('密码修改成功，请重新登录')
    pwdForm.old_password = ''
    pwdForm.new_password = ''
    pwdForm.confirm_password = ''
    await userStore.logout()
    router.push({ name: 'Login' })
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '修改失败')
  } finally {
    changingPwd.value = false
  }
}
</script>
