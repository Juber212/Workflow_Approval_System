<template>
  <!-- 文件提交文件夹配置编辑器 —— PropertyPanel/PresetEditor 共用（P2-2 抽取） -->
  <!-- 变更经 change 事件上抛（父组件决定是否实时写回 LogicFlow）；文件夹清空副作用经 mode-change 上抛 -->
  <div class="file-folders-section" :class="{ 'file-folders-section--compact': compact }">
    <div class="file-folders-section__header">
      <span class="file-folders-section__title">文件提交配置</span>
      <el-switch
        v-model="useFileFoldersModel"
        active-text="文件夹"
        inactive-text="简单"
        size="small"
        @change="handleModeToggle"
      />
    </div>

    <!-- 简单模式：require_file 开关（向后兼容） -->
    <template v-if="!useFileFolders">
      <el-form-item label="文件上传">
        <el-switch
          v-model="requireFileModel"
          active-text="必须上传"
          inactive-text="可不上传"
          @change="emitChange"
        />
      </el-form-item>
    </template>

    <!-- 文件夹模式：文件夹卡片列表 -->
    <template v-else>
      <div class="folder-list" v-if="folders.length > 0">
        <div
          v-for="(folder, idx) in folders"
          :key="idx"
          class="folder-card"
          :class="{ 'folder-card--expanded': expandedFolderIdx === idx }"
        >
          <!-- 折叠态：摘要行 -->
          <div class="folder-card__summary" @click="toggleFolder(idx)">
            <span class="folder-card__icon"><el-icon :size="14"><Folder /></el-icon></span>
            <span class="folder-card__name">{{ folder.name || '未命名文件夹' }}</span>
            <span class="folder-card__rule">{{ folderRuleSummary(folder) }}</span>
            <el-icon class="folder-card__arrow" :class="{ rotated: expandedFolderIdx === idx }"><ArrowRight /></el-icon>
          </div>

          <!-- 展开态：编辑表单 -->
          <div class="folder-card__body" v-show="expandedFolderIdx === idx">
            <el-form label-position="top" size="small">
              <el-form-item label="文件夹名称" :rules="[{ required: true, message: '请输入文件夹名称' }]">
                <el-input
                  v-model="folder.name"
                  placeholder="例如：资质文件"
                  maxlength="20"
                  show-word-limit
                  @change="emitChange"
                />
              </el-form-item>
              <el-form-item label="必须提交">
                <el-switch
                  v-model="folder.required"
                  active-text="必须提交"
                  inactive-text="可选"
                  @change="emitChange"
                />
              </el-form-item>
              <el-form-item v-if="folder.required" label="文件数量">
                <el-radio-group v-model="folderCountMode[idx]" @change="handleCountModeChange(idx)" size="small">
                  <el-radio-button value="unlimited">不限制</el-radio-button>
                  <el-radio-button value="exact">精确数量</el-radio-button>
                </el-radio-group>
                <el-input-number
                  v-if="folderCountMode[idx] === 'exact'"
                  v-model="folder.file_count"
                  :min="1"
                  :max="99"
                  style="width:100%;margin-top:8px"
                  @change="emitChange"
                />
              </el-form-item>
            </el-form>
            <el-button text type="danger" size="small" @click="removeFolder(idx)">删除文件夹</el-button>
          </div>
        </div>
      </div>

      <div class="folder-empty" v-else>
        <span class="folder-empty__hint">暂未添加文件夹，点击下方按钮添加</span>
      </div>

      <el-button
        type="primary"
        plain
        size="small"
        style="width:100%;margin-top:8px"
        @click="addFolder"
      >
        + 添加文件夹
      </el-button>

      <!-- 名称冲突警告（父组件计算注入，仅 PropertyPanel 使用） -->
      <el-alert
        v-if="nameConflict"
        type="warning"
        :closable="false"
        show-icon
        style="margin-top:8px"
      >
        {{ nameConflict }}
      </el-alert>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { ArrowRight, Folder } from '@element-plus/icons-vue'
import type { FileFolderConfig } from '@/api/designer'

const props = defineProps<{
  /** 文件夹列表（v-model） */
  folders: FileFolderConfig[]
  /** 是否文件夹模式（v-model） */
  useFileFolders: boolean
  /** 简单模式必须上传开关（v-model，父组件表单字段） */
  requireFile: boolean
  /** 文件夹名称冲突提示（父组件计算注入，无则不显示） */
  nameConflict?: string | null
  /** 紧凑间距（PresetEditor 弹窗内使用，原底部间距 8px） */
  compact?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:folders', v: FileFolderConfig[]): void
  (e: 'update:useFileFolders', v: boolean): void
  (e: 'update:requireFile', v: boolean): void
  /** 任一项变更（父组件决定是否同步写回 LogicFlow） */
  (e: 'change'): void
  /** 文件夹/简单模式切换（父组件决定是否清空列表并同步） */
  (e: 'mode-change', v: boolean): void
}>()

/** 模式开关双向绑定（props 只读，经 update 事件写回） */
const useFileFoldersModel = computed({
  get: () => props.useFileFolders,
  set: (v: boolean) => emit('update:useFileFolders', v),
})
/** 简单模式必须上传开关双向绑定 */
const requireFileModel = computed({
  get: () => props.requireFile,
  set: (v: boolean) => emit('update:requireFile', v),
})

/** 当前展开的文件夹索引 */
const expandedFolderIdx = ref<number | null>(null)
/** 每个文件夹的数量模式：unlimited | exact */
const folderCountMode = reactive<Record<number, string>>({})

/** 外部整体替换文件夹列表（加载/重置）时重建数量模式，保证索引对齐 */
watch(() => props.folders, (val) => {
  const next: Record<number, string> = {}
  val.forEach((f, i) => { next[i] = f.file_count != null ? 'exact' : 'unlimited' })
  Object.keys(folderCountMode).forEach(k => delete folderCountMode[Number(k)])
  Object.assign(folderCountMode, next)
})

/** 文件夹规则摘要文字 */
function folderRuleSummary(f: FileFolderConfig): string {
  if (!f.required) return '可选'
  if (f.file_count == null) return '至少1个，不限'
  return `必须提交 · ${f.file_count}个`
}

/** 展开/折叠文件夹 */
function toggleFolder(idx: number) {
  expandedFolderIdx.value = expandedFolderIdx.value === idx ? null : idx
}

/** 添加文件夹（自动展开新建项） */
function addFolder() {
  emit('update:folders', [...props.folders, { name: '', required: false, file_count: null }])
  const idx = props.folders.length
  folderCountMode[idx] = 'unlimited'
  expandedFolderIdx.value = idx
  emitChange()
}

/** 删除文件夹 */
function removeFolder(idx: number) {
  emit('update:folders', props.folders.filter((_, i) => i !== idx))
  delete folderCountMode[idx]
  if (expandedFolderIdx.value === idx) expandedFolderIdx.value = null
  emitChange()
}

/** 数量模式切换：unlimited 清空数量，exact 兜底为 1 */
function handleCountModeChange(idx: number) {
  const folder = props.folders[idx]
  if (!folder) return
  if (folderCountMode[idx] === 'unlimited') {
    folder.file_count = null
  } else {
    folder.file_count = folder.file_count || 1
  }
  emitChange()
}

/** 模式切换：切文件夹模式关闭简单开关；切回简单模式收起展开项；清空副作用由父组件决定 */
function handleModeToggle(val: boolean) {
  if (val) {
    emit('update:requireFile', false)
  } else {
    expandedFolderIdx.value = null
  }
  emit('mode-change', val)
}

/** 任一项变更上抛（父组件同步写回 LogicFlow） */
function emitChange() {
  emit('change')
}
</script>

<style lang="scss" scoped>
/* 文件提交配置区域 */
.file-folders-section {
  margin-bottom: 16px;

  &--compact { margin-bottom: 8px; }

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
  }

  &__title {
    font-size: 13px;
    font-weight: 600;
    color: var(--el-text-color-regular);
  }

  .folder-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .folder-card {
    border: 1px solid var(--el-border-color-light);
    border-radius: 6px;
    overflow: hidden;
    transition: border-color 0.2s;

    &:hover { border-color: var(--el-color-primary-light-5); }

    &__summary {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 8px 10px;
      cursor: pointer;
      background: var(--el-fill-color-lighter);
      user-select: none;
    }

    &__icon { font-size: 14px; flex-shrink: 0; }

    &__name {
      font-size: 13px;
      font-weight: 500;
      color: var(--el-text-color-primary);
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    &__rule {
      font-size: 11px;
      color: var(--el-text-color-secondary);
      flex-shrink: 0;
      margin-left: auto;
      margin-right: 4px;
    }

    &__arrow {
      font-size: 12px;
      color: var(--el-text-color-placeholder);
      flex-shrink: 0;
      transition: transform 0.2s;
      &.rotated { transform: rotate(90deg); }
    }

    &__body {
      padding: 10px 12px;
      border-top: 1px solid var(--el-border-color-lighter);
    }
  }

  .folder-empty {
    padding: 16px 0;
    text-align: center;

    &__hint {
      font-size: 12px;
      color: var(--el-text-color-placeholder);
    }
  }
}
</style>
