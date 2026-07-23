<template>
  <div class="property-panel">
    <!-- 空状态：未选中节点 -->
    <div v-if="!nodeData" class="panel-empty">
      <el-icon :size="48" color="#c0c4cc"><InfoFilled /></el-icon>
      <p class="empty-text">请选择节点进行配置</p>
      <p class="empty-hint">点击画布上的节点查看和编辑属性</p>
    </div>

    <!-- 系统节点：开始/结束 -->
    <div v-else-if="isSystemNode" class="panel-system">
      <el-icon :size="48" color="#409eff"><Setting /></el-icon>
      <p class="system-text">系统默认节点，无需配置</p>
      <p class="system-hint">
        {{ nodeData.properties?.is_start ? '开始节点由系统自动生成，显示发起人姓名，发起后自动跳过' : '结束节点为发起人终审节点，查看全部文件后通过则归档' }}
      </p>
    </div>

    <!-- 工作节点配置表单 -->
    <div v-else class="panel-form">
      <div class="panel-title">
        <span class="node-label">工作节点配置</span>
        <div class="panel-title__right">
          <el-tag size="small" :type="isConfigured ? 'success' : 'warning'">
            {{ isConfigured ? '已配置' : '未配置' }}
          </el-tag>
          <el-button
            v-show="isConfigured"
            text
            size="small"
            type="primary"
            @click="emit('save-as-preset', form)"
            style="margin-left: 6px"
          >
            💾 保存为预设
          </el-button>
        </div>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        label-position="top"
        size="default"
        class="config-form"
      >
        <!-- 节点名称 -->
        <el-form-item
          label="节点名称"
          prop="name"
          :rules="[{ required: true, message: '请输入节点名称', trigger: 'blur' }]"
        >
          <el-input
            v-model="form.name"
            placeholder="例如：部门审批、财务复核"
            maxlength="30"
            show-word-limit
            @change="syncToNode"
          />
        </el-form-item>

        <!-- 节点描述 -->
        <el-form-item label="节点描述" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="2"
            placeholder="节点补充说明（可选）"
            maxlength="500"
            show-word-limit
            @change="syncToNode"
          />
        </el-form-item>

        <!-- 负责人 -->
        <el-form-item
          label="负责人"
          prop="assignee_id"
          :rules="[{ required: true, message: '请选择负责人', trigger: 'change' }]"
        >
          <UserSelector
            v-model="form.assignee_id"
            :initial-options="assigneeInitialOptions"
            placeholder="搜索并选择负责人"
            org-members
            @update:model-value="handleAssigneeChange"
            @options-loaded="handleOptionsLoaded"
          />
        </el-form-item>

        <!-- 校验人（多人） -->
        <el-form-item
          label="校验人"
          prop="checkers"
          :rules="[{ required: true, message: '请选择校验人', trigger: 'change', type: 'array', min: 1 }]"
        >
          <UserSelector
            v-model="form.checkers"
            :multiple="true"
            :initial-options="checkerInitialOptions"
            placeholder="搜索并选择校验人（可多选）"
            org-members
            @update:model-value="handleCheckersChange"
            @options-loaded="handleOptionsLoaded"
          />
        </el-form-item>

        <!-- 审批人（多人） -->
        <el-form-item
          label="审批人"
          prop="approvers"
          :rules="[{ required: true, message: '请选择审批人', trigger: 'change', type: 'array', min: 1 }]"
        >
          <UserSelector
            v-model="form.approvers"
            :multiple="true"
            :initial-options="approverInitialOptions"
            placeholder="搜索并选择审批人（可多选）"
            org-members
            @update:model-value="handleApproversChange"
            @options-loaded="handleOptionsLoaded"
          />
        </el-form-item>

        <!-- 批准人（单人，仅难度4时生效） -->
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

        <!-- 完成时限 -->
        <!-- 编辑模式：数字输入框（工作日天数） -->
        <el-form-item
          v-if="!launchMode"
          label="完成时限（工作日）"
          prop="time_limit_days"
          :rules="[{ required: true, message: '请设置完成时限' }]"
        >
          <el-input-number
            v-model="form.time_limit_days"
            :min="1"
            :max="365"
            :step="1"
            placeholder="1~365"
            style="width: 100%"
            @change="syncToNode"
          />
        </el-form-item>

        <!-- 发起模式：日期范围选择器（预估开始 → 截止，预填跳过节假日的日期） -->
        <el-form-item
          v-else
          label="计划日期"
          prop="deadlineRange"
          :rules="[{ required: true, message: '请选择计划日期范围', trigger: 'change' }]"
        >
          <el-date-picker
            v-model="form.deadlineRange"
            type="daterange"
            start-placeholder="预估开始"
            end-placeholder="截止日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
            @change="syncToNode"
          />
          <div class="field-hint">
            开始：发起日期 + 前序节点累计 · 截止：开始 + {{ form.time_limit_days ?? '?' }} 工作日（已跳过法定节假日和周末）
          </div>
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
              @change="handleFolderModeToggle"
            />
          </div>

          <!-- 简单模式：require_file 开关（向后兼容） -->
          <template v-if="!useFileFolders">
            <el-form-item label="文件上传">
              <el-switch
                v-model="form.require_file"
                active-text="必须上传"
                inactive-text="可不上传"
                @change="syncToNode"
              />
            </el-form-item>
          </template>

          <!-- 文件夹模式：文件夹卡片列表 -->
          <template v-else>
            <div class="folder-list" v-if="folders.length > 0">
              <div
                v-for="(folder, idx) in folders"
                :key="idx"
                class="folder-card"
                :class="{ 'folder-card--expanded': expandedFolderIdx === idx }"
              >
                <!-- 折叠态：摘要行 -->
                <div class="folder-card__summary" @click="toggleFolder(idx)">
                  <span class="folder-card__icon">📁</span>
                  <span class="folder-card__name">{{ folder.name || '未命名文件夹' }}</span>
                  <span class="folder-card__rule">{{ folderRuleSummary(folder) }}</span>
                  <el-icon class="folder-card__arrow" :class="{ rotated: expandedFolderIdx === idx }"><ArrowRight /></el-icon>
                </div>

                <!-- 展开态：编辑表单 -->
                <div class="folder-card__body" v-show="expandedFolderIdx === idx">
                  <el-form label-position="top" size="small">
                    <el-form-item label="文件夹名称" :rules="[{ required: true, message: '请输入文件夹名称' }]">
                      <el-input
                        v-model="folder.name"
                        placeholder="例如：资质文件"
                        maxlength="20"
                        show-word-limit
                        @change="handleFolderChange"
                      />
                    </el-form-item>
                    <el-form-item label="必须提交">
                      <el-switch
                        v-model="folder.required"
                        active-text="必须提交"
                        inactive-text="可选"
                        @change="handleFolderChange"
                      />
                    </el-form-item>
                    <el-form-item v-if="folder.required" label="文件数量">
                      <el-radio-group v-model="folderCountMode[idx]" @change="handleFolderCountModeChange(idx)" size="small">
                        <el-radio-button value="unlimited">不限制</el-radio-button>
                        <el-radio-button value="exact">精确数量</el-radio-button>
                      </el-radio-group>
                      <el-input-number
                        v-if="folderCountMode[idx] === 'exact'"
                        v-model="folder.file_count"
                        :min="1"
                        :max="99"
                        style="width:100%;margin-top:8px"
                        @change="handleFolderChange"
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

            <el-button
              type="primary"
              plain
              size="small"
              style="width:100%;margin-top:8px"
              @click="addFolder"
            >
              + 添加文件夹
            </el-button>

            <!-- 名称冲突警告 -->
            <el-alert
              v-if="folderNameConflict"
              type="warning"
              :closable="false"
              show-icon
              style="margin-top:8px"
            >
              {{ folderNameConflict }}
            </el-alert>
          </template>
        </div>

        <!-- 签批配置 —— 三个独立开关 -->
        <el-form-item label="签批配置">
          <div class="sig-switches">
            <el-checkbox v-model="form.require_assignee_signature" @change="syncToNode">
              负责人提交时签名
            </el-checkbox>
            <el-checkbox v-model="form.require_checker_signature" @change="syncToNode">
              校验人通过时签名
            </el-checkbox>
            <el-checkbox v-model="form.require_approver_signature" @change="syncToNode">
              审批人通过时签名
            </el-checkbox>
            <el-checkbox v-model="form.require_endorser_signature" @change="syncToNode">
              批准人通过时签名
            </el-checkbox>
          </div>
        </el-form-item>

        <!-- 签名位置（至少一个开关开启时显示） -->
        <template v-if="form.require_assignee_signature || form.require_checker_signature || form.require_approver_signature || form.require_endorser_signature">
          <el-form-item label="签名X坐标">
            <el-input-number v-model="form.signature_x" :min="0" :max="800" style="width:100%" @change="syncToNode" />
          </el-form-item>
          <el-form-item label="签名Y坐标">
            <el-input-number v-model="form.signature_y" :min="0" :max="800" style="width:100%" @change="syncToNode" />
          </el-form-item>
          <el-form-item label="签名页码（-1=最后一页）">
            <el-input-number v-model="form.signature_page" :min="-1" :max="100" style="width:100%" @change="syncToNode" />
          </el-form-item>
        </template>

      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { InfoFilled, Setting, ArrowRight } from '@element-plus/icons-vue'
import UserSelector from '@/components/UserSelector.vue'
import type { UserSearchItem } from '@/api/admin'
import type { FileFolderConfig } from '@/api/designer'

/** Props */
const props = defineProps<{
  /** LogicFlow 实例（用于读写节点属性） */
  lf?: any
  /** 当前选中节点的 LogicFlow 数据 */
  nodeData?: any
  /** 是否为发起项目模式（显示日历而非数字输入框） */
  launchMode?: boolean
  /** 发起模式下预计算好的日期映射 { 节点模板ID → { begin, deadline } } */
  deadlineMap?: Record<number, { begin: string; deadline: string }>
}>()

/** emit 事件 */
const emit = defineEmits<{
  'save-as-preset': [formData: typeof form]
}>()

/** 表单引用 */
const formRef = ref()

/** 表单本地状态 */
const form = reactive({
  name: '',
  description: '',
  assignee_id: undefined as number | undefined,
  assignee_name: '' as string,
  checkers: [] as number[],
  checkers_names: [] as string[],
  approvers: [] as number[],
  approvers_names: [] as string[],
  time_limit_days: undefined as number | undefined,
  deadlineRange: undefined as [string, string] | undefined,  // 发起模式：[begin, deadline]
  require_file: false,
  require_assignee_signature: true,
  require_checker_signature: true,
  require_approver_signature: true,
  endorser_id: undefined as number | undefined,
  endorser_name: '' as string,
  require_endorser_signature: true,
  signature_x: 400,
  signature_y: 100,
  signature_page: -1,
})

/** 文件夹配置 */
const folders = ref<FileFolderConfig[]>([])
/** 是否使用文件夹模式 */
const useFileFolders = ref(false)
/** 当前展开的文件夹索引 */
const expandedFolderIdx = ref<number | null>(null)
/** 每个文件夹的数量模式：unlimited | exact */
const folderCountMode = reactive<Record<number, string>>({})

/** 用户名称缓存 —— 从 UserSelector options-loaded 事件积累 */
const userNameCache = reactive<Record<number, string>>({})

/** 是否系统节点（开始/结束） */
const isSystemNode = computed(() => {
  if (!props.nodeData) return false
  return props.nodeData.properties?.is_start || props.nodeData.properties?.is_end
})

/** 简要判断节点是否已配置（必填字段均填写） */
const isConfigured = computed(() => {
  // 发起模式：检查日期范围
  const hasDeadline = props.launchMode
    ? (form.deadlineRange && form.deadlineRange.length === 2)
    : (form.time_limit_days && form.time_limit_days >= 1)
  return !!(
    form.name &&
    form.assignee_id &&
    form.checkers.length > 0 &&
    form.approvers.length > 0 &&
    hasDeadline
  )
})

/** 预填选项 —— 从已保存节点属性构造初始选项，避免 UserSelector 显示裸 ID */
const assigneeInitialOptions = computed<UserSearchItem[]>(() => {
  if (form.assignee_id && form.assignee_name) {
    return [{ id: form.assignee_id, username: '', real_name: form.assignee_name, organization_id: null, organization_name: null }]
  }
  return []
})

const checkerInitialOptions = computed<UserSearchItem[]>(() => {
  const ids = form.checkers || []
  const names = form.checkers_names || []
  return ids.map((id, i) => ({
    id, username: '', real_name: names[i] || `用户${id}`, organization_id: null, organization_name: null,
  }))
})

const approverInitialOptions = computed<UserSearchItem[]>(() => {
  const ids = form.approvers || []
  const names = form.approvers_names || []
  return ids.map((id, i) => ({
    id, username: '', real_name: names[i] || `用户${id}`, organization_id: null, organization_name: null,
  }))
})

/** 批准人初始选项（单人） */
const endorserInitialOptions = computed<UserSearchItem[]>(() => {
  if (!form.endorser_id) return []
  return [{
    id: form.endorser_id, username: '', real_name: form.endorser_name || `用户${form.endorser_id}`,
    organization_id: null, organization_name: null,
  }]
})

/** 上次加载的节点 ID（用于检测切换） */
let lastNodeId: string | null = null

/** 同步 LogicFlow 节点属性 → 表单 */
function loadFromNode() {
  if (!props.nodeData) {
    lastNodeId = null
    return
  }

  const nodeId = props.nodeData.id || ''
  if (nodeId === lastNodeId) return  // 同一节点，不需要重新加载
  lastNodeId = nodeId

  const p = props.nodeData.properties || {}
  form.name = p.name || ''
  form.description = p.description || ''
  form.assignee_id = p.assignee_id ?? undefined
  form.assignee_name = p.assignee_name || ''
  form.checkers = Array.isArray(p.checkers) ? [...p.checkers] : []
  form.checkers_names = Array.isArray(p.checkers_names) ? [...p.checkers_names] : []
  form.approvers = Array.isArray(p.approvers) ? [...p.approvers] : []
  form.approvers_names = Array.isArray(p.approvers_names) ? [...p.approvers_names] : []
  form.time_limit_days = p.time_limit_days ?? undefined
  form.require_file = p.require_file ?? false
  form.require_assignee_signature = p.require_assignee_signature ?? true
  form.require_checker_signature = p.require_checker_signature ?? true
  form.require_approver_signature = p.require_approver_signature ?? true
  form.endorser_id = p.endorser_id ?? undefined
  form.endorser_name = p.endorser_name || ''
  form.require_endorser_signature = p.require_endorser_signature ?? true
  form.signature_x = p.signature_x ?? 400
  form.signature_y = p.signature_y ?? 100
  form.signature_page = p.signature_page ?? -1

  // 发起模式：从预计算映射取 begin + deadline 填入日期范围
  const dbId = p.db_id
  if (props.launchMode && props.deadlineMap && dbId != null) {
    // 优先用节点上已保存的范围（用户手动调整过的），否则用预计算值
    const mapEntry = props.deadlineMap[dbId]
    if (p.deadline_range && Array.isArray(p.deadline_range) && p.deadline_range.length === 2) {
      form.deadlineRange = p.deadline_range as [string, string]
    } else if (mapEntry) {
      form.deadlineRange = [mapEntry.begin, mapEntry.deadline] as [string, string]
    } else {
      form.deadlineRange = undefined
    }
  } else {
    form.deadlineRange = undefined
  }

  // 文件夹配置
  const rawFolders = p.file_folders
  if (rawFolders && Array.isArray(rawFolders) && rawFolders.length > 0) {
    useFileFolders.value = true
    folders.value = rawFolders.map((f: any, i: number) => {
      folderCountMode[i] = f.file_count != null ? 'exact' : 'unlimited'
      return { name: f.name || '', required: f.required ?? false, file_count: f.file_count ?? null }
    })
  } else {
    useFileFolders.value = false
    folders.value = []
  }
}

/** 同步表单 → LogicFlow 节点（即时生效，不持久化） */
function syncToNode() {
  if (!props.lf || !props.nodeData) return
  const nodeId = props.nodeData.id
  if (!nodeId) return

  const node = props.lf.getNodeModelById(nodeId)
  if (!node) return

  // 更新 LogicFlow 节点属性（前端本地）
  props.lf.setProperties(nodeId, {
    name: form.name,
    description: form.description,
    assignee_id: form.assignee_id ?? null,
    assignee_name: form.assignee_name || null,
    checkers: form.checkers.length > 0 ? [...form.checkers] : null,
    checkers_names: form.checkers_names.length > 0 ? [...form.checkers_names] : null,
    approvers: form.approvers.length > 0 ? [...form.approvers] : null,
    approvers_names: form.approvers_names.length > 0 ? [...form.approvers_names] : null,
    time_limit_days: form.time_limit_days ?? null,
    require_file: form.require_file,
    file_folders: useFileFolders.value && folders.value.length > 0
      ? folders.value.filter(f => f.name.trim())  // 过滤掉空名称的文件夹
      : null,
    require_assignee_signature: form.require_assignee_signature,
    require_checker_signature: form.require_checker_signature,
    require_approver_signature: form.require_approver_signature,
    endorser_id: form.endorser_id ?? null,
    endorser_name: form.endorser_name || null,
    require_endorser_signature: form.require_endorser_signature,
    signature_x: form.signature_x,
    signature_y: form.signature_y,
    signature_page: form.signature_page,
    // 发起模式下保存 deadline_range，后续 handleLaunch 会收集为 node_override
    ...(props.launchMode && form.deadlineRange?.length === 2 ? { deadline_range: form.deadlineRange } : {}),
  })
}

/** UserSelector 加载完成 —— 缓存用户名称映射 */
function handleOptionsLoaded(users: Array<{ id: number; real_name: string }>) {
  for (const u of users) {
    userNameCache[u.id] = u.real_name
  }
}

/** 负责人变更 —— 同步名称 + 写入节点 */
function handleAssigneeChange(val: number | undefined) {
  form.assignee_name = val ? (userNameCache[val] || '') : ''
  syncToNode()
}

/** 校验人变更 —— 同步名称 + 写入节点 */
function handleCheckersChange(val: number[]) {
  form.checkers_names = (val || []).map(id => userNameCache[id] || '').filter(Boolean)
  syncToNode()
}

/** 审批人变更 —— 同步名称 + 写入节点 */
function handleApproversChange(val: number[]) {
  form.approvers_names = (val || []).map(id => userNameCache[id] || '').filter(Boolean)
  syncToNode()
}

/** 批准人变更 —— 同步名称 + 写入节点 */
function handleEndorserChange(val: number | undefined) {
  form.endorser_name = val ? (userNameCache[val] || '') : ''
  syncToNode()
}

// ========== 文件夹管理 ==========

/** 文件夹规则摘要文字 */
function folderRuleSummary(f: FileFolderConfig): string {
  if (!f.required) return '可选'
  if (f.file_count == null) return '至少1个，不限'
  return `必须提交 · ${f.file_count}个`
}

/** 展开/折叠文件夹 */
function toggleFolder(idx: number) {
  expandedFolderIdx.value = expandedFolderIdx.value === idx ? null : idx
}

/** 添加文件夹 */
function addFolder() {
  const idx = folders.value.length
  folders.value.push({ name: '', required: false, file_count: null })
  folderCountMode[idx] = 'unlimited'
  expandedFolderIdx.value = idx  // 自动展开新建的文件夹
  syncToNode()
}

/** 删除文件夹 */
function removeFolder(idx: number) {
  folders.value.splice(idx, 1)
  delete folderCountMode[idx]
  if (expandedFolderIdx.value === idx) expandedFolderIdx.value = null
  syncToNode()
}

/** 文件夹配置变更 */
function handleFolderChange() {
  syncToNode()
}

/** 数量模式切换 */
function handleFolderCountModeChange(idx: number) {
  const folder = folders.value[idx]
  if (!folder) return
  if (folderCountMode[idx] === 'unlimited') {
    folder.file_count = null
  } else {
    folder.file_count = folder.file_count || 1
  }
  syncToNode()
}

/** 文件夹模式切换 */
function handleFolderModeToggle(val: boolean) {
  if (val) {
    // 切换到文件夹模式：清空旧 require_file，初始化空文件夹列表
    form.require_file = false
    folders.value = []
  } else {
    // 切换回简单模式：清空文件夹配置
    folders.value = []
    expandedFolderIdx.value = null
  }
  syncToNode()
}

/** 同名文件夹冲突检测（同模板内跨节点） */
const folderNameConflict = computed<string | null>(() => {
  if (!useFileFolders.value || !props.lf) return null
  const currentName = form.name
  // 收集当前节点所有非空文件夹名
  const currentNames = new Set(folders.value.map(f => f.name.trim()).filter(Boolean))
  // 检查同一节点内重复
  if (currentNames.size < folders.value.filter(f => f.name.trim()).length) {
    return '当前节点内存在重复的文件夹名称'
  }
  return null
})

/** 节点变化时重新加载表单 */
watch(() => props.nodeData, () => {
  loadFromNode()
}, { immediate: true })
</script>

<style lang="scss" scoped>
.property-panel {
  width: 320px;
  height: 100%;
  background: #fff;
  border-left: 1px solid var(--el-border-color-light);
  overflow-y: auto;
  flex-shrink: 0;
}

/* 空状态 */
.panel-empty,
.panel-system {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 40px 24px;
  text-align: center;

  .empty-text,
  .system-text {
    margin: 16px 0 8px;
    font-size: 15px;
    font-weight: 600;
    color: var(--el-text-color-regular);
  }

  .empty-hint,
  .system-hint {
    margin: 0;
    font-size: 13px;
    color: var(--el-text-color-secondary);
    line-height: 1.6;
  }
}

/* 表单区域 */
.panel-form {
  padding: 16px;

  .panel-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;

    &__right { display: flex; align-items: center; }

    .node-label {
      font-size: 15px;
      font-weight: 600;
      color: var(--el-text-color-primary);
    }
  }

  .config-form {
    .field-hint {
      font-size: 12px;
      color: var(--el-text-color-secondary);
      margin-top: 4px;
      line-height: 1.5;
    }
  }
}

/* 文件提交配置区域 */
.file-folders-section {
  margin-bottom: 16px;

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
