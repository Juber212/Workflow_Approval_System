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

    <!-- 全部项目（P2-2 共享组件：筛选/搜索/分页/删除，fetch 权留在本页） -->
    <InstanceTable
      v-model:status-filter="instanceStatusFilter"
      v-model:page="instancePage"
      v-model:page-size="instancePageSize"
      :items="instances"
      :loading="instanceLoading"
      :total="instanceTotal"
      :counts="statusCounts"
      :init-date-range="initDateRange"
      show-org-column
      @refresh="fetchInstances"
      @refresh-counts="fetchStatusCounts"
      @row-click="(row: InstanceListItem) => goInstanceDetail(row.id)"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * 项目管理全局入口页 —— 组织卡片 + 全部项目（PRD P03）
 * 点击组织卡片 → 跳转 /flows/organization/:id
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getTemplateOrganizations, type OrgCardItem } from '@/api/template'
import { getInstances, type InstanceListItem } from '@/api/instance'
import { useBreadcrumb } from '@/composables/useBreadcrumb'
import OrgCardList from './components/OrgCardList.vue'
import InstanceTable, { type InstanceQuery } from './components/InstanceTable.vue'

const { setBreadcrumb } = useBreadcrumb()
const router = useRouter()
const route = useRoute()

// ========== 组织卡片 ==========
const orgs = ref<OrgCardItem[]>([])

// ========== 实例列表 ==========
// 数据与分页/状态筛选由本页持有（组件内 keyword/高级搜索等状态内部管理）
const instanceLoading = ref(false)
const instances = ref<InstanceListItem[]>([])
const instanceTotal = ref(0)
const instancePage = ref(1)
const instancePageSize = ref(20)
/** 实例状态筛选 —— 与 URL query.status 双向同步，支持外部链接预选 */
const validStatuses = ['all', 'running', 'completed', 'terminated']
const instanceStatusFilter = ref((validStatuses.includes(route.query.status as string) ? route.query.status : 'all') as string)
/** 各状态实例数量（从 API 获取） */
const statusCounts = ref<Record<string, number>>({})

// ========== 初始化 ==========
onMounted(async () => {
  setBreadcrumb([{ label: '首页', to: '/dashboard' }, { label: '项目管理' }])
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
/** 查询参数（keyword/日期/优先级/发起人）由 InstanceTable 组件经 refresh 事件上抛 */
async function fetchInstances(query?: InstanceQuery) {
  instanceLoading.value = true
  try {
    const data = await getInstances({
      page: instancePage.value,
      page_size: instancePageSize.value,
      status: instanceStatusFilter.value === 'all' ? undefined : instanceStatusFilter.value,
      keyword: query?.keyword,
      sort_by: instanceStatusFilter.value === 'running' ? 'priority' : undefined,
      priority: query?.priority,
      date_from: query?.date_from,
      date_to: query?.date_to,
      initiator_id: query?.initiator_id ?? undefined,
    })
    instances.value = data.items
    instanceTotal.value = data.total
  } catch { /* 拦截器统一处理 */ }
  finally { instanceLoading.value = false }
}

// M19：首页「本月归档」卡片跳转带本月起止日期 → 预筛本月完成项目
const initDateRange = computed<[string, string] | null>(() => {
  const df = route.query.date_from as string | undefined
  const dt = route.query.date_to as string | undefined
  return df && dt ? [df, dt] : null
})

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

function goInstanceDetail(id: number) { router.push({ name: 'InstanceDetail', params: { id } }) }
</script>

<style lang="scss" scoped>
.page-header__subtitle { margin-left: 12px; font-weight: 400; }

.flow-management { :deep(.caret-wrapper) { display: none; } :deep(.el-table__header) .el-icon { display: none !important; } :deep(.el-table .cell)::before, :deep(.el-table .cell)::after { display: none !important; content: none !important; } }
.section-divider { display: flex; align-items: center; margin: 24px 0 16px; }
.section-label { font-size: 15px; font-weight: 600; color: var(--el-text-color-primary); margin: 0; }
</style>
