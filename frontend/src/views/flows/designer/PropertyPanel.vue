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
        <el-tag size="small" :type="isConfigured ? 'success' : 'warning'">
          {{ isConfigured ? '已配置' : '未配置' }}
        </el-tag>
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
            @update:model-value="handleApproversChange"
            @options-loaded="handleOptionsLoaded"
          />
        </el-form-item>

        <!-- 完成时限 -->
        <el-form-item
          label="完成时限（天）"
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

        <el-divider content-position="left">高级设置</el-divider>

        <!-- 是否必须上传文件 -->
        <el-form-item label="文件上传">
          <el-switch
            v-model="form.require_file"
            active-text="必须上传"
            inactive-text="可不上传"
            @change="syncToNode"
          />
        </el-form-item>

      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { InfoFilled, Setting } from '@element-plus/icons-vue'
import UserSelector from '@/components/UserSelector.vue'
import type { UserSearchItem } from '@/api/admin'

/** Props */
const props = defineProps<{
  /** LogicFlow 实例（用于读写节点属性） */
  lf?: any
  /** 当前选中节点的 LogicFlow 数据 */
  nodeData?: any
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
  require_file: false,
})

/** 用户名称缓存 —— 从 UserSelector options-loaded 事件积累 */
const userNameCache = reactive<Record<number, string>>({})

/** 是否系统节点（开始/结束） */
const isSystemNode = computed(() => {
  if (!props.nodeData) return false
  return props.nodeData.properties?.is_start || props.nodeData.properties?.is_end
})

/** 简要判断节点是否已配置（必填字段均填写） */
const isConfigured = computed(() => {
  return !!(
    form.name &&
    form.assignee_id &&
    form.checkers.length > 0 &&
    form.approvers.length > 0 &&
    form.time_limit_days &&
    form.time_limit_days >= 1
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
</style>
