<template>
  <el-dialog
    v-model="visible"
    :title="isEdit ? '编辑组织' : '新增组织'"
    width="460px"
    :close-on-click-modal="false"
    @closed="handleClosed"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="80px" @keyup.enter="handleSubmit">
      <el-form-item label="组织名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入组织名称" maxlength="50" />
      </el-form-item>
      <el-form-item label="描述" prop="description">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="3"
          placeholder="选填"
          maxlength="500"
          show-word-limit
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'

const props = defineProps<{
  modelValue: boolean
  isEdit: boolean
  initialData?: { name: string; description: string | null } | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [data: { name: string; description: string | null }]
}>()

const visible = ref(props.modelValue)
watch(() => props.modelValue, (v) => { visible.value = v })
watch(visible, (v) => { emit('update:modelValue', v) })

const formRef = ref<FormInstance>()
const submitting = ref(false)

const form = reactive({ name: '', description: '' as string | null })

const rules: FormRules = {
  name: [{ required: true, message: '请输入组织名称', trigger: 'blur' }],
}

watch(visible, (val) => {
  if (val && props.initialData) {
    form.name = props.initialData.name
    form.description = props.initialData.description
  } else if (val) {
    form.name = ''
    form.description = ''
  }
})

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    emit('submit', { name: form.name, description: form.description || null })
    visible.value = false
  } finally {
    submitting.value = false
  }
}

function handleClosed() {
  formRef.value?.resetFields()
}
</script>
