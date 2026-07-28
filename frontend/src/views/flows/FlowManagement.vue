<template>
  <!-- 项目管理全局视图 —— 组织卡片 + 全部项目（PRD P03） -->
  <div class="flow-management">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="page-header__info">
        <h1 class="page-header__title">项目管理<span class="page-header__subtitle">各组织项目运行概览，点击卡片进入对应组织</span></h1>
      </div>
    </div>

    <!-- 组织卡片列表（点击跳转 /flows/organization/:id） -->
    <OrgCardList :orgs="orgs" @select="handleOrgSelect" />

    <!-- 全部项目 -->
    <div class="section-divider">
      <h3 class="section-label">全部项目</h3>
    </div>

    <!-- 表格工具栏：筛选按钮 + 搜索各独立容器 -->
    <div class="table-toolbar">
      <!-- 状态筛选按钮独立容器 -->
      <div class="filter-tabs">
        <button
          v-for="f in instanceFilters" :key="f.value"
          class="filter-tab" :class="{ 'is-active': instanceStatusFilter === f.value }"
          @click="handleInstanceFilter(f.value)"
        >
          <span class="filter-label">{{ f.label }}</span>
          <span class="filter-count">{{ statusCounts[f.value] ?? '—' }}</span>
        </button>
      </div>
      <!-- 搜索+高级搜索独立容器 -->
      <div class="toolbar-actions">
        <el-input
          v-model="instanceKeyword" placeholder="搜索项目名称" clearable
          :prefix-icon="Search" size="default" style="width: 200px"
          @input="handleInstanceSearch"
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
        v-model="instanceDateRange" type="daterange" range-separator="至"
        start-placeholder="发起起始" end-placeholder="发起截止"
          format="YYYY-MM-DD" value-format="YYYY-MM-DD" size="default"
          style="width: 260px" @change="handleInstanceSearch"
        />
        <el-select v-model="instancePriority" placeholder="优先级" clearable size="default" style="width: 120px" @change="handleInstanceSearch">
          <el-option label="紧急" value="urgent" /><el-option label="高" value="high" />
          <el-option label="普通" value="normal" /><el-option label="低" value="low" />
        </el-select>
        <el-select v-model="instanceInitiatorId" placeholder="发起人" clearable filterable remote
          :remote-method="searchInitiators" size="default" style="width: 180px" @change="handleInstanceSearch">
          <el-option v-for="u in initiatorOptions" :key="u.user_id" :label="u.real_name" :value="u.user_id" />
        </el-select>
    </div>

    <!-- 实例列表 -->
    <div class="card">
      <div class="card__body" style="padding:0">
        <el-table :data="instances" stripe border v-loading="instanceLoading"
          :row-class-name="instanceRowClass"
          @row-click="handleInstanceRowClick" style="cursor:pointer"
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
          <!-- 3. 所属组织 -->
          <el-table-column prop="organization_name" label="所属组织" show-overflow-tooltip />
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
              <span class="diff-badge" :class="'diff--' + (row.difficulty || '1')">{{ row.difficulty || '1' }}级</span>
            </template>
          </el-table-column>
          <!-- 9. 发起时间 -->
          <el-table-column prop="initiated_at" label="发起时间" width="150">
            <template #default="{ row }">
              <span class="num">{{ formatTime(row.initiated_at) }}</span>
            </template>
          </el-table-column>
          <!-- 10. 操作 -->
          <!-- 管理员多一个"删除"按钮，列宽稍大避免换行 -->
          <el-table-column label="操作" :width="isAdmin ? 160 : 140" fixed="right">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click.stop="goInstanceDetail(row.id)">查看详情</el-button>
              <el-button v-if="isAdmin && row.status === 'terminated'" text type="danger" size="small" @click.stop="handlePermanentDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="!instanceLoading && instances.length === 0" style="padding:40px 0;text-align:center">
          <span style="color:var(--el-text-color-secondary);font-size:14px">暂无项目</span>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <div class="list-pagination">
      <el-pagination
        v-model:current-page="instancePage"
        v-model:page-size="instancePageSize"
        :page-sizes="[20, 50, 100]"
        :total="instanceTotal"
        layout="total, sizes, prev, pager, next"
        @current-change="fetchInstances"
        @size-change="fetchInstances"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 项目管理全局入口页 —— 组织卡片 + 全部项目（PRD P03）
 * 点击组织卡片 → 跳转 /flows/organization/:id
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Search, ArrowDown, ArrowUp } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { getTemplateOrganizations, type OrgCardItem } from '@/api/template'
import { getInstances, permanentDeleteInstance, type InstanceListItem } from '@/api/instance'
import { searchUsers } from '@/api/admin'
import { useBreadcrumb } from '@/composables/useBreadcrumb'
import { formatTime } from '@/utils/format'
import { priLabel, instStatusClass, instStatusLabel } from '@/utils/labels'
import OrgCardList from './components/OrgCardList.vue'

const { setBreadcrumb } = useBreadcrumb()
const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const isAdmin = computed(() => userStore.isAdmin)

// ========== 组织卡片 ==========
const orgs = ref<OrgCardItem[]>([])

// ========== 实例列表 ==========
const instanceLoading = ref(false)
const instances = ref<InstanceListItem[]>([])
const instanceTotal = ref(0)
const instancePage = ref(1)
const instancePageSize = ref(20)
/** 实例状态筛选 —— 与 URL query.status 双向同步，支持外部链接预选 */
const validStatuses = ['all', 'running', 'completed', 'terminated']
const instanceStatusFilter = ref((validStatuses.includes(route.query.status as string) ? route.query.status : 'all') as string)
const instanceKeyword = ref('')
/** 高级搜索 */
const showAdvancedSearch = ref(false)
const instanceDateRange = ref<[string, string] | null>(null)
const instancePriority = ref('')
const instanceInitiatorId = ref<number | null>(null)
const initiatorOptions = ref<{ user_id: number; real_name: string }[]>([])
/** 各状态实例数量（从 API 获取） */
const statusCounts = ref<Record<string, number>>({})

const instanceFilters = [
  { label: '全部', value: 'all' },
  { label: '运行中', value: 'running' },
  { label: '已完成', value: 'completed' },
  { label: '已终止', value: 'terminated' },
]

// ========== 初始化 ==========
onMounted(async () => {
  setBreadcrumb([{ label: '首页', to: '/dashboard' }, { label: '项目管理' }])
  await Promise.all([fetchOrgs(), fetchInstances(), fetchStatusCounts()])
})

onUnmounted(() => {
  if (searchTimer) clearTimeout(searchTimer)
  if (initiatorSearchTimer) clearTimeout(initiatorSearchTimer)
})

async function fetchOrgs() {
  try {
    const data = await getTemplateOrganizations()
    orgs.value = data.organizations
  } catch { /* 拦截器统一处理 */ }
}

/** 点击组织卡片 → 跳转所内主页 */
function handleOrgSelect(orgId: number) {
  router.push({ name: 'OrgHome', params: { orgId } })
}

/** 获取各状态的实例总数 */
async function fetchStatusCounts() {
  try {
    const results = await Promise.all([
      getInstances({ page_size: 1 }),
      getInstances({ page_size: 1, status: 'running' }),
      getInstances({ page_size: 1, status: 'completed' }),
      getInstances({ page_size: 1, status: 'terminated' }),
    ])
    statusCounts.value = {
      all: results[0].total,
      running: results[1].total,
      completed: results[2].total,
      terminated: results[3].total,
    }
  } catch { /* ignore */ }
}

// ========== 实例列表 ==========
async function fetchInstances() {
  instanceLoading.value = true
  try {
    const data = await getInstances({
      page: instancePage.value,
      page_size: instancePageSize.value,
      status: instanceStatusFilter.value === 'all' ? undefined : instanceStatusFilter.value,
      keyword: instanceKeyword.value || undefined,
      sort_by: instanceStatusFilter.value === 'running' ? 'priority' : undefined,
      priority: instancePriority.value || undefined,
      date_from: instanceDateRange.value?.[0],
      date_to: instanceDateRange.value?.[1],
      initiator_id: instanceInitiatorId.value ?? undefined,
    })
    instances.value = data.items
    instanceTotal.value = data.total
  } catch { /* 拦截器统一处理 */ }
  finally { instanceLoading.value = false }
}

/** 实例表格行高亮：运行中 urgent/high 加背景色 */
function instanceRowClass({ row }: { row: InstanceListItem }) {
  if (row.status !== 'running') return ''
  if (row.priority === 'urgent') return 'row--priority-urgent'
  if (row.priority === 'high') return 'row--priority-high'
  return ''
}

function handleInstanceFilter(status: string) {
  instanceStatusFilter.value = status
  instancePage.value = 1
  fetchInstances()
}

// ── URL query ↔ 状态筛选 双向同步 ──
// 筛选变更 → 写入 URL
watch(instanceStatusFilter, (val) => {
  if (route.query.status !== val) {
    router.replace({ query: { ...route.query, status: val === 'all' ? undefined : val } })
  }
})
// 浏览器前进/后退 → 读取 URL
watch(() => route.query.status, (val) => {
  const target = validStatuses.includes(val as string) ? val : 'all'
  if (instanceStatusFilter.value !== target) {
    instanceStatusFilter.value = target as string
    instancePage.value = 1
    fetchInstances()
  }
})

let searchTimer: ReturnType<typeof setTimeout> | null = null
function handleInstanceSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    instancePage.value = 1
    fetchInstances()
  }, 300)
}

/** 远程搜索发起人 */
let initiatorSearchTimer: ReturnType<typeof setTimeout> | null = null
async function searchInitiators(query: string) {
  if (!query) { initiatorOptions.value = []; return }
  if (initiatorSearchTimer) clearTimeout(initiatorSearchTimer)
  initiatorSearchTimer = setTimeout(async () => {
    try { initiatorOptions.value = await searchUsers({ keyword: query, page_size: 20 }) } catch { /* ignore */ }
  }, 300)
}

function goInstanceDetail(id: number) { router.push({ name: 'InstanceDetail', params: { id } }) }
function handleInstanceRowClick(row: InstanceListItem) { goInstanceDetail(row.id) }

/** 管理员永久删除已终止实例 */
async function handlePermanentDelete(row: InstanceListItem) {
  try {
    await ElMessageBox.confirm(`确认永久删除项目「${row.name}」？此操作不可撤销，所有关联数据将被清除。`, '永久删除', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' })
  } catch { /* 用户取消关闭，无需处理 */ return }
  try {
    await permanentDeleteInstance(row.id)
    ElMessage.success('项目已永久删除')
    fetchInstances()
    fetchStatusCounts()
  } catch (e: any) { ElMessage.error(e?.response?.data?.message || '删除失败') }
}

// 时间/状态标签 —— 统一从 @/utils 导入
</script>

<style lang="scss" scoped>
.page-header__subtitle { margin-left: 12px; font-weight: 400; }

.flow-management { :deep(.caret-wrapper) { display: none; } :deep(.el-table__header) .el-icon { display: none !important; } :deep(.el-table .cell)::before, :deep(.el-table .cell)::after { display: none !important; content: none !important; } }
.section-divider { display: flex; align-items: center; margin: 24px 0 16px; }
.section-label { font-size: 15px; font-weight: 600; color: var(--el-text-color-primary); margin: 0; }

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

.pri-badge { font-size: 12px; font-weight: 500; padding: 1px 8px; border-radius: 10px; &.pri--urgent { color: #fff; background: var(--el-color-danger); } &.pri--high { color: #fff; background: var(--el-color-warning); } &.pri--normal { color: var(--el-text-color-secondary); background: var(--el-fill-color); } &.pri--low { color: var(--el-color-info); background: var(--el-color-info-light-9); } }

/* 难度等级 badge */
.diff-badge { font-size: 12px; font-weight: 500; padding: 1px 8px; border-radius: 10px; &.diff--1 { color: #1e8449; background: #eafaf1; } &.diff--2 { color: #2471a3; background: #eaf2f8; } &.diff--3 { color: #b87333; background: #fef5e7; } &.diff--4 { color: #fff; background: var(--el-color-danger); } }

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
/* 优先级行高亮（仅运行中实例） */
.row--priority-urgent td { background: #fde8e8 !important; }
.row--priority-high td { background: #fef3e2 !important; }
</style>
