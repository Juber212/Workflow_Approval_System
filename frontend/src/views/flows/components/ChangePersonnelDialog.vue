<template>
  <!-- 紧急换人弹窗 —— 修改节点的负责人/校验人/审批人 -->
  <el-dialog
    v-model="visible"
    title="修改人员"
    width="480px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <div class="personnel-edit" v-loading="submitting">
      <!-- 节点名称 -->
      <div class="personnel-edit__node-info">
        <span class="personnel-edit__label">节点</span>
        <span class="personnel-edit__node-name">{{ node?.name }}</span>
      </div>

      <!-- 负责人（单选） -->
      <div class="personnel-edit__row">
        <label class="personnel-edit__label">负责人</label>
        <UserSelector
          :model-value="form.assignee_id"
          @update:model-value="(v: number | number[] | undefined) => form.assignee_id = v as number | undefined"
          :initial-options="assigneeInitialOptions"
          :placeholder="'选择负责人'"
          org-members
          :disabled="assigneeLocked"
          style="width: 320px"
        />
        <span v-if="assigneeLocked" class="personnel-edit__lock-tip">负责人已提交，不可更换</span>
      </div>

      <!-- 校验人 -->
      <div class="personnel-edit__row">
        <label class="personnel-edit__label">校验人</label>
        <UserSelector
          :model-value="form.checker_id"
          @update:model-value="(v: number | number[] | undefined) => form.checker_id = v as number | undefined"
          :initial-options="checkerInitialOptions"
          :multiple="false"
          :placeholder="'选择校验人'"
          org-members
          :disabled="checkerLocked"
          style="width: 320px"
        />
        <span v-if="checkerLocked" class="personnel-edit__lock-tip">校验已完成，不可更换</span>
      </div>

      <!-- 审批人 -->
      <div class="personnel-edit__row">
        <label class="personnel-edit__label">审批人</label>
        <UserSelector
          :model-value="form.approver_id"
          @update:model-value="(v: number | number[] | undefined) => form.approver_id = v as number | undefined"
          :initial-options="approverInitialOptions"
          :multiple="false"
          :placeholder="'选择审批人'"
          org-members
          :disabled="approverLocked"
          style="width: 320px"
        />
        <span v-if="approverLocked" class="personnel-edit__lock-tip">审批已完成，不可更换</span>
      </div>
    </div>

    <template #footer>
      <el-button @click="visible = false" :disabled="submitting">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSave">
        确认修改
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/** 紧急换人弹窗 —— 修改运行中节点的负责人/校验人/审批人，未传的字段保持原值 */
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { changePersonnel } from '@/api/instance'
import type { DetailNodeInfo } from '@/api/instance'
import type { UserSearchItem } from '@/api/admin'
import UserSelector from '@/components/UserSelector.vue'

const props = defineProps<{
  modelValue: boolean
  instanceId: number
  node: DetailNodeInfo | null
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  success: []
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const submitting = ref(false)

/** 表单数据：只传有修改的字段，null/undefined 表示不修改 */
const form = reactive<{
  assignee_id: number | undefined
  checker_id: number | undefined
  approver_id: number | undefined
}>({
  assignee_id: undefined,
  checker_id: undefined,
  approver_id: undefined,
})

/** 负责人是否已提交（节点进入等待校验/审批/批准）→ 不可更换负责人 */
const assigneeLocked = computed(() => {
  const st = (props.node?.status || '').toLowerCase()
  return ['waiting_check', 'waiting_approval', 'waiting_endorsement'].includes(st)
})

/** 校验人是否已通过（节点进入等待审批/批准）→ 不可更换校验人 */
const checkerLocked = computed(() => {
  const st = (props.node?.status || '').toLowerCase()
  return ['waiting_approval', 'waiting_endorsement'].includes(st)
})

/** 审批人是否已通过（节点进入等待批准）→ 不可更换审批人 */
const approverLocked = computed(() => {
  const st = (props.node?.status || '').toLowerCase()
  return ['waiting_endorsement'].includes(st)
})

/** 负责人初始选项 —— 预填当前负责人姓名，避免 UserSelector 远程模式显示裸 ID */
const assigneeInitialOptions = computed<UserSearchItem[]>(() => {
  if (!props.node?.assignee_id) return []
  return [{
    id: props.node.assignee_id,
    real_name: props.node.assignee_name || '',
    username: '',
    organization_id: null,
    organization_name: null,
  }]
})

/** 校验人初始选项 —— 预填当前校验人姓名 */
const checkerInitialOptions = computed<UserSearchItem[]>(() => {
  if (!props.node?.checkers?.length) return []
  const c = props.node.checkers[0]
  return [{ id: c.user_id, real_name: (c as any).user_name || '', username: '', organization_id: null, organization_name: null }]
})

/** 审批人初始选项 —— 预填当前审批人姓名 */
const approverInitialOptions = computed<UserSearchItem[]>(() => {
  if (!props.node?.approvers?.length) return []
  const a = props.node.approvers[0]
  return [{ id: a.user_id, real_name: (a as any).user_name || '', username: '', organization_id: null, organization_name: null }]
})

// 弹窗打开时预填当前节点的人员配置
watch(() => props.modelValue, (val) => {
  if (val && props.node) {
    form.assignee_id = props.node.assignee_id ?? undefined
    form.checker_id = (props.node.checkers || []).map(c => c.user_id).filter(Boolean)[0] ?? undefined
    form.approver_id = (props.node.approvers || []).map(a => a.user_id).filter(Boolean)[0] ?? undefined
  }
})

/** 提交换人请求 */
async function handleSave() {
  submitting.value = true
  try {
    const data: any = {}

    // 只传有变化的字段
    if (props.node) {
      const oldCheckerIds = (props.node.checkers || []).map(c => c.user_id).filter(Boolean)
      const newCheckerId = form.checker_id
      if (JSON.stringify(oldCheckerIds) !== JSON.stringify(newCheckerId != null ? [newCheckerId] : [])) {
        data.checkers = newCheckerId != null ? [{ user_id: newCheckerId }] : []
      }

      const oldApproverIds = (props.node.approvers || []).map(a => a.user_id).filter(Boolean)
      const newApproverId = form.approver_id
      if (JSON.stringify(oldApproverIds) !== JSON.stringify(newApproverId != null ? [newApproverId] : [])) {
        data.approvers = newApproverId != null ? [{ user_id: newApproverId }] : []
      }

      if ((form.assignee_id ?? null) !== (props.node.assignee_id ?? null)) {
        data.assignee_id = form.assignee_id ?? null
      }
    }

    // 无变更时提示
    if (Object.keys(data).length === 0) {
      ElMessage.info('未检测到人员变更')
      return
    }

    const result = await changePersonnel(props.instanceId, props.node!.id, data)
    ElMessage.success(`人员修改成功：${result.changes?.join('；') ?? '已修改'}`)
    visible.value = false
    emit('success')
  } catch (err: any) {
    const msg = err?.response?.data?.message || err?.message || '修改失败'
    ElMessage.error(msg)
  } finally {
    submitting.value = false
  }
}

function handleClose() {
  // 关闭时重置表单
}
</script>

<style lang="scss" scoped>
.personnel-edit {
  &__node-info {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 18px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--el-border-color-lighter);
  }

  &__node-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }

  &__row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 14px;

    &:last-child {
      margin-bottom: 0;
    }
  }

  &__label {
    font-size: 14px;
    color: var(--el-text-color-secondary);
    width: 60px;
    flex-shrink: 0;
  }

  &__lock-tip {
    font-size: 12px;
    color: var(--el-color-warning);
    white-space: nowrap;
  }
}
</style>
