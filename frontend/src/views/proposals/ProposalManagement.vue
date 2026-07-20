<template>
  <!-- 方案管理全局视图 —— 组织卡片 + 全部方案（方案库浏览，发起入口在组织内部页面） -->
  <div class="proposal-management">
    <div class="page-header">
      <div class="page-header__info">
        <h1 class="page-header__title">方案管理<span class="page-header__subtitle">各组织方案概览，点击卡片进入对应组织</span></h1>
      </div>
    </div>

    <!-- 方案组织卡片列表（点击跳转 /proposals/organization/:id） -->
    <ProposalOrgCardList :orgs="propOrgs" @select="handleOrgSelect" />

    <!-- 全部方案 -->
    <div class="section-divider">
      <h3 class="section-label">全部方案</h3>
    </div>

    <!-- 操作栏 -->
    <div class="instance-toolbar">
      <div class="filter-tabs">
        <button
          v-for="f in statusFilters" :key="f.value"
          class="filter-tab" :class="{ 'is-active': statusFilter === f.value }"
          @click="handleStatusFilter(f.value)"
        >
          <span class="filter-label">{{ f.label }}</span>
          <span class="filter-count">{{ statusCounts[f.value] ?? '—' }}</span>
        </button>
      </div>
      <div class="instance-toolbar__right">
        <el-input
          v-model="keyword" placeholder="搜索方案名称" clearable
          :prefix-icon="Search" size="default" style="width: 220px"
          @input="handleSearch"
        />
      </div>
    </div>

    <!-- 方案列表 -->
    <div class="card">
      <div class="card__body" style="padding:0">
        <el-table :data="proposals" stripe v-loading="loading" @row-click="handleRowClick" style="cursor:pointer">
          <el-table-column prop="name" label="方案名称" min-width="160">
            <template #default="{ row }"><span class="inst-name">{{ row.name }}</span></template>
          </el-table-column>
          <el-table-column prop="organization_name" label="所属组织" min-width="100" v-if="false" />
          <el-table-column prop="initiator_name" label="发起人" min-width="80" />
          <el-table-column prop="description" label="说明" min-width="140" show-overflow-tooltip />
          <el-table-column prop="created_at" label="发起时间" min-width="140">
            <template #default="{ row }"><span class="num">{{ fmtTime(row.created_at) }}</span></template>
          </el-table-column>
          <el-table-column label="状态" min-width="80" align="center">
            <template #default="{ row }">
              <span class="status-tag" :class="instStatusClass(row.status)">{{ instStatusLabel(row.status) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="80" fixed="right">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click.stop="goDetail(row.id)">查看详情</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div v-if="!loading && proposals.length === 0" style="padding:40px 0;text-align:center">
          <span style="color:var(--el-text-color-secondary);font-size:14px">暂无方案</span>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <div class="list-pagination" v-if="total > pageSize">
      <el-pagination
        v-model:current-page="page" :page-size="pageSize"
        :total="total" layout="prev, pager, next"
        @current-change="fetchList"
      />
    </div>

  </div>
</template>

<script setup lang="ts">
/** 方案管理全局入口 —— 组织卡片 + 全部方案（方案库浏览，发起入口在组织内部页面） */
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { getProposals, getProposalOrganizations, type ProposalListItem, type ProposalOrgCardItem } from '@/api/proposal'
import { getOrgOptions } from '@/api/admin'
import { useBreadcrumb } from '@/composables/useBreadcrumb'
import ProposalOrgCardList from './ProposalOrgCardList.vue'

const { setBreadcrumb } = useBreadcrumb()
const router = useRouter()

// ========== 组织卡片 ==========
const propOrgs = ref<ProposalOrgCardItem[]>([])

// ========== 方案列表 ==========
const loading = ref(false)
const proposals = ref<ProposalListItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const statusFilter = ref('all')
const keyword = ref('')
const statusCounts = ref<Record<string, number>>({})

const statusFilters = [
  { label: '全部', value: 'all' },
  { label: '运行中', value: 'running' },
  { label: '已完成', value: 'completed' },
  { label: '已终止', value: 'terminated' },
]

onMounted(async () => {
  setBreadcrumb([{ label: '首页', to: '/dashboard' }, { label: '方案管理' }])
  await Promise.all([fetchOrgs(), fetchList(), fetchStatusCounts()])
})

/** 合并组织列表 + 方案统计，确保所有组织卡片都显示（无方案也显示） */
async function fetchOrgs() {
  try {
    const [allOrgs, statsData] = await Promise.all([
      getOrgOptions(),
      getProposalOrganizations().catch(() => ({ organizations: [] as ProposalOrgCardItem[] })),
    ])
    const statsMap = new Map(statsData.organizations.map(o => [o.id, o]))
    propOrgs.value = allOrgs.map(org => ({
      id: org.id, name: org.name,
      total_count: statsMap.get(org.id)?.total_count || 0,
      running_count: statsMap.get(org.id)?.running_count || 0,
      completed_count: statsMap.get(org.id)?.completed_count || 0,
      terminated_count: statsMap.get(org.id)?.terminated_count || 0,
      latest_update_time: statsMap.get(org.id)?.latest_update_time || null,
    }))
  } catch {
    // 兜底：至少显示组织列表
    try {
      const allOrgs = await getOrgOptions()
      propOrgs.value = allOrgs.map(org => ({
        id: org.id, name: org.name,
        total_count: 0, running_count: 0, completed_count: 0, terminated_count: 0,
        latest_update_time: null,
      }))
    } catch { /* 无组织数据则空白 */ }
  }
}

function handleOrgSelect(orgId: number) {
  router.push(`/proposals/organization/${orgId}`)
}

async function fetchStatusCounts() {
  try {
    const results = await Promise.all([
      getProposals({ page_size: 1 }),
      getProposals({ page_size: 1, status: 'running' }),
      getProposals({ page_size: 1, status: 'completed' }),
      getProposals({ page_size: 1, status: 'terminated' }),
    ])
    statusCounts.value = {
      all: results[0].total,
      running: results[1].total,
      completed: results[2].total,
      terminated: results[3].total,
    }
  } catch { /* ignore */ }
}

async function fetchList() {
  loading.value = true
  try {
    const data = await getProposals({
      keyword: keyword.value || undefined,
      status: statusFilter.value === 'all' ? undefined : statusFilter.value,
      page: page.value,
      page_size: pageSize.value,
    })
    proposals.value = data?.items || []
    total.value = data?.total || 0
  } catch {
    proposals.value = []
    total.value = 0
  } finally { loading.value = false }
}

function handleStatusFilter(status: string) {
  statusFilter.value = status
  page.value = 1
  fetchList()
}

let searchTimer: ReturnType<typeof setTimeout> | null = null
function handleSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { page.value = 1; fetchList() }, 300)
}

function handleRowClick(row: ProposalListItem) { goDetail(row.id) }
function goDetail(id: number) { router.push(`/flows/instances/${id}`) }

// ========== 工具 ==========
function fmtTime(val: string | null): string {
  if (!val) return '-'
  return val.replace('T', ' ').substring(0, 16)
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
.proposal-management { /* max-width 由 AppLayout 内容区统一控制 */ }
.section-divider { display: flex; align-items: center; margin: 24px 0 16px; }
.section-label { font-size: 15px; font-weight: 600; color: var(--el-text-color-primary); margin: 0; }

.instance-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; flex-wrap: wrap; gap: 12px; &__right { display: flex; align-items: center; gap: 10px; flex-shrink: 0; } }

.filter-tabs { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.filter-tab { height: 32px; padding: 0 16px; border: 1px solid var(--el-border-color); background: #fff; border-radius: 6px; font-size: 13px; color: var(--el-text-color-regular); cursor: pointer; display: inline-flex; align-items: center; gap: 6px; line-height: 1; transition: all 0.2s; &:hover { border-color: var(--el-color-primary); color: var(--el-color-primary); } &.is-active { background: var(--el-color-primary); border-color: var(--el-color-primary); color: #fff; } }
.filter-label { display: inline-block; min-width: 3em; }
.filter-count { opacity: 0.7; }

.inst-name { font-weight: 500; color: var(--el-text-color-primary); }
.list-pagination { display: flex; justify-content: center; margin-top: 16px; }
.num { font-variant-numeric: tabular-nums; }
</style>
