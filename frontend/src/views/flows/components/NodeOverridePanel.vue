<template>
  <div class="node-override-panel">
    <h4 class="panel-title">
      节点配置调整
      <span class="panel-hint">（可选，未调整的节点使用模板默认配置）</span>
    </h4>

    <el-collapse v-if="workNodes.length > 0" v-model="activeNames" accordion>
      <el-collapse-item
        v-for="node in workNodes"
        :key="node.id"
        :name="String(node.id)"
      >
        <template #title>
          <div class="node-collapse-title">
            <span class="node-name">{{ node.name }}</span>
            <span class="node-summary">{{ getNodeSummary(node) }}</span>
            <el-tag
              v-if="getNodeIssues(node).length > 0"
              size="small"
              type="danger"
              effect="plain"
              class="node-issue-tag"
            >
              {{ getNodeIssues(node).length }} 项问题
            </el-tag>
          </div>
        </template>

        <div class="node-override-form">
          <!-- 负责人 -->
          <div class="override-row">
            <label class="override-label">负责人</label>
            <UserSelector
              :model-value="getOverride(node.id, 'assignee_id') ?? node.assignee_id"
              @update:model-value="(v: number | number[] | undefined) => setOverride(node.id, 'assignee_id', v as number | undefined)"
              :placeholder="'选择负责人'"
              org-members
              style="width: 280px"
              @options-loaded="(users: any[]) => cacheNames(users)"
            />
          </div>

          <!-- 校验人 -->
          <div class="override-row">
            <label class="override-label">校验人</label>
            <div>
              <UserSelector
                :model-value="getOverride(node.id, 'checkers_ids')?.[0] ?? getCheckerId(node)"
                @update:model-value="(v: number | number[] | undefined) => setOverride(node.id, 'checkers_ids', typeof v === 'number' ? [v] : undefined)"
                :multiple="false"
                :placeholder="'选择校验人'"
                org-members
                style="width: 280px"
                @options-loaded="(users: any[]) => cacheNames(users)"
              />
              <p class="override-warn" v-if="isFieldEmpty(node, 'checkers')">
                ⚠ 请选择校验人
              </p>
            </div>
          </div>

          <!-- 审批人 -->
          <div class="override-row">
            <label class="override-label">审批人</label>
            <div>
              <UserSelector
                :model-value="getOverride(node.id, 'approvers_ids')?.[0] ?? getApproverId(node)"
                @update:model-value="(v: number | number[] | undefined) => setOverride(node.id, 'approvers_ids', typeof v === 'number' ? [v] : undefined)"
                :multiple="false"
                :placeholder="'选择审批人'"
                org-members
                style="width: 280px"
                @options-loaded="(users: any[]) => cacheNames(users)"
              />
              <p class="override-warn" v-if="isFieldEmpty(node, 'approvers')">
                ⚠ 请选择审批人
              </p>
            </div>
          </div>

          <!-- 截止日期 -->
          <div class="override-row">
            <label class="override-label">截止日期</label>
            <div>
              <el-date-picker
                :model-value="getOverride(node.id, 'deadline') ?? ''"
                @update:model-value="(v: any) => handleDeadlineChange(node.id, v)"
                type="date"
                placeholder="默认：发起日期 + {{ node.time_limit_days ?? '无' }} 工作日（跳过节假日）"
                value-format="YYYY-MM-DD"
                style="width: 280px"
              />
              <p v-if="isWeekend(getOverride(node.id, 'deadline'))" class="override-warn">
                ⚠ 所选日期为周末，提交时服务端将自动调整为最近的工作日（含法定节假日校验）
              </p>
            </div>
          </div>

          <!-- 签批配置（三个独立开关） -->
          <div class="override-row">
            <label class="override-label">签批配置</label>
            <div class="sig-switches">
              <el-checkbox
                :model-value="getOverride(node.id, 'require_assignee_signature') ?? node.require_assignee_signature ?? true"
                @update:model-value="(v: boolean) => setOverride(node.id, 'require_assignee_signature', v)"
              >负责人签名</el-checkbox>
              <el-checkbox
                :model-value="getOverride(node.id, 'require_checker_signature') ?? node.require_checker_signature ?? true"
                @update:model-value="(v: boolean) => setOverride(node.id, 'require_checker_signature', v)"
              >校验人签名</el-checkbox>
              <el-checkbox
                :model-value="getOverride(node.id, 'require_approver_signature') ?? node.require_approver_signature ?? true"
                @update:model-value="(v: boolean) => setOverride(node.id, 'require_approver_signature', v)"
              >审批人签名</el-checkbox>
            </div>
          </div>

          <!-- 重置按钮 -->
          <div class="override-row">
            <el-button text type="warning" size="small" @click="resetNode(node.id)">
              恢复默认配置
            </el-button>
          </div>
        </div>
      </el-collapse-item>
    </el-collapse>

    <el-empty v-else description="该模板无工作节点" :image-size="60" />
  </div>
</template>

<script setup lang="ts">
/** 节点覆盖配置面板 —— 逐节点调整负责人/校验人/审批人/截止日期 */
import { ref, computed } from 'vue'
import type { TemplateNodeItem } from '@/api/template'
import type { UserSearchItem } from '@/api/admin'
import UserSelector from '@/components/UserSelector.vue'

// ========== Props & Emits ==========
const props = defineProps<{
  /** 工作节点列表（不含开始/结束） */
  nodes: TemplateNodeItem[]
  /** 当前覆盖配置 */
  overrides: Record<number, Record<string, any>>
}>()

const emit = defineEmits<{
  'update:overrides': [overrides: Record<number, Record<string, any>>]
}>()

// ========== 状态 ==========
const activeNames = ref<string[]>([])  // 折叠面板当前展开项
const userNameCache = ref<Record<number, string>>({})  // 用户名缓存

// 只显示工作节点（排除开始/结束）
const workNodes = computed(() =>
  props.nodes.filter(n => !n.is_start && !n.is_end)
)

// ========== 辅助函数 ==========

/** 获取节点默认校验人ID（第一个） */
function getCheckerId(node: TemplateNodeItem): number | undefined {
  const ids = getCheckerIds(node)
  return ids.length > 0 ? ids[0] : undefined
}

/** 获取节点默认审批人ID（第一个） */
function getApproverId(node: TemplateNodeItem): number | undefined {
  const ids = getApproverIds(node)
  return ids.length > 0 ? ids[0] : undefined
}

/** 获取节点默认校验人ID列表（保留兼容性） */
function getCheckerIds(node: TemplateNodeItem): number[] {
  const checkers = node.checkers
  if (Array.isArray(checkers)) return checkers.map((c: any) => c.user_id ?? c.id ?? c)
  return []
}

/** 获取节点默认审批人ID列表（保留兼容性） */
function getApproverIds(node: TemplateNodeItem): number[] {
  const approvers = node.approvers
  if (Array.isArray(approvers)) return approvers.map((a: any) => a.user_id ?? a.id ?? a)
  return []
}

/** 获取覆盖值 */
function getOverride(nodeId: number, key: string): any {
  return props.overrides[nodeId]?.[key]
}

/** 设置覆盖值 */
function setOverride(nodeId: number, key: string, value: any) {
  const newOverrides = { ...props.overrides }
  if (!newOverrides[nodeId]) newOverrides[nodeId] = {}

  if (value === undefined || value === null || (Array.isArray(value) && value.length === 0)) {
    delete newOverrides[nodeId][key]
    if (Object.keys(newOverrides[nodeId]).length === 0) {
      delete newOverrides[nodeId]
    }
  } else {
    newOverrides[nodeId][key] = value
  }

  emit('update:overrides', newOverrides)
}

/** 重置单个节点 */
function resetNode(nodeId: number) {
  const newOverrides = { ...props.overrides }
  delete newOverrides[nodeId]
  emit('update:overrides', newOverrides)
}

/** 判断给定日期字符串是否为周末（周六或周日） */
function isWeekend(dateStr: string | undefined): boolean {
  if (!dateStr) return false
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return false
  const day = d.getDay()
  return day === 0 || day === 6
}

/** 截止日期选择变更处理 —— 用户手动选择日期后设置覆盖值 */
function handleDeadlineChange(nodeId: number, value: any) {
  setOverride(nodeId, 'deadline', value || undefined)
}

/** 缓存用户名 */
function cacheNames(users: UserSearchItem[]) {
  users.forEach(u => { userNameCache.value[u.id] = u.real_name })
}

/** 获取节点摘要（显示在折叠标题） */
function getNodeSummary(node: TemplateNodeItem): string {
  const parts: string[] = []
  const aId = getOverride(node.id, 'assignee_id') ?? node.assignee_id
  if (aId && userNameCache.value[aId as number]) {
    parts.push(userNameCache.value[aId as number])
  }
  const checkerIds = getOverride(node.id, 'checkers_ids') ?? getCheckerIds(node)
  if (checkerIds && checkerIds.length > 0) {
    const cName = userNameCache.value[checkerIds[0] as number]
    parts.push(cName ? `${cName}（校验）` : `1位校验人`)
  }
  const approverIds = getOverride(node.id, 'approvers_ids') ?? getApproverIds(node)
  if (approverIds && approverIds.length > 0) {
    const aName = userNameCache.value[approverIds[0] as number]
    parts.push(aName ? `${aName}（审批）` : `1位审批人`)
  }
  return parts.join(' · ') || '未配置'
}

// ========== 校验逻辑 ==========

/** 检查节点某个字段是否为空（覆盖后） */
function isFieldEmpty(node: TemplateNodeItem, field: 'checkers' | 'approvers'): boolean {
  if (field === 'checkers') {
    const overrideVal = getOverride(node.id, 'checkers_ids')
    if (overrideVal !== undefined) return !overrideVal || overrideVal.length === 0
    // 未被覆盖，检查模板默认值
    return getCheckerIds(node).length === 0
  }

  if (field === 'approvers') {
    const overrideVal = getOverride(node.id, 'approvers_ids')
    if (overrideVal !== undefined) return !overrideVal || overrideVal.length === 0
    return getApproverIds(node).length === 0
  }

  return false
}

/** 获取节点配置问题列表 */
function getNodeIssues(node: TemplateNodeItem): string[] {
  const issues: string[] = []
  if (isFieldEmpty(node, 'checkers')) issues.push('校验人未设置')
  if (isFieldEmpty(node, 'approvers')) issues.push('审批人未设置')

  return issues
}

/** 对外暴露：校验全部节点配置，返回问题列表 */
function validate(): { nodeId: number; nodeName: string; issues: string[] }[] {
  const errors: { nodeId: number; nodeName: string; issues: string[] }[] = []
  for (const node of workNodes.value) {
    const issues = getNodeIssues(node)
    if (issues.length > 0) {
      errors.push({ nodeId: node.id, nodeName: node.name, issues })
      // 自动展开有问题的节点
      if (!activeNames.value.includes(String(node.id))) {
        activeNames.value = [String(node.id), ...activeNames.value]
      }
    }
  }
  return errors
}

/** 检查是否有任何校验问题 */
function hasIssues(): boolean {
  return workNodes.value.some(n => getNodeIssues(n).length > 0)
}

// 对外暴露校验方法
defineExpose({ validate, hasIssues })
</script>

<script lang="ts">
// 仅用于注册组件名，computed 已在 <script setup> 中导入，避免重复声明
export default { name: 'NodeOverridePanel' }
</script>

<style lang="scss" scoped>
.node-override-panel {
  margin-top: 16px;

  .panel-title {
    font-size: 15px;
    font-weight: 600;
    color: var(--el-text-color-primary);
    margin-bottom: 12px;

    .panel-hint {
      font-size: 12px;
      font-weight: 400;
      color: var(--el-text-color-secondary);
    }
  }

  .node-collapse-title {
    display: flex;
    align-items: center;
    gap: 12px;
    width: 100%;

    .node-name {
      font-weight: 600;
      font-size: 14px;
      min-width: 80px;
    }

    .node-summary {
      font-size: 12px;
      color: var(--el-text-color-secondary);
    }
  }

  .node-override-form {
    padding: 8px 0;

    .override-row {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 14px;

      .override-label {
        min-width: 72px;
        line-height: 32px;
        font-size: 13px;
        color: var(--el-text-color-regular);
        display: flex;
        align-items: center;
        gap: 6px;

        .label-text {
          font-size: 13px;
        }
      }

      .override-desc {
        font-size: 12px;
        color: var(--el-color-warning);
        line-height: 32px;
      }
    }

    .override-warn {
      font-size: 12px;
      color: var(--el-color-danger);
      margin: 4px 0 0 0;
      line-height: 1.4;
    }

    .sig-switches {
      display: flex;
      flex-direction: column;
      gap: 6px;
      line-height: 32px;
    }
  }

  .node-issue-tag {
    margin-left: auto;
    flex-shrink: 0;
  }
}
</style>
