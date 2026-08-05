<template>
  <el-dialog
    v-model="visible"
    title="重置密码"
    width="420px"
    :close-on-click-modal="false"
    @closed="handleClosed"
  >
    <p class="reset-tip">
      正在为用户 <strong>{{ username }}</strong> 重置密码
    </p>
    <p class="reset-desc">
      密码将恢复为系统默认初始密码，用户下次登录时需要修改密码。
    </p>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">确认重置</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/** 重置密码弹窗 —— 恢复为默认初始密码，无需手动输入 */
import { ref, watch } from 'vue'

const props = defineProps<{
  modelValue: boolean
  username: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: []
}>()

const visible = ref(props.modelValue)
watch(() => props.modelValue, (v) => { visible.value = v })
watch(visible, (v) => { emit('update:modelValue', v) })

const submitting = ref(false)

async function handleSubmit() {
  submitting.value = true
  try {
    // M22：不自行关闭——由父组件提交成功后关闭 v-model（失败时保留弹窗）
    emit('submit')
  } finally {
    submitting.value = false
  }
}

function handleClosed() {
  // 无需清理
}
</script>

<style lang="scss" scoped>
.reset-tip {
  margin-bottom: 8px;
  font-size: 14px;
  color: var(--el-text-color-regular);
}
.reset-desc {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 0;
}
</style>
