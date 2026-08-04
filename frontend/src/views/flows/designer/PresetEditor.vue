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

      <!-- 文件提交配置 -->
      <div class="file-folders-section">
        <div class="file-folders-section__header">
          <span class="file-folders-section__title">文件提交配置</span>
          <el-switch
            v-model="useFileFolders"
            active-text="文件夹"
            inactive-text="简单"
            size="small"
          />
        </div>

        <!-- 简单模式：require_file 开关 -->
        <template v-if="!useFileFolders">
          <el-form-item label="文件上传">
            <el-switch v-model="form.require_file" active-text="必须上传" inactive-text="可不上传" />
          </el-form-item>
        </template>

        <!-- 文件夹模式 -->
        <template v-else>
          <div class="folder-list" v-if="folders.length > 0">
            <div
              v-for="(folder, idx) in folders"
              :key="idx"
              class="folder-card"
              :class="{ 'folder-card--expanded': expandedFolderIdx === idx }"
            >
              <div class="folder-card__summary" @click="toggleFolder(idx)">
                <span class="folder-card__icon"><el-icon :size="14"><Folder /></el-icon></span>
                <span class="folder-card__name">{{ folder.name || '未命名文件夹' }}</span>
                <span class="folder-card__rule">{{ folderRuleSummary(folder) }}</span>
                <el-icon class="folder-card__arrow" :class="{ rotated: expandedFolderIdx === idx }"><ArrowRight /></el-icon>
              </div>
              <div class="folder-card__body" v-show="expandedFolderIdx === idx">
                <el-form label-position="top" size="small">
                  <el-form-item label="文件夹名称">
                    <el-input v-model="folder.name" placeholder="例如：资质文件" maxlength="20" show-word-limit />
                  </el-form-item>
                  <el-form-item label="必须提交">
                    <el-switch v-model="folder.required" active-text="必须提交" inactive-text="可选" />
                  </el-form-item>
                  <el-form-item v-if="folder.required" label="文件数量">
                    <el-radio-group v-model="folderCountMode[idx]" size="small">
                      <el-radio-button value="unlimited">不限制</el-radio-button>
                      <el-radio-button value="exact">精确数量</el-radio-button>
                    </el-radio-group>
                    <el-input-number
                      v-if="folderCountMode[idx] === 'exact'"
                      v-model="folder.file_count"
                      :min="1" :max="99"
                      style="width:100%;margin-top:8px"
                    />
                  </el-form-item>
                </el-form>
                <el-button text type="danger" size="small" @click="removeFolder(idx)">删除文件夹</el-button>
              </div>
            </div>
          </div>
          <div class="folder-empty" v-else>
            <span class="folder-empty__hint">暂未添加文件夹，点击下方按钮添加</span>
          </div>
          <el-button type="primary" plain size="small" style="width:100%;margin-top:8px" @click="addFolder">
            + 添加文件夹
          </el-button>
        </template>
      </div>

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
import { Folder, ArrowRight } from '@element-plus/icons-vue'
import UserSelector from '@/components/UserSelector.vue'
import type { UserSearchItem } from '@/api/admin'
import { createPreset, updatePreset, type PresetFormData } from '@/api/presets'

/** 本地文件夹配置类型 */
interface LocalFolderConfig {
  name: string
  required: boolean
  file_count: number | null
}

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

// ─── 文件夹配置 ───
const folders = ref<LocalFolderConfig[]>([])
const useFileFolders = ref(false)
const expandedFolderIdx = ref<number | null>(null)
const folderCountMode = reactive<Record<number, string>>({})

function folderRuleSummary(f: LocalFolderConfig): string {
  if (!f.required) return '可选'
  if (f.file_count == null) return '至少1个，不限'
  return `必须提交 · ${f.file_count}个`
}

function toggleFolder(idx: number) {
  expandedFolderIdx.value = expandedFolderIdx.value === idx ? null : idx
}

function addFolder() {
  const idx = folders.value.length
  folders.value.push({ name: '', required: false, file_count: null })
  folderCountMode[idx] = 'unlimited'
  expandedFolderIdx.value = idx
}

function removeFolder(idx: number) {
  folders.value.splice(idx, 1)
  delete folderCountMode[idx]
  if (expandedFolderIdx.value === idx) expandedFolderIdx.value = null
}

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
  // 重置文件夹
  folders.value = []
  useFileFolders.value = false
  expandedFolderIdx.value = null

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

    // 文件夹配置
    const rawFolders = props.initial.file_folders
    if (rawFolders && Array.isArray(rawFolders) && rawFolders.length > 0) {
      useFileFolders.value = true
      folders.value = rawFolders.map((f: any, i: number) => {
        folderCountMode[i] = f.file_count != null ? 'exact' : 'unlimited'
        return { name: f.name || '', required: f.required ?? false, file_count: f.file_count ?? null }
      })
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

/* 文件提交配置区域 */
.file-folders-section {
  margin-bottom: 8px;

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
  }

  &__title {
    font-size: 13px;
    font-weight: 600;
    color: var(--el-text-color-regular);
  }

  .folder-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .folder-card {
    border: 1px solid var(--el-border-color-light);
    border-radius: 6px;
    overflow: hidden;
    transition: border-color 0.2s;

    &:hover { border-color: var(--el-color-primary-light-5); }

    &__summary {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 8px 10px;
      cursor: pointer;
      background: var(--el-fill-color-lighter);
      user-select: none;
    }

    &__icon { font-size: 14px; flex-shrink: 0; }

    &__name {
      font-size: 13px;
      font-weight: 500;
      color: var(--el-text-color-primary);
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    &__rule {
      font-size: 11px;
      color: var(--el-text-color-secondary);
      flex-shrink: 0;
      margin-left: auto;
      margin-right: 4px;
    }

    &__arrow {
      font-size: 12px;
      color: var(--el-text-color-placeholder);
      flex-shrink: 0;
      transition: transform 0.2s;
      &.rotated { transform: rotate(90deg); }
    }

    &__body {
      padding: 10px 12px;
      border-top: 1px solid var(--el-border-color-lighter);
    }
  }

  .folder-empty {
    padding: 16px 0;
    text-align: center;

    &__hint {
      font-size: 12px;
      color: var(--el-text-color-placeholder);
    }
  }
}

/* 签批开关 */
.sig-switches {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
</style>
