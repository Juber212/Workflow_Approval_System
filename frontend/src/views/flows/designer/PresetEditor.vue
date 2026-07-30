<template>
  <!-- 预设编辑弹窗 —— 新建/编辑节点预设 -->
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :title="isEdit ? '编辑预设' : '新建预设'"
    width="460px"
    @close="handleClose"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="80px" label-position="top">
      <el-form-item label="预设名称" prop="name">
        <el-input v-model="form.name" placeholder="列表中显示的名称" maxlength="30" show-word-limit />
      </el-form-item>
      <el-form-item label="节点名称" prop="node_name">
        <el-input v-model="form.node_name" placeholder="拖出后节点的默认名称" maxlength="30" show-word-limit />
      </el-form-item>
      <el-form-item label="负责人" prop="assignee_id">
        <UserSelector
          v-model="form.assignee_id"
          :initial-options="assigneeInitialOptions"
          placeholder="搜索并选择负责人"
          org-members
          @update:model-value="handleAssigneeChange"
          @options-loaded="handleOptionsLoaded"
        />
      </el-form-item>
      <el-form-item label="校验人">
        <UserSelector
          v-model="form.checkers"
          :multiple="false"
          :initial-options="checkerInitialOptions"
          placeholder="搜索并选择校验人"
          org-members
          @update:model-value="handleCheckersChange"
          @options-loaded="handleOptionsLoaded"
        />
      </el-form-item>
      <el-form-item label="审批人">
        <UserSelector
          v-model="form.approvers"
          :multiple="false"
          :initial-options="approverInitialOptions"
          placeholder="搜索并选择审批人"
          org-members
          @update:model-value="handleApproversChange"
          @options-loaded="handleOptionsLoaded"
        />
      </el-form-item>
      <el-form-item label="时限（工作日）">
        <el-input-number v-model="form.time_limit_days" :min="1" :max="365" placeholder="1~365" style="width:100%" />
      </el-form-item>
      <el-form-item label="文件上传">
        <el-switch v-model="form.require_file" active-text="必须上传" inactive-text="可不上传" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/** 预设编辑弹窗 —— 新建/编辑节点预设配置 */
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import UserSelector from '@/components/UserSelector.vue'
import type { UserSearchItem } from '@/api/admin'
import { createPreset, updatePreset, type PresetFormData } from '@/api/presets'

const props = defineProps<{
  modelValue: boolean
  initial?: PresetFormData | null  // 编辑时传入已有数据
  editingId?: number | null        // 编辑时传预设 ID
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  saved: []
}>()

const formRef = ref<FormInstance>()
const saving = ref(false)
const isEdit = computed(() => !!props.editingId)

/** 用户名称缓存 */
const userNameCache = reactive<Record<number, string>>({})

const form = reactive({
  name: '',
  node_name: '',
  assignee_id: undefined as number | undefined,
  checkers: undefined as number | undefined,
  approvers: undefined as number | undefined,
  time_limit_days: 3,
  require_file: true,
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入预设名称', trigger: 'blur' }],
  node_name: [{ required: true, message: '请输入节点名称', trigger: 'blur' }],
}

/** 初始选项 —— 让 UserSelector 显示已有姓名 */
const assigneeInitialOptions = computed<UserSearchItem[]>(() => {
  if (form.assignee_id) {
    const name = userNameCache[form.assignee_id] || ''
    return [{ id: form.assignee_id, username: '', real_name: name, organization_id: null, organization_name: null }]
  }
  return []
})

const checkerInitialOptions = computed<UserSearchItem[]>(() => {
  if (form.checkers != null) {
    return [{ id: form.checkers, username: '', real_name: userNameCache[form.checkers] || '', organization_id: null, organization_name: null }]
  }
  return []
})

const approverInitialOptions = computed<UserSearchItem[]>(() => {
  if (form.approvers != null) {
    return [{ id: form.approvers, username: '', real_name: userNameCache[form.approvers] || '', organization_id: null, organization_name: null }]
  }
  return []
})

/** 加载初始数据 */
function loadInitial() {
  if (props.initial) {
    // 预填 userNameCache —— 从 initial 携带的姓名中提取，避免 UserSelector 初次渲染时空白
    if (props.initial.assignee_id && props.initial.assignee_name) {
      userNameCache[props.initial.assignee_id] = props.initial.assignee_name
    }
    if (props.initial.checkers && props.initial.checkers_names) {
      props.initial.checkers.forEach((c, i) => {
        const name = props.initial?.checkers_names?.[i]
        if (name) userNameCache[c.user_id] = name
      })
    }
    if (props.initial.approvers && props.initial.approvers_names) {
      props.initial.approvers.forEach((a, i) => {
        const name = props.initial?.approvers_names?.[i]
        if (name) userNameCache[a.user_id] = name
      })
    }

    form.name = props.initial.name || ''
    form.node_name = props.initial.node_name || ''
    form.assignee_id = props.initial.assignee_id ?? undefined
    form.checkers = props.initial.checkers?.[0]?.user_id ?? undefined
    form.approvers = props.initial.approvers?.[0]?.user_id ?? undefined
    form.time_limit_days = props.initial.time_limit_days ?? 3
    form.require_file = props.initial.require_file ?? true
  } else {
    form.name = ''
    form.node_name = ''
    form.assignee_id = undefined
    form.checkers = undefined
    form.approvers = undefined
    form.time_limit_days = 3
    form.require_file = true
  }
}

/** 弹窗打开/切换时重置 */
watch(() => props.modelValue, (visible) => {
  if (visible) loadInitial()
})

/** UserSelector 加载完成 */
function handleOptionsLoaded(users: Array<{ id: number; real_name: string }>) {
  for (const u of users) userNameCache[u.id] = u.real_name
}

function handleAssigneeChange(_val: number | undefined) { /* 不需要额外处理 */ }
function handleCheckersChange(_val: number | undefined) { /* 不需要额外处理 */ }
function handleApproversChange(_val: number | undefined) { /* 不需要额外处理 */ }

/** 关闭时重置表单 */
function handleClose() {
  formRef.value?.resetFields()
  loadInitial()
}

/** 保存 */
async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    const data: PresetFormData = {
      name: form.name.trim(),
      node_name: form.node_name.trim(),
      assignee_id: form.assignee_id || null,
      checkers: form.checkers != null ? [{ user_id: form.checkers }] : null,
      approvers: form.approvers != null ? [{ user_id: form.approvers }] : null,
      time_limit_days: form.time_limit_days,
      require_file: form.require_file,
    }

    if (props.editingId) {
      await updatePreset(props.editingId, data)
      ElMessage.success('预设已更新')
    } else {
      await createPreset(data)
      ElMessage.success('预设已创建')
    }
    emit('update:modelValue', false)
    emit('saved')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>
