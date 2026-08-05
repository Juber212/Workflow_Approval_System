<template>
  <!-- 详情页文件展示 —— 本节点文件 + 历史节点文件分组 + 无文件兜底（P2-2 抽取，Check/Approval/Endorse 三页共用） -->
  <div class="file-list-view">
    <!-- 本节点文件 -->
    <div class="card" v-if="currentNodeFiles.length > 0">
      <div class="card__header">
        <span>本节点文件（{{ currentNodeFiles.length }}）<el-tag size="small" type="primary" effect="plain" style="margin-left:6px">当前节点</el-tag></span>
      </div>
      <div class="card__body">
        <div v-for="f in currentNodeFiles" :key="f.id" class="file-row">
          <span>{{ f.original_name }}</span>
          <span class="file-size">{{ formatFileSize(f.file_size) }}</span>
          <el-button text type="primary" size="small" @click="previewFile(f.id)">查看</el-button>
          <el-button text type="primary" size="small" @click="downloadFile(f.id)">下载</el-button>
        </div>
      </div>
    </div>

    <!-- 历史节点文件（默认折叠） -->
    <div class="card" v-if="historyGroups.length > 0">
      <div class="card__header" style="cursor:pointer" @click="showHistoryFiles = !showHistoryFiles">
        <span style="display:flex;align-items:center;gap:6px">
          历史节点文件（{{ historyTotal }}）
          <el-icon :size="14" style="transition:transform 0.2s" :style="{ transform: showHistoryFiles ? 'rotate(90deg)' : 'rotate(0deg)' }"><ArrowRight /></el-icon>
        </span>
      </div>
      <div class="card__body" v-show="showHistoryFiles">
        <div v-for="group in historyGroups" :key="group.nodeKey" class="file-group">
          <div class="file-group__header">
            <span class="file-group__node-name">{{ group.nodeName }}</span>
            <span class="file-group__count">{{ group.files.length }} 个文件</span>
          </div>
          <div v-for="f in group.files" :key="f.id" class="file-row">
            <span>{{ f.original_name }}</span>
            <span class="file-size">{{ formatFileSize(f.file_size) }}</span>
            <el-button text type="primary" size="small" @click="previewFile(f.id)">查看</el-button>
            <el-button text type="primary" size="small" @click="downloadFile(f.id)">下载</el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 无文件兜底 -->
    <div class="card" v-if="currentNodeFiles.length === 0 && historyGroups.length === 0">
      <div class="card__header">{{ emptyTitle }}</div>
      <div class="card__body"><div class="empty-hint">暂无文件</div></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ArrowRight } from '@element-plus/icons-vue'
import { previewFile, downloadFile } from '@/api/task'
import { formatFileSize } from '@/utils/format'
import type { HistoryFileGroup } from '@/composables/useDetailFileGrouping'

/** 本节点文件（node_files 结构较简，此处只声明展示用字段） */
export interface CurrentNodeFile {
  id: number
  original_name: string
  file_size: number | null
}

const props = defineProps<{
  /** 本节点文件（后端 node_files 已过滤） */
  currentNodeFiles: CurrentNodeFile[]
  /** 历史节点文件分组（useDetailFileGrouping 输出） */
  historyGroups: HistoryFileGroup[]
  /** 无文件兜底卡的标题（Endorse 页用「流程文件」） */
  emptyTitle?: string
  /** 是否默认展开历史文件（终审节点为 true） */
  defaultExpand?: boolean
}>()

/** 历史节点文件（默认折叠，终审节点默认展开） */
const showHistoryFiles = ref(props.defaultExpand ?? false)

/** 历史文件总数 */
const historyTotal = computed(() => props.historyGroups.reduce((s, g) => s + g.files.length, 0))
</script>

<style lang="scss" scoped>
/* 文件分组 */
.file-group {
  margin-bottom: 12px;
  &:last-child { margin-bottom: 0; }
  &__header {
    display: flex; align-items: center; gap: 8px;
    padding: 4px 0; margin-bottom: 4px;
    border-bottom: 1px solid var(--el-border-color-lighter);
  }
  &__node-name { font-size: 13px; font-weight: 600; color: var(--el-text-color-primary); }
  &__count { font-size: 12px; color: var(--el-text-color-secondary); margin-left: auto; }
}

.file-row { display: flex; align-items: center; gap: 10px; padding: 4px 8px; background: var(--el-bg-color-page); border-radius: 4px; margin-bottom: 4px; font-size: 13px; }
.file-size { color: var(--el-text-color-secondary); font-size: 12px; }
.empty-hint { color: var(--el-text-color-placeholder); font-size: 13px; text-align: center; padding: 12px; }
</style>
