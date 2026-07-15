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
          style="width: 320px"
        />
      </div>

      <!-- 校验人（多选） -->
      <div class="personnel-edit__row">
        <label class="personnel-edit__label">校验人</label>
        <UserSelector
          :model-value="form.checker_ids"
          @update:model-value="(v: number | number[] | undefined) => form.checker_ids = (v as number[]) || []"
          :initial-options="checkerInitialOptions"
          :multiple="true"
          :placeholder="'选择校验人（可多选）'"
          style="width: 320px"
        />
      </div>

      <!-- 审批人（多选） -->
      <div class="personnel-edit__row">
        <label class="personnel-edit__label">审批人</label>
        <UserSelector
          :model-value="form.approver_ids"
          @update:model-value="(v: number | number[] | undefined) => form.approver_ids = (v as number[]) || []"
          :initial-options="approverInitialOptions"
          :multiple="true"
          :placeholder="'选择审批人（可多选）'"
          style="width: 320px"
        />
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
  checker_ids: number[]
  approver_ids: number[]
}>({
  assignee_id: undefined,
  checker_ids: [],
  approver_ids: [],
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
  if (!props.node?.checkers) return []
  return props.node.checkers.map(c => ({
    id: c.user_id,
    real_name: (c as any).user_name || '',
    username: '',
    organization_id: null,
    organization_name: null,
  }))
})

/** 审批人初始选项 —— 预填当前审批人姓名 */
const approverInitialOptions = computed<UserSearchItem[]>(() => {
  if (!props.node?.approvers) return []
  return props.node.approvers.map(a => ({
    id: a.user_id,
    real_name: (a as any).user_name || '',
    username: '',
    organization_id: null,
    organization_name: null,
  }))
})

// 弹窗打开时预填当前节点的人员配置
watch(() => props.modelValue, (val) => {
  if (val && props.node) {
    form.assignee_id = props.node.assignee_id ?? undefined
    form.checker_ids = (props.node.checkers || []).map(c => c.user_id).filter(Boolean)
    form.approver_ids = (props.node.approvers || []).map(a => a.user_id).filter(Boolean)
  }
})

/** 提交换人请求 */
async function handleSave() {
  submitting.value = true
  try {
    const data: any = {}

    // 只传有变化的字段
    if (props.node) {
      const oldCheckerIds = (props.node.checkers || []).map(c => c.user_id).filter(Boolean).sort()
      const newCheckerIds = [...form.checker_ids].sort()
      if (JSON.stringify(oldCheckerIds) !== JSON.stringify(newCheckerIds)) {
        data.checkers = form.checker_ids.map(id => ({ user_id: id }))
      }

      const oldApproverIds = (props.node.approvers || []).map(a => a.user_id).filter(Boolean).sort()
      const newApproverIds = [...form.approver_ids].sort()
      if (JSON.stringify(oldApproverIds) !== JSON.stringify(newApproverIds)) {
        data.approvers = form.approver_ids.map(id => ({ user_id: id }))
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
    ElMessage.success(`人员修改成功：${result.changes.join('；')}`)
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
}
</style>
