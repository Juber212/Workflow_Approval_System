<template>
  <div class="config-management">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>系统配置</span>
          <div class="card-header__actions">
            <el-button v-if="!editing" type="primary" size="small" @click="startEdit">编辑</el-button>
            <template v-else>
              <el-button size="small" @click="cancelEdit">取消</el-button>
              <el-button type="primary" size="small" :loading="saving" @click="saveConfigs">保存</el-button>
            </template>
          </div>
        </div>
      </template>

      <div v-loading="loading">
        <!-- 按分组渲染配置区 -->
        <div v-for="group in groupedConfigs" :key="group.key" class="config-group">
          <h3 class="config-group__title">{{ group.label }}</h3>
          <div class="config-group__body">
            <div
              v-for="item in group.items"
              :key="item.id"
              class="config-row"
            >
              <label class="config-row__label">{{ getConfigLabel(item.config_key) }}</label>
              <div class="config-row__value">
                <!-- 编辑模式：根据类型渲染不同输入控件 -->
                <template v-if="editing">
                  <!-- 数值型：数字输入框 -->
                  <el-input-number
                    v-if="getConfigMeta(item.config_key)?.type === 'number'"
                    v-model="editMap[item.id]"
                    :min="0"
                    :max="9999"
                    size="small"
                    controls-position="right"
                    style="width: 180px"
                  />
                  <!-- 文本型：普通输入框 -->
                  <el-input
                    v-else
                    v-model="editMap[item.id]"
                    size="small"
                    style="width: 260px"
                  />
                </template>
                <!-- 只读模式 -->
                <span v-else>{{ item.config_value }}</span>
              </div>
              <span class="config-row__hint">{{ item.description || '' }}</span>
            </div>
          </div>
        </div>

        <!-- 无配置时提示 -->
        <div v-if="groupedConfigs.length === 0 && !loading" style="text-align:center;padding:48px 0;color:var(--el-text-color-secondary)">
          暂无系统配置
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
/** 系统配置管理 —— 按分类分组，数值型用数字输入框 */
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getConfigs, updateConfigs, type ConfigItem } from '@/api/admin'

// ==================== 配置元数据 ====================

/** 配置项元数据：分组、中文标签、输入类型 */
interface ConfigMeta {
  group: string      // 分组 key
  label: string      // 中文显示名
  type: 'text' | 'number'
}

const CONFIG_META: Record<string, ConfigMeta> = {
  // ── 文件上传 ──（上传大小/允许扩展名由后端环境变量 settings 控制，不在页面配置——M28 假开关移除）
  // ── PDF 签名通用 ──
  pdf_signature_x:          { group: 'signature', label: '签名默认 X 坐标', type: 'number' },
  pdf_signature_y:          { group: 'signature', label: '签名默认 Y 坐标', type: 'number' },
  pdf_signature_offset:     { group: 'signature', label: '多签名 X 偏移量', type: 'number' },
  pdf_signature_max_width:  { group: 'signature', label: '签名图片最大宽度(px)', type: 'number' },
  pdf_signature_max_height: { group: 'signature', label: '签名图片最大高度(px)', type: 'number' },
  // ── 角色维度签名默认位置 ──
  pdf_signature_assignee_x:  { group: 'signature', label: '负责人签名 X 坐标', type: 'number' },
  pdf_signature_assignee_y:  { group: 'signature', label: '负责人签名 Y 坐标', type: 'number' },
  pdf_signature_checker_x:   { group: 'signature', label: '校验人签名 X 坐标', type: 'number' },
  pdf_signature_checker_y:   { group: 'signature', label: '校验人签名 Y 坐标', type: 'number' },
  pdf_signature_approver_x:  { group: 'signature', label: '审批人签名 X 坐标', type: 'number' },
  pdf_signature_approver_y:  { group: 'signature', label: '审批人签名 Y 坐标', type: 'number' },
  pdf_signature_endorser_x:  { group: 'signature', label: '批准人签名 X 坐标', type: 'number' },
  pdf_signature_endorser_y:  { group: 'signature', label: '批准人签名 Y 坐标', type: 'number' },
  // ── 过时配置（仍显示，但归入"其他"）──
  pdf_signature_page: { group: 'legacy', label: '签名默认页码（已过时）', type: 'number' },
}

/** 分组定义：key → 中文名称（按显示顺序排列） */
const GROUP_ORDER: { key: string; label: string }[] = [
  { key: 'upload',    label: '文件上传' },
  { key: 'signature', label: 'PDF 签名' },
  { key: 'general',   label: '通用' },
  { key: 'legacy',    label: '其他（已过时）' },
]

// ==================== 辅助函数 ====================

function getConfigMeta(key: string): ConfigMeta | undefined {
  return CONFIG_META[key]
}

function getConfigLabel(key: string): string {
  return CONFIG_META[key]?.label ?? key
}

// ==================== 状态 ====================

const loading = ref(false)
const saving = ref(false)
const list = ref<ConfigItem[]>([])
const editing = ref(false)

/** 编辑模式下每个配置项 id → 当前值 */
const editMap = reactive<Record<number, any>>({})

/** 按分组归类后的配置列表 */
const groupedConfigs = computed(() => {
  const groups = new Map<string, { key: string; label: string; items: ConfigItem[] }>()
  // 初始化分组
  for (const g of GROUP_ORDER) {
    groups.set(g.key, { key: g.key, label: g.label, items: [] })
  }
  // 归类
  for (const item of list.value) {
    const meta = getConfigMeta(item.config_key)
    const groupKey = meta?.group ?? 'legacy'
    const group = groups.get(groupKey)
    if (group) {
      group.items.push(item)
    } else {
      // 未知 key 归入"其他"
      const legacy = groups.get('legacy')!
      legacy.items.push(item)
    }
  }
  // 去掉空分组
  return Array.from(groups.values()).filter(g => g.items.length > 0)
})

// ==================== 生命周期 ====================

onMounted(async () => {
  loading.value = true
  try {
    list.value = await getConfigs()
  } finally {
    loading.value = false
  }
})

// ==================== 编辑操作 ====================

/** 进入编辑模式 —— 初始化 editMap */
function startEdit() {
  for (const item of list.value) {
    const meta = getConfigMeta(item.config_key)
    if (meta?.type === 'number') {
      editMap[item.id] = Number(item.config_value) || 0
    } else {
      editMap[item.id] = item.config_value
    }
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
      if (!orig) return false
      // 类型统一后比较字符串
      return String(orig.config_value) !== String(val)
    })
    .map(([id, val]) => ({ id: Number(id), config_value: String(val) }))

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

.card-header__actions {
  display: flex;
  gap: 8px;
}

/* ─── 配置分组 ─── */
.config-group {
  margin-bottom: 20px;

  &:last-child {
    margin-bottom: 0;
  }

  &__title {
    font-size: 15px;
    font-weight: 600;
    color: var(--el-text-color-primary);
    margin: 0 0 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--el-border-color-lighter);
  }

  &__body {
    display: flex;
    flex-direction: column;
    gap: 0;
  }
}

/* ─── 配置行 ─── */
.config-row {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  border-radius: 6px;
  transition: background 0.12s;

  &:hover {
    background: var(--el-fill-color-lighter);
  }

  &__label {
    width: 180px;
    flex-shrink: 0;
    font-size: 13px;
    font-weight: 500;
    color: var(--el-text-color-regular);
  }

  &__value {
    width: 260px;
    flex-shrink: 0;
    font-size: 13px;
    color: var(--el-text-color-primary);
    :deep(.el-input-number) {
      .el-input__wrapper {
        box-shadow: none !important;
      }
    }
  }

  &__hint {
    flex: 1;
    font-size: 12px;
    color: var(--el-text-color-placeholder);
    margin-left: 16px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}
</style>
