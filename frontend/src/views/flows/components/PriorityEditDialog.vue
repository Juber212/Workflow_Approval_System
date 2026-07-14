<template>
  <!-- 优先级修改弹窗 -->
  <el-dialog
    v-model="visible"
    title="修改优先级"
    width="380px"
    :close-on-click-modal="false"
    @close="$emit('close')"
  >
    <div class="pri-edit">
      <div class="pri-edit__info">
        <span class="pri-edit__label">当前优先级</span>
        <span class="priority-badge" :class="'priority--' + currentPriority">
          {{ priorityLabel(currentPriority) }}
        </span>
      </div>
      <div class="pri-edit__select">
        <label class="pri-edit__label">新优先级</label>
        <el-select v-model="newPriority" style="width: 100%" :disabled="submitting">
          <el-option
            v-for="opt in priorityOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
      </div>
    </div>

    <template #footer>
      <el-button @click="visible = false" :disabled="submitting">取消</el-button>
      <el-button
        type="primary"
        :loading="submitting"
        :disabled="newPriority === currentPriority"
        @click="handleConfirm"
      >
        确认修改
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/** 优先级修改弹窗 —— 下拉选择 + 确认 */
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { changePriority } from '@/api/instance'

const props = defineProps<{
  modelValue: boolean
  instanceId: number
  currentPriority: string
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  close: []
  changed: []
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const newPriority = ref(props.currentPriority)
const submitting = ref(false)

const priorityOptions = [
  { label: '🔴 紧急', value: 'urgent' },
  { label: '🟠 高', value: 'high' },
  { label: '🔵 普通', value: 'normal' },
  { label: '🟢 低', value: 'low' },
]

function priorityLabel(val: string): string {
  const map: Record<string, string> = { urgent: '紧急', high: '高', normal: '普通', low: '低' }
  return map[val] || val
}

async function handleConfirm() {
  if (newPriority.value === props.currentPriority) return

  submitting.value = true
  try {
    await changePriority(props.instanceId, newPriority.value)
    ElMessage.success('优先级已修改')
    visible.value = false
    emit('changed')
  } catch (err: any) {
    const msg = err?.response?.data?.message || err?.message || '修改失败'
    ElMessage.error(msg)
  } finally {
    submitting.value = false
  }
}
</script>

<style lang="scss" scoped>
.pri-edit {
  &__info {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 16px;
  }

  &__label {
    font-size: 14px;
    color: var(--el-text-color-secondary);
    width: 80px;
  }

  &__select {
    display: flex;
    align-items: center;
    gap: 10px;
  }
}

.priority-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;

  &.priority--urgent { color: #fff; background: var(--el-color-danger); }
  &.priority--high   { color: var(--el-color-warning); background: var(--el-color-warning-light-9); }
  &.priority--normal { color: var(--el-text-color-secondary); background: var(--el-fill-color); }
  &.priority--low    { color: var(--el-color-info); background: var(--el-color-info-light-9); }
}
</style>
