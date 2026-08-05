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
            :disabled-date="disabledDeadlineDate"
            @change="handleDeadlineChange"
          />
          <div class="field-hint">
            预估 {{ form.time_limit_days ?? '?' }} 个工作日（不含起始日，调整截止日后下游已按法定节假日自动顺延）
          </div>
        </el-form-item>

        <el-divider content-position="left">高级设置</el-divider>

        <!-- 文件提交配置（P2-2 共享组件：文件夹增删改 + 模式切换） -->
        <FolderConfigEditor
          v-model:folders="folders"
          v-model:use-file-folders="useFileFolders"
          v-model:require-file="form.require_file"
          :name-conflict="folderNameConflict"
          @change="syncToNode"
          @mode-change="handleFolderModeToggle"
        />

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
import { InfoFilled, Setting } from '@element-plus/icons-vue'
import UserSelector from '@/components/UserSelector.vue'
import type { UserSearchItem } from '@/api/admin'
import type { FileFolderConfig } from '@/api/designer'
import { calculateDeadlines } from '@/api/instance'
import FolderConfigEditor from './FolderConfigEditor.vue'

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

/** 文件夹配置（v-model 给 FolderConfigEditor，展开/数量模式状态在组件内部） */
const folders = ref<FileFolderConfig[]>([])
/** 是否使用文件夹模式 */
const useFileFolders = ref(false)

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

  // 文件夹配置（数量模式由 FolderConfigEditor 内部按 file_count 推导）
  const rawFolders = p.file_folders
  if (rawFolders && Array.isArray(rawFolders) && rawFolders.length > 0) {
    useFileFolders.value = true
    folders.value = rawFolders.map((f: any) => ({
      name: f.name || '',
      required: f.required ?? false,
      file_count: f.file_count ?? null,
    }))
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

/** 文件夹模式切换 —— 清空旧文件夹列表并同步（require_file 联动与展开收起由 FolderConfigEditor 内部处理） */
function handleFolderModeToggle() {
  folders.value = []
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

/** 截止日期选择器禁用规则：禁止选择周末作为截止日（P1-39 补充，截止日对齐工作日语义；法定节假日由后端预填/级联自动跳过） */
function disabledDeadlineDate(date: Date): boolean {
  return isWeekend(date)
}

/** 从 start 的下一日到 end（含 end）的工作日数 —— 不含起始日，与后端 add_workdays(start, N) 口径一致（P1-39 消除 off-by-one） */
function countWorkdaysExcludingStart(startStr: string, endStr: string): number {
  let count = 0
  const cur = new Date(startStr)
  const end = new Date(endStr)
  cur.setDate(cur.getDate() + 1)  // 从起始日的下一天开始数
  while (cur <= end) {
    if (!isWeekend(cur)) count++
    cur.setDate(cur.getDate() + 1)
  }
  return count
}

// ========== 发起模式：截止日期变更 → 锚定当前节点 + 级联下游（P1-39 统一走后端 calculate-deadlines，节假日正确） ==========

async function handleDeadlineChange(newDeadline: string | undefined) {
  if (!newDeadline || !props.lf || !props.launchMode) {
    syncToNode()
    return
  }

  const begin = form.plan_begin
  if (!begin) {
    syncToNode()
    return
  }

  // 反向计算当前节点占用的工作日数（不含起始日，与后端 add_workdays 对齐）
  form.time_limit_days = Math.max(1, countWorkdaysExcludingStart(begin, newDeadline))

  // 同步当前节点到 LogicFlow（含新 deadline 和 time_limit_days）
  syncToNode()

  // ── 级联更新下游节点：当前节点截止日作锚点，后端链式顺延（跳过法定节假日）──
  const allNodes = props.lf.getGraphData().nodes || []
  const workNodes = allNodes
    .filter((n: any) => {
      const p = n.properties || {}
      return !p.is_start && !p.is_end
    })
    .sort((a: any, b: any) => (a.properties?.sort_order ?? 0) - (b.properties?.sort_order ?? 0))

  const currentIdx = workNodes.findIndex((n: any) => String(n.id) === String(props.nodeData?.id))
  // 已是最后一个工作节点 → 无下游可级联
  if (currentIdx < 0 || currentIdx >= workNodes.length - 1) return

  const downstream = workNodes.slice(currentIdx + 1)
  const currentDbId = Number(props.nodeData?.properties?.db_id ?? props.nodeData?.id)

  try {
    const results = await calculateDeadlines(begin, [
      // 锚点：当前节点截止日已锁定，后端从该日期起顺延下游
      { node_id: currentDbId, time_limit_days: null, deadline: newDeadline },
      ...downstream.map((n: any) => ({
        node_id: Number(n.properties?.db_id ?? n.id),
        time_limit_days: n.properties?.time_limit_days || 1,
      })),
    ])
    // 写回下游节点（results[0] 为锚点当前节点，从 1 开始）
    for (let i = 1; i < results.length; i++) {
      const r = results[i]
      const node = downstream[i - 1]
      if (!r.begin || !r.deadline) continue
      props.lf.setProperties(node.id, {
        ...(node.properties || {}),
        plan_begin: r.begin,
        deadline: r.deadline,
      })
    }
    ElMessage.success('截止日期已更新，下游节点已级联')
  } catch {
    // 拦截器已统一弹错（P1-35），无需重复提示
  }
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
