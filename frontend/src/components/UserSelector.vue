<template>
  <el-select
    v-model="selected"
    :multiple="multiple"
    :placeholder="placeholder"
    :disabled="disabled"
    filterable
    remote
    :remote-method="handleSearch"
    :loading="loading"
    :clearable="clearable"
    style="width: 100%"
    @change="handleChange"
  >
    <el-option
      v-for="user in options"
      :key="user.id"
      :label="`${user.real_name} (${user.username})`"
      :value="user.id"
    >
      <span>{{ user.real_name }}</span>
      <span class="user-option-org">{{ user.organization_name }}</span>
    </el-option>
  </el-select>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { searchUsers, type UserSearchItem } from '@/api/admin'

/** Props */
const props = withDefaults(defineProps<{
  modelValue?: number | number[]
  multiple?: boolean
  placeholder?: string
  disabled?: boolean
  clearable?: boolean
}>(), {
  modelValue: undefined,
  multiple: false,
  placeholder: '请搜索并选择用户',
  disabled: false,
  clearable: true,
})

const emit = defineEmits<{
  'update:modelValue': [value: number | number[] | undefined]
  /** 选项加载完成时触发，父组件可缓存用户名称映射 */
  'options-loaded': [users: UserSearchItem[]]
}>()

// ========== 状态 ==========
const loading = ref(false)
const options = ref<UserSearchItem[]>([])
const selected = ref<number | number[] | undefined>(props.modelValue)

// 双向绑定
watch(() => props.modelValue, (v) => { selected.value = v })
function handleChange(val: number | number[] | undefined) {
  emit('update:modelValue', val)
}

// ========== 远程搜索 ==========
let searchTimer: ReturnType<typeof setTimeout> | null = null

async function handleSearch(keyword: string) {
  if (!keyword || keyword.length < 1) {
    options.value = []
    return
  }

  // 防抖 300ms
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(async () => {
    loading.value = true
    try {
      options.value = await searchUsers(keyword)
      emit('options-loaded', options.value)
    } catch {
      options.value = []
    } finally {
      loading.value = false
    }
  }, 300)
}
</script>

<style lang="scss" scoped>
.user-option-org {
  float: right;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
