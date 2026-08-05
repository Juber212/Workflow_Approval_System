<template>
  <!-- 预设编辑弹窗 —— 新建/编辑节点预设 -->
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :title="isEdit ? '编辑预设' : '新建预设'"
    width="560px"
    @close="handleClose"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="80px" label-position="top">
      <!-- 基础信息 -->
      <el-form-item label="预设名称" prop="name">
        <el-input v-model="form.name" placeholder="列表中显示的名称" maxlength="30" show-word-limit />
      </el-form-item>
      <el-form-item label="节点名称" prop="node_name">
        <el-input v-model="form.node_name" placeholder="拖出后节点的默认名称" maxlength="30" show-word-limit />
      </el-form-item>

      <!-- ═══════ 人员配置 ═══════ -->
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
      <!-- 批准人（仅难度4时生效） -->
      <el-form-item label="批准人">
        <UserSelector
          v-model="form.endorser_id"
          :multiple="false"
          :initial-options="endorserInitialOptions"
          placeholder="可选，仅难度4级时生效"
          org-members
          @update:model-value="handleEndorserChange"
          @options-loaded="handleOptionsLoaded"
        />
        <div class="field-hint">批准人在所有审批人通过后操作，可审核、签字、驳回。仅难度4级时生效。</div>
      </el-form-item>

      <!-- 时限 -->
      <el-form-item label="时限（工作日）">
        <el-input-number v-model="form.time_limit_days" :min="1" :max="365" placeholder="1~365" style="width:100%" />
      </el-form-item>

      <el-divider content-position="left">高级设置</el-divider>

      <!-- 文件提交配置（P2-2 共享组件：文件夹增删改 + 模式切换，保存时一次性构建） -->
      <FolderConfigEditor
        v-model:folders="folders"
        v-model:use-file-folders="useFileFolders"
        v-model:require-file="form.require_file"
        compact
      />

      <!-- 签批配置 -->
      <el-form-item label="签批配置" style="margin-top:12px">
        <div class="sig-switches">
          <el-checkbox v-model="form.require_assignee_signature">负责人提交时签名</el-checkbox>
          <el-checkbox v-model="form.require_checker_signature">校验人通过时签名</el-checkbox>
          <el-checkbox v-model="form.require_approver_signature">审批人通过时签名</el-checkbox>
          <el-checkbox v-model="form.require_endorser_signature">批准人通过时签名</el-checkbox>
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/** 预设编辑弹窗 —— 新建/编辑节点预设配置（含文件提交文件夹 + 签批配置 + 批准人） */
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import UserSelector from '@/components/UserSelector.vue'
import type { UserSearchItem } from '@/api/admin'
import type { FileFolderConfig } from '@/api/designer'
import { createPreset, updatePreset, type PresetFormData } from '@/api/presets'
import FolderConfigEditor from './FolderConfigEditor.vue'

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

/** 表单状态 */
const form = reactive({
  name: '',
  node_name: '',
  assignee_id: undefined as number | undefined,
  checkers: undefined as number | undefined,
  approvers: undefined as number | undefined,
  endorser_id: undefined as number | undefined,
  time_limit_days: 3,
  require_file: true,
  require_assignee_signature: true,
  require_checker_signature: true,
  require_approver_signature: true,
  require_endorser_signature: true,
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入预设名称', trigger: 'blur' }],
  node_name: [{ required: true, message: '请输入节点名称', trigger: 'blur' }],
}

// ─── 文件夹配置（v-model 给 FolderConfigEditor，展开/数量模式状态在组件内部） ───
const folders = ref<FileFolderConfig[]>([])
const useFileFolders = ref(false)

// ─── UserSelector 初始选项 ───
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

const endorserInitialOptions = computed<UserSearchItem[]>(() => {
  if (form.endorser_id != null) {
    return [{ id: form.endorser_id, username: '', real_name: userNameCache[form.endorser_id] || '', organization_id: null, organization_name: null }]
  }
  return []
})

// ─── 加载/重置 ───
function loadInitial() {
  // 重置文件夹（展开状态由 FolderConfigEditor 内部 watch 处理）
  folders.value = []
  useFileFolders.value = false

  if (props.initial) {
    // 预填 userNameCache
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
    if (props.initial.endorser_id && props.initial.endorser_name) {
      userNameCache[props.initial.endorser_id] = props.initial.endorser_name
    }

    form.name = props.initial.name || ''
    form.node_name = props.initial.node_name || ''
    form.assignee_id = props.initial.assignee_id ?? undefined
    form.checkers = props.initial.checkers?.[0]?.user_id ?? undefined
    form.approvers = props.initial.approvers?.[0]?.user_id ?? undefined
    form.endorser_id = props.initial.endorser_id ?? undefined
    form.time_limit_days = props.initial.time_limit_days ?? 3
    form.require_file = props.initial.require_file ?? true
    form.require_assignee_signature = props.initial.require_assignee_signature ?? true
    form.require_checker_signature = props.initial.require_checker_signature ?? true
    form.require_approver_signature = props.initial.require_approver_signature ?? true
    form.require_endorser_signature = props.initial.require_endorser_signature ?? true

    // 文件夹配置（数量模式由 FolderConfigEditor 内部按 file_count 推导）
    const rawFolders = props.initial.file_folders
    if (rawFolders && Array.isArray(rawFolders) && rawFolders.length > 0) {
      useFileFolders.value = true
      folders.value = rawFolders.map((f: any) => ({
        name: f.name || '',
        required: f.required ?? false,
        file_count: f.file_count ?? null,
      }))
    }
  } else {
    form.name = ''
    form.node_name = ''
    form.assignee_id = undefined
    form.checkers = undefined
    form.approvers = undefined
    form.endorser_id = undefined
    form.time_limit_days = 3
    form.require_file = true
    form.require_assignee_signature = true
    form.require_checker_signature = true
    form.require_approver_signature = true
    form.require_endorser_signature = true
  }
}

watch(() => props.modelValue, (visible) => {
  if (visible) loadInitial()
})

function handleOptionsLoaded(users: Array<{ id: number; real_name: string }>) {
  for (const u of users) userNameCache[u.id] = u.real_name
}

// 参数类型放宽以匹配 UserSelector 的 update:model-value 签名（number | number[] | undefined）
function handleAssigneeChange(_val: number | number[] | undefined) {}
function handleCheckersChange(_val: number | number[] | undefined) {}
function handleApproversChange(_val: number | number[] | undefined) {}
function handleEndorserChange(_val: number | number[] | undefined) {}

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
    // 构建文件夹配置（仅文件夹模式且有内容时传）
    const fileFolders = useFileFolders.value && folders.value.length > 0
      ? folders.value.filter(f => f.name.trim()).map(f => ({
          name: f.name.trim(),
          required: f.required,
          file_count: f.file_count ?? null,
        }))
      : null

    const data: PresetFormData = {
      name: form.name.trim(),
      node_name: form.node_name.trim(),
      assignee_id: form.assignee_id || null,
      checkers: form.checkers != null ? [{ user_id: form.checkers }] : null,
      approvers: form.approvers != null ? [{ user_id: form.approvers }] : null,
      endorser_id: form.endorser_id ?? null,
      time_limit_days: form.time_limit_days,
      require_file: useFileFolders ? false : form.require_file,  // 文件夹模式下关闭简单开关
      file_folders: fileFolders,
      require_assignee_signature: form.require_assignee_signature,
      require_checker_signature: form.require_checker_signature,
      require_approver_signature: form.require_approver_signature,
      require_endorser_signature: form.require_endorser_signature,
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
  } catch {
    // 拦截器已统一弹错（P1-35），无需重复提示
  } finally {
    saving.value = false
  }
}
</script>

<style lang="scss" scoped>
.field-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
  line-height: 1.5;
}

/* 签批开关 */
.sig-switches {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
</style>
