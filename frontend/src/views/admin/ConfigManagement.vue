<template>
  <div class="config-management">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>系统配置</span>
          <el-button v-if="!editing" type="primary" size="small" @click="startEdit">编辑</el-button>
          <template v-else>
            <el-button size="small" @click="cancelEdit">取消</el-button>
            <el-button type="primary" size="small" :loading="saving" @click="saveConfigs">保存</el-button>
          </template>
        </div>
      </template>

      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column prop="config_key" label="配置键" width="220" />
        <el-table-column label="配置值" min-width="250">
          <template #default="{ row }">
            <el-input v-if="editing" v-model="editMap[row.id]" />
            <span v-else>{{ row.config_value }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="说明" min-width="200">
          <template #default="{ row }">
            {{ row.description || '-' }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getConfigs, updateConfigs, type ConfigItem } from '@/api/admin'

const loading = ref(false)
const saving = ref(false)
const list = ref<ConfigItem[]>([])
const editing = ref(false)

/** 编辑模式下每个配置项 id → 当前输入值 */
const editMap = reactive<Record<number, string>>({})

onMounted(async () => {
  loading.value = true
  try {
    list.value = await getConfigs()
  } finally {
    loading.value = false
  }
})

/** 进入编辑模式 —— 复制当前值到 editMap */
function startEdit() {
  for (const item of list.value) {
    editMap[item.id] = item.config_value
  }
  editing.value = true
}

/** 取消编辑 */
function cancelEdit() {
  editing.value = false
}

/** 保存配置 */
async function saveConfigs() {
  const items = Object.entries(editMap)
    .filter(([id, val]) => {
      const orig = list.value.find(c => c.id === Number(id))
      return orig && orig.config_value !== val
    })
    .map(([id, val]) => ({ id: Number(id), config_value: val }))

  if (items.length === 0) {
    ElMessage.info('没有变更')
    editing.value = false
    return
  }

  saving.value = true
  try {
    await updateConfigs(items)
    // 更新本地列表
    for (const item of items) {
      const cfg = list.value.find(c => c.id === item.id)
      if (cfg) cfg.config_value = item.config_value
    }
    ElMessage.success(`已更新 ${items.length} 项配置`)
    editing.value = false
  } finally {
    saving.value = false
  }
}
</script>

<style lang="scss" scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
