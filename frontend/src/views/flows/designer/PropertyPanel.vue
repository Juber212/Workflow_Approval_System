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

        <!-- ═══════ 人员配置区头部（含一键应用） ═══════ -->
        <div class="personnel-header">
          <span class="personnel-header__title">人员配置</span>
          <el-button
            v-if="hasPersonnelConfig"
            size="small"
            type="primary"
            plain
            @click="applyPersonnelToAllNodes"
          >
            ⚡ 一键应用到全部节点
          </el-button>
        </div>

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

        <!-- 校验人（单人） -->
        <el-form-item
          label="校验人"
          prop="checkers"
          :rules="[{ required: true, message: '请选择校验人', trigger: 'change' }]"
        >
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

        <!-- 审批人（单人） -->
        <el-form-item
          label="审批人"
          prop="approvers"
          :rules="[{ required: true, message: '请选择审批人', trigger: 'change' }]"
        >
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

        <!-- 发起模式：截止日期选择器（修改后自动级联下游节点） -->
        <el-form-item
          v-else
          label="截止日期"
          prop="deadline"
          :rules="[{ required: true, message: '请选择截止日期', trigger: 'change' }]"
        >
          <div class="plan-begin-row">
            <span class="plan-begin-label">计划开始</span>
            <span class="plan-begin-value">{{ form.plan_begin || '—' }}</span>
          </div>
          <el-date-picker
            v-model="form.deadline"
            type="date"
            placeholder="选择截止日期"
            value-format="YYYY-MM-DD"
            style="width: 100%; margin-top: 8px"
            @change="handleDeadlineChange"
          />
          <div class="field-hint">
            预估 {{ form.time_limit_days ?? '?' }} 个工作日（周末已跳过，节假日以发起时后端计算为准）
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
                  <span class="folder-card__icon"><el-icon :size="14"><Folder /></el-icon></span>
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

      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { InfoFilled, Setting, ArrowRight, Folder } from '@element-plus/icons-vue'
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
}>()

/** emit 事件 */
const emit = defineEmits<{
  'save-as-preset': [formData: typeof form]
}>()

/** 表单本地状态 */
const form = reactive({
  name: '',
  description: '',
  assignee_id: undefined as number | undefined,
  assignee_name: '' as string,
  checkers: undefined as number | undefined,
  checkers_name: '' as string,
  approvers: undefined as number | undefined,
  approvers_name: '' as string,
  time_limit_days: undefined as number | undefined,
  plan_begin: undefined as string | undefined,  // 发起模式：计划开始（前序节点累积计算）
  deadline: undefined as string | undefined,    // 发起模式：截止日期
  require_file: false,
  require_assignee_signature: true,
  require_checker_signature: true,
  require_approver_signature: true,
  endorser_id: undefined as number | undefined,
  endorser_name: '' as string,
  require_endorser_signature: true,
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
    ? !!form.deadline
    : (form.time_limit_days && form.time_limit_days >= 1)
  return !!(
    form.name &&
    form.assignee_id &&
    form.checkers != null &&
    form.approvers != null &&
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
  if (form.checkers != null && form.checkers_name) {
    return [{ id: form.checkers, username: '', real_name: form.checkers_name, organization_id: null, organization_name: null }]
  }
  return []
})

const approverInitialOptions = computed<UserSearchItem[]>(() => {
  if (form.approvers != null && form.approvers_name) {
    return [{ id: form.approvers, username: '', real_name: form.approvers_name, organization_id: null, organization_name: null }]
  }
  return []
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
  // 校验人/审批人：存储为数组（兼容旧数据），UI 只取第一个
  const ch = Array.isArray(p.checkers) ? p.checkers : []
  const chNames = Array.isArray(p.checkers_names) ? p.checkers_names : []
  form.checkers = ch.length > 0 ? ch[0] : undefined
  form.checkers_name = chNames.length > 0 ? chNames[0] : ''
  const ap = Array.isArray(p.approvers) ? p.approvers : []
  const apNames = Array.isArray(p.approvers_names) ? p.approvers_names : []
  form.approvers = ap.length > 0 ? ap[0] : undefined
  form.approvers_name = apNames.length > 0 ? apNames[0] : ''
  form.time_limit_days = p.time_limit_days ?? undefined
  form.require_file = p.require_file ?? false
  form.require_assignee_signature = p.require_assignee_signature ?? true
  form.require_checker_signature = p.require_checker_signature ?? true
  form.require_approver_signature = p.require_approver_signature ?? true
  form.endorser_id = p.endorser_id ?? undefined
  form.endorser_name = p.endorser_name || ''
  form.require_endorser_signature = p.require_endorser_signature ?? true

  // 发起模式：读取节点上已保存的截止日期（初始值由 FlowDesigner 预填）
  form.plan_begin = p.plan_begin ?? undefined
  form.deadline = p.deadline ?? undefined
  if (!props.launchMode) {
    form.plan_begin = undefined
    form.deadline = undefined
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
    checkers: form.checkers != null ? [form.checkers] : null,
    checkers_names: form.checkers_name ? [form.checkers_name] : null,
    approvers: form.approvers != null ? [form.approvers] : null,
    approvers_names: form.approvers_name ? [form.approvers_name] : null,
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
    // 发起模式下保存截止日期，后续 handleLaunch 会收集为 node_override
    ...(props.launchMode ? { plan_begin: form.plan_begin, deadline: form.deadline } : {}),
  })
}

/** UserSelector 加载完成 —— 缓存用户名称映射 */
function handleOptionsLoaded(users: Array<{ id: number; real_name: string }>) {
  for (const u of users) {
    userNameCache[u.id] = u.real_name
  }
}

/** 负责人变更 —— 同步名称 + 写入节点（参数放宽以匹配 UserSelector 的 update:model-value 签名，仅 number 有效） */
function handleAssigneeChange(val: number | number[] | undefined) {
  form.assignee_name = typeof val === 'number' && val ? (userNameCache[val] || '') : ''
  syncToNode()
}

/** 校验人变更 —— 同步名称 + 写入节点 */
function handleCheckersChange(val: number | number[] | undefined) {
  form.checkers_name = typeof val === 'number' ? (userNameCache[val] || '') : ''
  syncToNode()
}

/** 审批人变更 —— 同步名称 + 写入节点 */
function handleApproversChange(val: number | number[] | undefined) {
  form.approvers_name = typeof val === 'number' ? (userNameCache[val] || '') : ''
  syncToNode()
}

/** 批准人变更 —— 同步名称 + 写入节点 */
function handleEndorserChange(val: number | number[] | undefined) {
  form.endorser_name = typeof val === 'number' && val ? (userNameCache[val] || '') : ''
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
  // 收集当前节点所有非空文件夹名
  const currentNames = new Set(folders.value.map(f => f.name.trim()).filter(Boolean))
  // 检查同一节点内重复
  if (currentNames.size < folders.value.filter(f => f.name.trim()).length) {
    return '当前节点内存在重复的文件夹名称'
  }
  return null
})

// ========== 工作日计算（跳过周末，节假日以后端为准） ==========

/** 判断是否周末 */
function isWeekend(date: Date): boolean {
  const d = date.getDay()
  return d === 0 || d === 6
}

/** 两个日期之间的工作日数（含首尾） */
function countBusinessDays(startStr: string, endStr: string): number {
  let count = 0
  const cur = new Date(startStr)
  const end = new Date(endStr)
  while (cur <= end) {
    if (!isWeekend(cur)) count++
    cur.setDate(cur.getDate() + 1)
  }
  return count
}

/** 从 start 起加 N 个工作日，返回结果日期 YYYY-MM-DD */
function addBusinessDays(startStr: string, days: number): string {
  const cur = new Date(startStr)
  let added = 0
  while (added < days) {
    cur.setDate(cur.getDate() + 1)
    if (!isWeekend(cur)) added++
  }
  return cur.toISOString().slice(0, 10)
}

// ========== 发起模式：截止日期变更 → 级联下游 ==========

function handleDeadlineChange(newDeadline: string | undefined) {
  if (!newDeadline || !props.lf || !props.launchMode) {
    syncToNode()
    return
  }

  const begin = form.plan_begin
  if (!begin) {
    syncToNode()
    return
  }

  // 反向计算当前节点的工作日数
  const newDays = countBusinessDays(begin, newDeadline)
  form.time_limit_days = Math.max(1, newDays)

  // 同步当前节点到 LogicFlow（含新 deadline 和 time_limit_days）
  syncToNode()

  // ── 级联更新下游节点 ──
  const allNodes = props.lf.getGraphData().nodes || []
  const workNodes = allNodes
    .filter((n: any) => {
      const p = n.properties || {}
      return !p.is_start && !p.is_end
    })
    .sort((a: any, b: any) => (a.properties?.sort_order ?? 0) - (b.properties?.sort_order ?? 0))

  const currentIdx = workNodes.findIndex((n: any) => String(n.id) === String(props.nodeData?.id))
  if (currentIdx < 0 || currentIdx >= workNodes.length - 1) return

  // 逐级推进：每个下游节点开始 = 前一个截止日 + 1 工作日
  let prevDeadline = newDeadline
  for (let i = currentIdx + 1; i < workNodes.length; i++) {
    const node = workNodes[i]
    const existingProps = node.properties || {}
    const limitDays = existingProps.time_limit_days || 1

    // 下游开始日 = 前一个截止日 + 1（跳过周末到下一个工作日）
    const nextStart = addBusinessDays(prevDeadline, 1)
    const nextDeadline = addBusinessDays(nextStart, limitDays)

    props.lf.setProperties(node.id, {
      ...existingProps,
      plan_begin: nextStart,
      deadline: nextDeadline,
    })

    prevDeadline = nextDeadline
  }

  // 如果当前选中的是下游节点，也需要更新面板表单
  ElMessage.success('截止日期已更新，下游节点已级联')
}

/** 是否配置了至少一个人员字段（显示"一键应用"按钮的条件） */
const hasPersonnelConfig = computed(() => {
  return !!(form.assignee_id || form.checkers != null || form.approvers != null || form.endorser_id)
})

/** 一键应用当前节点的人员配置到所有工作节点（排除开始/结束） */
function applyPersonnelToAllNodes() {
  if (!props.lf) return

  const allNodes = props.lf.getGraphData().nodes || []
  // 找到所有工作节点（排除开始/结束）
  const workNodes = allNodes.filter((n: any) => {
    const p = n.properties || {}
    return !p.is_start && !p.is_end
  })

  if (workNodes.length === 0) return

  // 更新所有工作节点的人员属性（合并到现有属性，不覆盖其他配置）
  for (const node of workNodes) {
    const existingProps = node.properties || {}
    props.lf.setProperties(node.id, {
      ...existingProps,  // 保留节点原有配置（名称、时限、签批等）
      assignee_id: form.assignee_id ?? null,
      assignee_name: form.assignee_name || null,
      checkers: form.checkers != null ? [form.checkers] : null,
      checkers_names: form.checkers_name ? [form.checkers_name] : null,
      approvers: form.approvers != null ? [form.approvers] : null,
      approvers_names: form.approvers_name ? [form.approvers_name] : null,
      endorser_id: form.endorser_id ?? null,
      endorser_name: form.endorser_name || null,
    })
  }

  ElMessage.success(`已应用到 ${workNodes.length} 个工作节点`)
}

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

/* 发起模式：计划开始只读行 */
.plan-begin-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: var(--el-fill-color-lighter);
  border-radius: 4px;
  font-size: 13px;

  .plan-begin-label { color: var(--el-text-color-secondary); flex-shrink: 0; }
  .plan-begin-value { font-weight: 600; color: var(--el-text-color-primary); }
}

/* 人员配置区头部 */
.personnel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  padding: 8px 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;

  &__title {
    font-size: 13px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }
}
</style>
