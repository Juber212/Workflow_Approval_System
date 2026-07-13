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
          </div>
        </template>

        <div class="node-override-form">
          <!-- 跳过开关（仅可选节点） -->
          <div v-if="node.is_optional" class="override-row">
            <label class="override-label">
              <el-switch
                :model-value="isNodeSkipped(node.id)"
                @update:model-value="(v: boolean) => setSkip(node.id, node.is_optional, v)"
                size="small"
              />
              <span class="label-text">跳过此节点</span>
            </label>
            <span class="override-desc" v-if="isNodeSkipped(node.id)">
              跳过后将不生成任务，直接进入下一节点
            </span>
          </div>

          <!-- 负责人 -->
          <div class="override-row" v-if="!isNodeSkipped(node.id)">
            <label class="override-label">负责人</label>
            <UserSelector
              :model-value="getOverride(node.id, 'assignee_id') ?? node.assignee_id"
              @update:model-value="(v: number | number[] | undefined) => setOverride(node.id, 'assignee_id', v as number | undefined)"
              :placeholder="'选择负责人'"
              style="width: 280px"
              @options-loaded="(users: any[]) => cacheNames(users)"
            />
          </div>

          <!-- 校验人 -->
          <div class="override-row" v-if="!isNodeSkipped(node.id)">
            <label class="override-label">校验人</label>
            <UserSelector
              :model-value="getOverride(node.id, 'checkers_ids') ?? getCheckerIds(node)"
              @update:model-value="(v: number | number[] | undefined) => setOverride(node.id, 'checkers_ids', v as number[] | undefined)"
              :multiple="true"
              :placeholder="'选择校验人（可多选）'"
              style="width: 400px"
              @options-loaded="(users: any[]) => cacheNames(users)"
            />
          </div>

          <!-- 审批人 -->
          <div class="override-row" v-if="!isNodeSkipped(node.id)">
            <label class="override-label">审批人</label>
            <UserSelector
              :model-value="getOverride(node.id, 'approvers_ids') ?? getApproverIds(node)"
              @update:model-value="(v: number | number[] | undefined) => setOverride(node.id, 'approvers_ids', v as number[] | undefined)"
              :multiple="true"
              :placeholder="'选择审批人（可多选）'"
              style="width: 400px"
              @options-loaded="(users: any[]) => cacheNames(users)"
            />
          </div>

          <!-- 截止日期 -->
          <div class="override-row" v-if="!isNodeSkipped(node.id)">
            <label class="override-label">截止日期</label>
            <el-date-picker
              :model-value="getOverride(node.id, 'deadline') ?? ''"
              @update:model-value="(v: any) => setOverride(node.id, 'deadline', v || undefined)"
              type="date"
              placeholder="默认：发起日期 + {{ node.time_limit_days ?? '无' }} 天"
              value-format="YYYY-MM-DD"
              style="width: 280px"
            />
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
/** 节点覆盖配置面板 —— 逐节点调整负责人/校验人/审批人/截止日期/跳过 */
import { ref } from 'vue'
import type { TemplateNodeItem } from '@/api/template'
import { searchUsers, type UserSearchItem } from '@/api/admin'
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

/** 获取节点默认校验人ID列表 */
function getCheckerIds(node: TemplateNodeItem): number[] {
  const checkers = node.checkers
  if (Array.isArray(checkers)) return checkers.map((c: any) => c.user_id ?? c.id ?? c)
  return []
}

/** 获取节点默认审批人ID列表 */
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

/** 是否跳过 */
function isNodeSkipped(nodeId: number): boolean {
  return !!props.overrides[nodeId]?.skip
}

/** 设置跳过 */
function setSkip(nodeId: number, isOptional: boolean, skip: boolean) {
  if (skip && !isOptional) return  // 安全兜底
  const newOverrides = { ...props.overrides }
  if (skip) {
    if (!newOverrides[nodeId]) newOverrides[nodeId] = {}
    newOverrides[nodeId].skip = true
    // 跳过时清除其他覆盖
    delete newOverrides[nodeId].assignee_id
    delete newOverrides[nodeId].checkers_ids
    delete newOverrides[nodeId].approvers_ids
    delete newOverrides[nodeId].deadline
  } else {
    if (newOverrides[nodeId]) {
      delete newOverrides[nodeId].skip
      if (Object.keys(newOverrides[nodeId]).length === 0) {
        delete newOverrides[nodeId]
      }
    }
  }
  emit('update:overrides', newOverrides)
}

/** 重置单个节点 */
function resetNode(nodeId: number) {
  const newOverrides = { ...props.overrides }
  delete newOverrides[nodeId]
  emit('update:overrides', newOverrides)
}

/** 缓存用户名 */
function cacheNames(users: UserSearchItem[]) {
  users.forEach(u => { userNameCache.value[u.id] = u.real_name })
}

/** 获取节点摘要（显示在折叠标题） */
function getNodeSummary(node: TemplateNodeItem): string {
  if (isNodeSkipped(node.id)) return '⏭ 已跳过'
  const parts: string[] = []
  const aId = getOverride(node.id, 'assignee_id') ?? node.assignee_id
  if (aId && userNameCache.value[aId as number]) {
    parts.push(userNameCache.value[aId as number])
  }
  const checkerIds = getOverride(node.id, 'checkers_ids') ?? getCheckerIds(node)
  if (checkerIds && checkerIds.length > 0) parts.push(`${checkerIds.length}位校验人`)
  const approverIds = getOverride(node.id, 'approvers_ids') ?? getApproverIds(node)
  if (approverIds && approverIds.length > 0) parts.push(`${approverIds.length}位审批人`)
  return parts.join(' · ') || '未配置'
}
</script>

<script lang="ts">
import { computed } from 'vue'
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
  }
}
</style>
