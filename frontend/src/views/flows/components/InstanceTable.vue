<template>
  <!-- 实例列表表格 —— OrgHome/FlowManagement 共用（P2-2 抽取） -->
  <!-- 数据与 fetch 权在父组件：组件负责筛选/搜索/分页交互，经 refresh 事件通知父组件拉取 -->
  <div class="instance-table">
    <!-- 表格工具栏：筛选按钮 + 搜索各独立容器 -->
    <div class="table-toolbar">
      <div class="filter-tabs">
        <button
          v-for="f in instanceFilters" :key="f.value"
          class="filter-tab" :class="{ 'is-active': statusFilter === f.value }"
          @click="handleFilterClick(f.value)"
        >
          <span class="filter-label">{{ f.label }}</span>
          <span class="filter-count">{{ counts[f.value] ?? '—' }}</span>
        </button>
      </div>
      <!-- 搜索+高级搜索独立容器 -->
      <div class="toolbar-actions">
        <el-input
          v-model="keyword" placeholder="搜索项目名称" clearable
          :prefix-icon="Search" size="default" style="width: 200px"
          @input="handleSearch"
        />
        <el-button text size="small" @click="showAdvancedSearch = !showAdvancedSearch" style="margin-left:4px">
          <el-icon><ArrowDown v-if="!showAdvancedSearch" /><ArrowUp v-else /></el-icon>
          高级搜索
        </el-button>
      </div>
    </div>
    <!-- 高级搜索面板 -->
    <div class="card__advanced-search" v-show="showAdvancedSearch">
      <el-date-picker
        v-model="dateRange" type="daterange" range-separator="至"
        start-placeholder="发起起始" end-placeholder="发起截止"
        format="YYYY-MM-DD" value-format="YYYY-MM-DD" size="default"
        style="width: 260px" @change="handleSearch"
      />
      <el-select v-model="priority" placeholder="优先级" clearable size="default" style="width: 120px" @change="handleSearch">
        <el-option label="紧急" value="urgent" /><el-option label="高" value="high" />
        <el-option label="普通" value="normal" /><el-option label="低" value="low" />
      </el-select>
      <el-select v-model="initiatorId" placeholder="发起人" clearable filterable remote
        :remote-method="searchInitiators" size="default" style="width: 180px" @change="handleSearch">
        <el-option v-for="u in initiatorOptions" :key="u.id" :label="u.real_name" :value="u.id" />
      </el-select>
    </div>

    <!-- 实例列表 -->
    <div class="card">
      <div class="card__body" style="padding:0">
        <el-table :data="items" stripe border v-loading="loading"
          :row-class-name="combinedRowClass"
          @row-click="(row: any) => emit('row-click', row)" style="cursor:pointer"
        >
          <!-- ===== 弹性列（按内容自适配） ===== -->
          <!-- 1. 项目名称 -->
          <el-table-column prop="name" label="项目名称" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="inst-name">{{ row.name }}</span>
            </template>
          </el-table-column>
          <!-- 2. 方案 -->
          <el-table-column label="方案" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="inst-meta">{{ row.proposal_name || '-' }}</span>
            </template>
          </el-table-column>
          <!-- 3. 所属组织（FlowManagement 全局视图显示） -->
          <el-table-column v-if="showOrgColumn" prop="organization_name" label="所属组织" width="90" show-overflow-tooltip />
          <!-- 4. 进度（进度条） -->
          <el-table-column label="进度" min-width="120">
            <template #default="{ row }">
              <div class="bt-progress">
                <el-progress
                  :percentage="row.total_nodes > 0 ? Math.round((row.current_node_index / row.total_nodes) * 100) : 0"
                  :stroke-width="8"
                  :show-text="false"
                />
                <span class="bt-progress__text">
                  {{ row.total_nodes > 0 ? Math.round((row.current_node_index / row.total_nodes) * 100) : 0 }}%（{{ row.current_node_index }}/{{ row.total_nodes }}）
                </span>
              </div>
            </template>
          </el-table-column>
          <!-- ===== 固定列 ===== -->
          <!-- 5. 当前处理人 -->
          <el-table-column label="当前处理人" width="110" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="inst-meta">{{ row.current_handlers || '-' }}</span>
            </template>
          </el-table-column>
          <!-- 6. 状态 -->
          <el-table-column label="状态" width="90" sortable="false">
            <template #default="{ row }">
              <span class="status-tag" :class="instStatusClass(row.status)">{{ instStatusLabel(row.status) }}</span>
            </template>
          </el-table-column>
          <!-- 7. 优先级 -->
          <el-table-column label="优先级" width="72">
            <template #default="{ row }">
              <span class="pri-badge" :class="'pri--' + row.priority">{{ priLabel(row.priority) }}</span>
            </template>
          </el-table-column>
          <!-- 8. 难度 -->
          <el-table-column label="难度" width="64">
            <template #default="{ row }">
              <span class="diff-badge diff-badge--list" :class="'diff--' + (row.difficulty || '1')">{{ row.difficulty || '1' }}级</span>
            </template>
          </el-table-column>
          <!-- 9. 发起时间 -->
          <el-table-column prop="initiated_at" label="发起时间" width="150">
            <template #default="{ row }">
              <span class="num">{{ formatTime(row.initiated_at) }}</span>
            </template>
          </el-table-column>
          <!-- 10. 流程截止 -->
          <el-table-column label="截止时间" width="150">
            <template #default="{ row }">
              <span class="num">{{ row.flow_deadline ? formatTime(row.flow_deadline) : '-' }}</span>
            </template>
          </el-table-column>
          <!-- 11. 操作 -->
          <!-- 管理员多一个"删除"按钮，列宽稍大避免换行 -->
          <el-table-column label="操作" :width="isAdmin ? 160 : 140" fixed="right">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click.stop="emit('row-click', row)">查看详情</el-button>
              <el-button v-if="isAdmin && row.status === 'terminated'" text type="danger" size="small" @click.stop="handlePermanentDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="!loading && items.length === 0" style="padding:40px 0;text-align:center">
          <span style="color:var(--el-text-color-secondary);font-size:14px">暂无项目</span>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <div class="list-pagination">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :page-sizes="[20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next"
        @current-change="emit('refresh', buildQuery())"
        @size-change="emit('refresh', buildQuery())"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import { Search, ArrowDown, ArrowUp } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { permanentDeleteInstance, type InstanceListItem } from '@/api/instance'
import { searchUsers, type UserSearchItem } from '@/api/admin'
import { formatTime, deadlineRowClass } from '@/utils/format'
import { priLabel, instStatusClass, instStatusLabel } from '@/utils/labels'

const props = defineProps<{
  items: InstanceListItem[]
  loading: boolean
  total: number
  /** 各状态实例数量（父组件统计） */
  counts: Record<string, number>
  /** 状态筛选（v-model，父组件持有以支持 URL 同步等） */
  statusFilter: string
  /** 分页（v-model） */
  page: number
  pageSize: number
  /** 是否显示所属组织列（全局视图为 true） */
  showOrgColumn?: boolean
}>()

/** 组件内筛选条件（keyword/日期/优先级/发起人），随 refresh 事件上抛给父组件用于请求参数 */
export interface InstanceQuery {
  keyword?: string
  date_from?: string
  date_to?: string
  priority?: string
  initiator_id?: number | null
}

const emit = defineEmits<{
  (e: 'update:statusFilter', v: string): void
  (e: 'update:page', v: number): void
  (e: 'update:pageSize', v: number): void
  /** 筛选/搜索/分页变化后通知父组件重新拉取列表（携带当前筛选条件） */
  (e: 'refresh', query: InstanceQuery): void
  /** 永久删除成功后通知父组件刷新状态统计 */
  (e: 'refresh-counts'): void
  (e: 'row-click', row: InstanceListItem): void
}>()

const userStore = useUserStore()
const isAdmin = computed(() => userStore.isAdmin)

const instanceFilters = [
  { label: '全部', value: 'all' },
  { label: '运行中', value: 'running' },
  { label: '已完成', value: 'completed' },
  { label: '已终止', value: 'terminated' },
]

// ========== 内部筛选状态 ==========
const keyword = ref('')
const showAdvancedSearch = ref(false)
const dateRange = ref<[string, string] | null>(null)
const priority = ref('')
const initiatorId = ref<number | null>(null)
const initiatorOptions = ref<UserSearchItem[]>([])

/** 分页双向绑定（props 只读，经 update 事件写回） */
const page = computed({
  get: () => props.page,
  set: (v: number) => emit('update:page', v),
})
const pageSize = computed({
  get: () => props.pageSize,
  set: (v: number) => emit('update:pageSize', v),
})

/** 重置页码到第 1 页 */
function resetPage() {
  if (props.page !== 1) emit('update:page', 1)
}

/** 当前筛选条件（keyword/日期/优先级/发起人） */
function buildQuery(): InstanceQuery {
  return {
    keyword: keyword.value || undefined,
    date_from: dateRange.value?.[0],
    date_to: dateRange.value?.[1],
    priority: priority.value || undefined,
    initiator_id: initiatorId.value,
  }
}

/** 切换状态筛选 Tab */
function handleFilterClick(value: string) {
  if (props.statusFilter === value) return
  emit('update:statusFilter', value)
  resetPage()
  emit('refresh', buildQuery())
}

/** 搜索防抖（300ms）：关键词/日期/优先级/发起人变化共用 */
let searchTimer: ReturnType<typeof setTimeout> | null = null
function handleSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    resetPage()
    emit('refresh', buildQuery())
  }, 300)
}

/** 远程搜索发起人（300ms 防抖） */
let initiatorSearchTimer: ReturnType<typeof setTimeout> | null = null
async function searchInitiators(query: string) {
  if (!query) { initiatorOptions.value = []; return }
  if (initiatorSearchTimer) clearTimeout(initiatorSearchTimer)
  initiatorSearchTimer = setTimeout(async () => {
    try { initiatorOptions.value = await searchUsers(query, 20) } catch { /* ignore */ }
  }, 300)
}

onUnmounted(() => {
  if (searchTimer) clearTimeout(searchTimer)
  if (initiatorSearchTimer) clearTimeout(initiatorSearchTimer)
})

// ========== 行样式 ==========
/** 实例表格优先级左侧色条：运行中 urgent/high 加强调条（背景色让给状态/逾期，避免叠加冲突） */
function instanceRowClass({ row }: { row: InstanceListItem }) {
  if (row.status !== 'running') return ''
  if (row.priority === 'urgent') return 'row--pri-bar--urgent'
  if (row.priority === 'high') return 'row--pri-bar--high'
  return ''
}

/** 合并优先级行色 + 状态行色 */
function combinedRowClass(data: { row: InstanceListItem }) {
  const pri = instanceRowClass(data)
  const dl = deadlineRowClass(data)
  return [pri, dl].filter(Boolean).join(' ')
}

// ========== 删除 ==========
/** 管理员永久删除已终止实例 */
async function handlePermanentDelete(row: InstanceListItem) {
  try {
    await ElMessageBox.confirm(`确认永久删除项目「${row.name}」？此操作不可撤销，所有关联数据将被清除。`, '永久删除', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' })
  } catch { /* 用户取消或关闭弹窗 */ return }
  try {
    await permanentDeleteInstance(row.id)
    ElMessage.success('项目已永久删除')
    emit('refresh', buildQuery())
    emit('refresh-counts')
  } catch { /* 拦截器已统一弹错（P1-35），无需重复提示 */ }
}

/** 重置全部筛选（组织切换时由父组件调用） */
function resetFilters() {
  keyword.value = ''
  showAdvancedSearch.value = false
  dateRange.value = null
  priority.value = ''
  initiatorId.value = null
  initiatorOptions.value = []
}

defineExpose({ resetFilters })
</script>

<style lang="scss" scoped>
/* 表格工具栏：筛选按钮 + 搜索操作各独立容器，同行排列（无外层卡片） */
.table-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; flex-wrap: wrap; gap: 12px; }
.toolbar-actions { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }

.filter-tabs { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.filter-tab { height: 32px; padding: 0 16px; border: 1px solid var(--el-border-color); background: #fff; border-radius: 6px; font-size: 13px; color: var(--el-text-color-regular); cursor: pointer; display: inline-flex; align-items: center; gap: 6px; line-height: 1; transition: all 0.2s; &:hover { border-color: var(--el-color-primary); color: var(--el-color-primary); } &.is-active { background: var(--el-color-primary); border-color: var(--el-color-primary); color: #fff; } }
.filter-label { display: inline-block; min-width: 3em; }
.filter-count { opacity: 0.7; }

.inst-name { font-weight: 500; color: var(--el-text-color-primary); }
.inst-meta { font-size: 13px; color: var(--el-text-color-secondary); }

/* 进度条（与首页卡点追踪一致） */
.bt-progress { display: flex; align-items: center; gap: 8px; padding: 4px 8px; :deep(.el-progress) { flex: 1; min-width: 60px; } :deep(.el-progress-bar__outer) { border-radius: 4px; } }
.bt-progress__text { font-size: 12px; color: var(--el-text-color-secondary); white-space: nowrap; flex-shrink: 0; }

.pri-badge { font-size: 12px; font-weight: 500; padding: 1px 8px; border-radius: 10px; &.pri--urgent { background: #fde2e2; color: #c0392b; } &.pri--high { background: #fef5e7; color: #d68910; } &.pri--normal { background: #eaf2f8; color: #2471a3; } &.pri--low { background: #f2f3f5; color: #86909c; } }

.list-pagination { display: flex; justify-content: flex-end; margin-top: 16px; }
.num { font-variant-numeric: tabular-nums; }

/* 高级搜索面板（独立于表格工具栏，折叠展开） */
.card__advanced-search {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 16px; margin-bottom: 8px;
  background: #fff; border: 1px solid var(--el-border-color-light); border-radius: 8px;
  flex-wrap: wrap;
}
</style>

<style lang="scss">
/* 优先级左侧色条（仅运行中实例）—— 背景色让给状态/逾期，两套信号互不覆盖 */
.row--pri-bar--urgent td:first-child { box-shadow: inset 3px 0 0 0 #c0392b; }
.row--pri-bar--high td:first-child { box-shadow: inset 3px 0 0 0 #d68910; }

/* 状态行背景色 —— tr 前缀确保覆盖 el-table stripe 条纹 */
tr.r--red td { background: #fef0f0 !important; }    /* 逾期=淡红 */
tr.r--yel td { background: #fffaf0 !important; }    /* 临期=淡黄 */
tr.r--green td { background: #eafaf1 !important; }   /* 已完成=淡绿 */
tr.r--gray td { background: #f2f3f5 !important; }    /* 已终止=淡灰 */
</style>
