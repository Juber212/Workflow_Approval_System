<template>
  <!-- 终止确认弹窗 —— 危险操作二次确认（项目/方案共用） -->
  <el-dialog
    v-model="visible"
    :title="'⚠️ 永久终止并删除文件'"
    width="480px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    @close="$emit('close')"
  >
    <!-- 当前流程信息 -->
    <div class="term-info">
      <div class="term-info__row">
        <span class="term-info__label">{{ isProposal ? '方案' : '项目' }}</span>
        <span class="term-info__value">{{ instanceName }}</span>
      </div>
      <div class="term-info__row">
        <span class="term-info__label">当前状态</span>
        <span class="status-tag" :class="statusTagClass">{{ statusLabel }}</span>
      </div>
    </div>

    <!-- 终止原因 -->
    <div class="term-reason">
      <label class="term-reason__label">
        终止原因 <span class="required">*</span>
      </label>
      <el-input
        v-model="reason"
        type="textarea"
        :rows="4"
        placeholder="请填写终止原因（必填），将记入操作日志"
        maxlength="500"
        show-word-limit
      />
      <div class="field-hint" v-if="reason.trim().length === 0">
        终止原因不能为空
      </div>
    </div>

    <!-- 警告提示 -->
    <el-alert type="error" :closable="false" show-icon class="term-warn">
      <template #title>
        终止后不可恢复，流程文件将被永久删除，仅保留操作日志。该实例状态将变更为"已终止"，所有待办任务关闭。
      </template>
    </el-alert>

    <!-- 底部按钮 -->
    <template #footer>
      <el-button @click="visible = false" :disabled="submitting">取消</el-button>
      <el-button
        type="danger"
        :loading="submitting"
        :disabled="!canConfirm"
        @click="handleConfirm"
      >
        终止并删除
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/** 终止确认弹窗 —— 二次确认 + 终止原因必填 + 危险操作警告（项目/方案共用） */
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { terminateInstance } from '@/api/instance'

const props = defineProps<{
  modelValue: boolean
  instanceId: number
  instanceName: string
  instanceStatus: string
  isProposal?: boolean  // 是否为方案实例，用于区分标签文案
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  close: []
  terminated: []
}>()

// ========== 弹窗可见性 ==========
const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

// ========== 表单状态 ==========
const reason = ref('')
const submitting = ref(false)

const canConfirm = computed(() => reason.value.trim().length > 0 && !submitting.value)

// ========== 状态标签 ==========
const statusLabel = computed(() => {
  const s = (props.instanceStatus || '').toLowerCase()
  const map: Record<string, string> = {
    created: '已创建', running: '运行中', completed: '已完成', terminated: '已终止',
  }
  return map[s] || props.instanceStatus
})

const statusTagClass = computed(() => {
  const s = (props.instanceStatus || '').toLowerCase()
  const map: Record<string, string> = {
    created: 'status-tag--draft', running: 'status-tag--running',
    completed: 'status-tag--completed', terminated: 'status-tag--terminated',
  }
  return map[s] || ''
})

// ========== 确认终止 ==========
async function handleConfirm() {
  if (!canConfirm.value) return

  submitting.value = true
  try {
    await terminateInstance(props.instanceId, reason.value.trim())
    ElMessage.success('流程已终止')
    visible.value = false
    emit('terminated')
  } catch (err: any) {
    const msg = err?.response?.data?.message || err?.message || '终止失败'
    ElMessage.error(msg)
  } finally {
    submitting.value = false
  }
}
</script>

<style lang="scss" scoped>
// 流程信息
.term-info {
  background: var(--el-bg-color-page);
  border-radius: 6px;
  padding: 12px 16px;
  margin-bottom: 16px;

  &__row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 4px 0;

    &:first-child {
      padding-top: 0;
    }

    &:last-child {
      padding-bottom: 0;
    }
  }

  &__label {
    font-size: 13px;
    color: var(--el-text-color-secondary);
    width: 70px;
    flex-shrink: 0;
  }

  &__value {
    font-size: 14px;
    font-weight: 500;
    color: var(--el-text-color-primary);
  }
}

// 终止原因
.term-reason {
  margin-bottom: 16px;

  &__label {
    display: block;
    font-size: 14px;
    font-weight: 500;
    color: var(--el-text-color-primary);
    margin-bottom: 6px;
  }

  .required {
    color: var(--el-color-danger);
  }

  .field-hint {
    font-size: 12px;
    color: var(--el-color-danger);
    margin-top: 4px;
  }
}

// 警告
.term-warn {
  margin-top: 0;
  border-radius: 6px;
}
</style>
