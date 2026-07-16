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
    @visible-change="handleVisibleChange"
  >
    <el-option
      v-for="user in options"
      :key="user.id"
      :label="user.username ? `${user.real_name} (${user.username})` : user.real_name"
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
import { useUserStore } from '@/stores/user'

/** Props */
const props = withDefaults(defineProps<{
  modelValue?: number | number[]
  /** 初始选项 —— 用于预填已选用户的显示名称，避免显示裸 ID */
  initialOptions?: UserSearchItem[]
  multiple?: boolean
  placeholder?: string
  disabled?: boolean
  clearable?: boolean
  /** 是否启用本所人员下拉浏览 —— 展开时自动加载当前用户所属组织的成员 */
  orgMembers?: boolean
}>(), {
  modelValue: undefined,
  initialOptions: () => [],
  multiple: false,
  placeholder: '请搜索并选择用户',
  disabled: false,
  clearable: true,
  orgMembers: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: number | number[] | undefined]
  /** 选项加载完成时触发，父组件可缓存用户名称映射 */
  'options-loaded': [users: UserSearchItem[]]
}>()

const userStore = useUserStore()

// ========== 状态 ==========
const loading = ref(false)
const options = ref<UserSearchItem[]>([])
const selected = ref<number | number[] | undefined>(props.modelValue)
/** 是否正在搜索模式（用户已输入关键词，使用远程搜索） */
const isSearching = ref(false)

// 双向绑定
watch(() => props.modelValue, (v) => { selected.value = v })

/** 初始选项：用于预填已选用户的名称，避免 el-select 显示裸 ID */
watch(() => props.initialOptions, (users) => {
  if (users && users.length > 0) {
    options.value = users
    emit('options-loaded', users)
  }
}, { immediate: true })

function handleChange(val: number | number[] | undefined) {
  emit('update:modelValue', val)
}

// ========== 本所成员浏览 ==========

/** 下拉框展开/收起事件 */
async function handleVisibleChange(visible: boolean) {
  if (!visible) return
  if (!props.orgMembers) return
  // 已有搜索关键词 → 走远程搜索逻辑，不覆盖
  if (isSearching.value) return
  // 已加载过 → 不重复请求
  if (options.value.length > 0 && !isSearching.value) return

  const orgId = userStore.userInfo?.organization_id
  if (!orgId) return

  loading.value = true
  try {
    options.value = await searchUsers(undefined, 100, orgId)
    emit('options-loaded', options.value)
  } catch {
    options.value = []
  } finally {
    loading.value = false
  }
}

// ========== 远程搜索 ==========
let searchTimer: ReturnType<typeof setTimeout> | null = null

async function handleSearch(keyword: string) {
  if (!keyword || keyword.length < 1) {
    // 清空搜索 → 切回本所浏览模式
    isSearching.value = false
    options.value = []
    // 重新加载本所成员
    const orgId = userStore.userInfo?.organization_id
    if (props.orgMembers && orgId) {
      loading.value = true
      try {
        options.value = await searchUsers(undefined, 100, orgId)
        emit('options-loaded', options.value)
      } catch {
        options.value = []
      } finally {
        loading.value = false
      }
    }
    return
  }

  isSearching.value = true

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
