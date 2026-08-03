<template>
  <el-dialog
    v-model="visible"
    :title="isEdit ? '编辑用户' : '新增用户'"
    width="520px"
    :close-on-click-modal="false"
    @closed="handleClosed"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
      <!-- 用户名（新增时显示，编辑时禁用） -->
      <el-form-item label="用户名" prop="username">
        <el-input v-model="form.username" :disabled="isEdit" placeholder="字母、数字、下划线" />
      </el-form-item>

      <!-- 真实姓名 -->
      <el-form-item label="真实姓名" prop="real_name">
        <el-input v-model="form.real_name" placeholder="请输入真实姓名" />
      </el-form-item>

      <!-- 所属组织 -->
      <el-form-item label="所属组织" prop="organization_id">
        <el-select v-model="form.organization_id" placeholder="请选择组织" style="width: 100%">
          <el-option
            v-for="org in orgOptions"
            :key="org.id"
            :label="org.name"
            :value="org.id"
          />
        </el-select>
      </el-form-item>

      <!-- 角色（单选：一个用户只挂一个角色） -->
      <el-form-item label="角色" prop="role_id">
        <el-select v-model="form.role_id" placeholder="请选择角色" style="width: 100%">
          <el-option
            v-for="role in roleOptions"
            :key="role.id"
            :label="role.name"
            :value="role.id"
          />
        </el-select>
      </el-form-item>

      <!-- 邮箱 -->
      <el-form-item label="邮箱" prop="email">
        <el-input v-model="form.email" placeholder="选填" />
      </el-form-item>

      <!-- 手机号 -->
      <el-form-item label="手机号" prop="phone">
        <el-input v-model="form.phone" placeholder="选填" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch, computed } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import type { OrgOption, RoleOption } from '@/api/admin'

/** Props */
const props = defineProps<{
  modelValue: boolean
  isEdit: boolean
  /** 编辑时的初始数据 */
  initialData?: {
    username: string
    real_name: string
    organization_id: number | null
    roles: string[]
    email: string | null
    phone: string | null
  } | null
  orgOptions: OrgOption[]
  roleOptions: RoleOption[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [data: {
    username: string
    real_name: string
    organization_id: number | null
    role_id: number
    email: string | null
    phone: string | null
  }]
}>()

const visible = ref(props.modelValue)
watch(() => props.modelValue, (v) => { visible.value = v })
watch(visible, (v) => { emit('update:modelValue', v) })

const formRef = ref<FormInstance>()
const submitting = ref(false)

/** 当前选中角色是否为系统管理员 */
const isAdminSelected = computed(() => {
  const adminRole = props.roleOptions.find(r => r.code === 'system_admin')
  return adminRole ? form.role_id === adminRole.id : false
})

/** 表单数据 */
const form = reactive({
  username: '',
  real_name: '',
  organization_id: null as number | null,
  role_id: null as number | null,
  email: '' as string | null,
  phone: '' as string | null,
})

/** 表单校验规则 */
const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_]+$/, message: '仅允许字母、数字、下划线', trigger: 'blur' },
    { min: 3, max: 30, message: '3~30 个字符', trigger: 'blur' },
  ],
  real_name: [{ required: true, message: '请输入真实姓名', trigger: 'blur' }],
  email: [
    { pattern: /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/, message: '邮箱格式不正确', trigger: 'blur' },
  ],
  phone: [
    { pattern: /^1[3-9]\d{9}$/, message: '手机号格式不正确（11位）', trigger: 'blur' },
  ],
  organization_id: [{ required: true, message: '请选择组织', trigger: 'change' }],
  role_id: [{ required: true, message: '请选择一个角色', trigger: 'change' }],
}

/** 监听角色变动 → 动态切换组织字段必填（管理员可选，其他角色必填） */
watch(isAdminSelected, (isAdmin) => {
  if (formRef.value) {
    formRef.value.clearValidate('organization_id')
  }
  // 动态修改 organization_id 的 required 规则（rules 值可能是单条或数组，统一取数组首条）
  const orgRules = rules.organization_id
  const orgRule = Array.isArray(orgRules) ? orgRules[0] : orgRules
  if (orgRule) {
    orgRule.required = !isAdmin
    orgRule.message = isAdmin ? undefined : '非管理员必须选择组织'
  }
})

/** 弹窗打开时初始化表单 */
watch(visible, (val) => {
  if (val && props.initialData) {
    form.username = props.initialData.username
    form.real_name = props.initialData.real_name
    form.organization_id = props.initialData.organization_id
    form.email = props.initialData.email
    form.phone = props.initialData.phone
    // 角色名 → 角色 ID 反向映射（单选：取第一个角色）
    const roleMap = new Map(props.roleOptions.map(r => [r.code, r.id]))
    form.role_id = props.initialData.roles.length ? (roleMap.get(props.initialData.roles[0]) ?? null) : null
  } else if (val && !props.initialData) {
    form.username = ''
    form.real_name = ''
    form.organization_id = null
    form.role_id = null
    form.email = ''
    form.phone = ''
  }
})

/** 提交 */
async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    emit('submit', {
      username: form.username,
      real_name: form.real_name,
      organization_id: form.organization_id,
      role_id: form.role_id as number,
      email: form.email || null,
      phone: form.phone || null,
    })
    visible.value = false
  } catch {
    // 错误由父组件处理
  } finally {
    submitting.value = false
  }
}

/** 弹窗关闭后重置表单 */
function handleClosed() {
  formRef.value?.resetFields()
}
</script>
