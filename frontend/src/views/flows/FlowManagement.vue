<template>
  <!-- 流程管理全局视图 —— 组织卡片 + 全部流程实例（PRD P03） -->
  <div class="flow-management">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="page-header__info">
        <h1 class="page-header__title">流程管理<span class="page-header__subtitle">各组织流程运行概览，点击卡片进入对应组织</span></h1>
      </div>
    </div>

    <!-- 组织卡片列表（点击跳转 /flows/organization/:id） -->
    <OrgCardList :orgs="orgs" @select="handleOrgSelect" />

    <!-- 全部流程实例 -->
    <div class="section-divider">
      <h3 class="section-label">全部流程实例</h3>
    </div>

    <!-- 实例操作栏 -->
    <div class="instance-toolbar">
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
      <div class="instance-toolbar__right">
        <el-input
          v-model="instanceKeyword" placeholder="搜索实例名称" clearable
          :prefix-icon="Search" size="default" style="width: 220px"
          @input="handleInstanceSearch"
        />
      </div>
    </div>

    <!-- 实例列表 -->
    <div class="card">
      <div class="card__body" style="padding:0">
        <el-table :data="instances" stripe v-loading="instanceLoading"
          @row-click="handleInstanceRowClick" style="cursor:pointer"
        >
          <el-table-column prop="name" label="实例名称" min-width="140">
            <template #default="{ row }">
              <span class="inst-name">{{ row.name }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="organization_name" label="所属组织" min-width="100" />
          <el-table-column label="当前负责人" min-width="100">
            <template #default="{ row }">
              <span class="inst-meta">{{ row.current_assignee_name || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="进度" min-width="64" align="center">
            <template #default="{ row }">
              <span class="inst-progress">{{ row.current_node_index }} / {{ row.total_nodes }}</span>
            </template>
          </el-table-column>
          <el-table-column label="优先级" min-width="64" align="center">
            <template #default="{ row }">
              <span class="pri-badge" :class="'pri--' + row.priority">{{ priShort(row.priority) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="initiated_at" label="发起时间" min-width="140">
            <template #default="{ row }">
              <span class="num">{{ fmtTime(row.initiated_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" min-width="64" align="center">
            <template #default="{ row }">
              <span class="status-tag" :class="instStatusClass(row.status)">{{ instStatusLabel(row.status) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="120" fixed="right">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click.stop="goInstanceDetail(row.id)">查看详情</el-button>
              <el-button v-if="isAdmin && row.status === 'terminated'" text type="danger" size="small" @click.stop="handlePermanentDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="!instanceLoading && instances.length === 0" style="padding:40px 0;text-align:center">
          <span style="color:var(--el-text-color-secondary);font-size:14px">暂无流程实例</span>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <div class="list-pagination" v-if="instanceTotal > instancePageSize">
      <el-pagination
        v-model:current-page="instancePage" :page-size="instancePageSize"
        :total="instanceTotal" layout="prev, pager, next"
        @current-change="fetchInstances"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 流程管理全局入口页 —— 组织卡片 + 全部流程实例（PRD P03）
 * 点击组织卡片 → 跳转 /flows/organization/:id
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { getTemplateOrganizations, type OrgCardItem } from '@/api/template'
import { getInstances, permanentDeleteInstance, type InstanceListItem } from '@/api/instance'
import OrgCardList from './components/OrgCardList.vue'

const router = useRouter()
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
const instanceStatusFilter = ref('all')
const instanceKeyword = ref('')
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
  await Promise.all([fetchOrgs(), fetchInstances(), fetchStatusCounts()])
})

async function fetchOrgs() {
  try {
    const data = await getTemplateOrganizations()
    orgs.value = data.organizations
  } catch { /* 拦截器统一处理 */ }
}

/** 点击组织卡片 → 跳转所内主页 */
function handleOrgSelect(orgId: number) {
  router.push(`/flows/organization/${orgId}`)
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
    })
    instances.value = data.items
    instanceTotal.value = data.total
  } catch { /* 拦截器统一处理 */ }
  finally { instanceLoading.value = false }
}

function handleInstanceFilter(status: string) {
  instanceStatusFilter.value = status
  instancePage.value = 1
  fetchInstances()
}

let searchTimer: ReturnType<typeof setTimeout> | null = null
function handleInstanceSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    instancePage.value = 1
    fetchInstances()
  }, 300)
}

function goInstanceDetail(id: number) { router.push(`/flows/instances/${id}`) }
function handleInstanceRowClick(row: InstanceListItem) { goInstanceDetail(row.id) }

/** 管理员永久删除已终止实例 */
async function handlePermanentDelete(row: InstanceListItem) {
  try {
    await ElMessageBox.confirm(`确认永久删除实例「${row.name}」？此操作不可撤销，所有关联数据将被清除。`, '永久删除', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' })
  } catch { return }
  try {
    await permanentDeleteInstance(row.id)
    ElMessage.success('实例已永久删除')
    fetchInstances()
    fetchStatusCounts()
  } catch (e: any) { ElMessage.error(e?.response?.data?.message || '删除失败') }
}

// ========== 工具 ==========
function fmtTime(val: string | null): string {
  if (!val) return '-'
  return val.replace('T', ' ').substring(0, 16)
}
function priShort(p: string): string {
  const m: Record<string, string> = { urgent: '紧急', high: '高', normal: '普通', low: '低' }
  return m[p] || p
}
function instStatusClass(s: string): string {
  const m: Record<string, string> = { created: 'status-tag--draft', running: 'status-tag--running', completed: 'status-tag--completed', terminated: 'status-tag--terminated' }
  return m[(s || '').toLowerCase()] || ''
}
function instStatusLabel(s: string): string {
  const m: Record<string, string> = { created: '已创建', running: '运行中', completed: '已完成', terminated: '已终止' }
  return m[(s || '').toLowerCase()] || s
}
</script>

<style lang="scss" scoped>
.page-header__subtitle { margin-left: 12px; font-weight: 400; }

.flow-management { /* max-width 由 AppLayout 内容区统一控制 */ }
.section-divider { display: flex; align-items: center; margin: 24px 0 16px; }
.section-label { font-size: 15px; font-weight: 600; color: var(--el-text-color-primary); margin: 0; }

.instance-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; flex-wrap: wrap; gap: 12px; &__right { display: flex; align-items: center; gap: 10px; flex-shrink: 0; } }

.filter-tabs { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.filter-tab { height: 32px; padding: 0 16px; border: 1px solid var(--el-border-color); background: #fff; border-radius: 6px; font-size: 13px; color: var(--el-text-color-regular); cursor: pointer; display: inline-flex; align-items: center; gap: 6px; line-height: 1; transition: all 0.2s; &:hover { border-color: var(--el-color-primary); color: var(--el-color-primary); } &.is-active { background: var(--el-color-primary); border-color: var(--el-color-primary); color: #fff; } }
.filter-label { display: inline-block; min-width: 3em; }
.filter-count { opacity: 0.7; }

.inst-name { font-weight: 500; color: var(--el-text-color-primary); }
.inst-meta { font-size: 13px; color: var(--el-text-color-secondary); }
.inst-progress { font-size: 13px; font-weight: 500; font-variant-numeric: tabular-nums; color: var(--el-text-color-primary); }

.pri-badge { font-size: 12px; font-weight: 500; padding: 1px 8px; border-radius: 10px; &.pri--urgent { color: #fff; background: var(--el-color-danger); } &.pri--high { color: #fff; background: var(--el-color-warning); } &.pri--normal { color: var(--el-text-color-secondary); background: var(--el-fill-color); } &.pri--low { color: var(--el-color-info); background: var(--el-color-info-light-9); } }

.list-pagination { display: flex; justify-content: center; margin-top: 16px; }
.num { font-variant-numeric: tabular-nums; }
</style>
