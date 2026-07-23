<template>
  <!-- 首页 —— 统计卡片 + 我的待办 + 饼图/卡点追踪 + 各所柱状图 -->
  <div class="page-container" v-loading="loading">
    <div class="page-header">
      <div class="page-header__info">
        <h1 class="page-header__title">首页<span class="page-header__subtitle">全局运行概况</span></h1>
      </div>
      <div class="page-header__actions">
        <el-button :icon="Refresh" circle @click="fetchData" :loading="loading" />
      </div>
    </div>

    <!-- ====== 项目/方案 Tab 切换 ====== -->
    <div class="cat-tabs">
      <span
        class="cat-tab"
        :class="{ 'cat-tab--active': catTab === 'project' }"
        @click="catTab = 'project'"
      >项目</span>
      <span
        class="cat-tab"
        :class="{ 'cat-tab--active': catTab === 'proposal' }"
        @click="catTab = 'proposal'"
      >方案</span>
    </div>

    <!-- ====== 统计卡片 ====== -->
    <div class="stats-grid">
      <div class="stat-card stat-card--primary" :style="cardNavStyle(catTab === 'project' ? '/flows' : '/proposals')">
        <div class="stat-card__num stat-card__num--primary">{{ curStats.running_instances }}</div>
        <div class="stat-card__label">进行中{{ catLabel }}</div>
      </div>
      <div class="stat-card stat-card--success">
        <div class="stat-card__num stat-card__num--success">{{ curStats.archived_total }}</div>
        <div class="stat-card__label">已归档{{ catLabel }}</div>
      </div>
      <div class="stat-card stat-card--info">
        <div class="stat-card__num stat-card__num--info">{{ curStats.archived_this_month }}</div>
        <div class="stat-card__label">本月归档</div>
      </div>
      <div
        class="stat-card stat-card--danger"
        @click="catTab === 'project' ? $router.push('/profile') : undefined"
        :style="catTab === 'project' ? 'cursor:pointer' : ''"
      >
        <div class="stat-card__num stat-card__num--danger">
          {{ catTab === 'project' ? curStats.overdue_warnings : (curStats.total ?? curStats.overdue_warnings ?? 0) }}
        </div>
        <div class="stat-card__label">{{ catTab === 'project' ? '超期预警' : '方案总数' }}</div>
      </div>
    </div>

    <!-- ====== 我的待办快捷条 ====== -->
    <div class="my-tasks-bar" @click="$router.push('/profile')">
      <span class="my-tasks-bar__label">我的待办</span>
      <template v-if="myPendingCount > 0">
        <span v-if="myCounts.pending" class="my-tasks-bar__item">待处理 <b>{{ myCounts.pending }}</b></span>
        <span v-if="myCounts.pending || myCounts.checking" class="my-tasks-bar__sep">·</span>
        <span v-if="myCounts.checking" class="my-tasks-bar__item">待校验 <b>{{ myCounts.checking }}</b></span>
        <span v-if="(myCounts.pending || myCounts.checking) && myCounts.approval" class="my-tasks-bar__sep">·</span>
        <span v-if="myCounts.approval" class="my-tasks-bar__item">待审批 <b>{{ myCounts.approval }}</b></span>
      </template>
      <span v-else class="my-tasks-bar__item">暂无待办</span>
      <span class="my-tasks-bar__arrow">→</span>
    </div>

    <!-- ====== 饼图 + 卡点追踪 ====== -->
    <div class="dash-row">
      <div class="card dash-pie">
        <div class="card__header"><span class="card__title">各所运行中项目分布</span></div>
        <div class="card__body" style="display:flex;align-items:center;justify-content:center;padding:24px 20px;flex:1">
          <PieChart :items="orgPieItems" @click="handlePieClick" />
        </div>
      </div>

      <div class="card dash-bn">
        <div class="card__header">
          <span class="card__title">流程卡点追踪</span>
          <div style="display:flex;align-items:center;gap:8px">
            <el-select v-model="bottleneckOrgFilter" placeholder="全部组织" clearable size="small" style="width:120px">
              <el-option v-for="o in orgNames" :key="o" :label="o" :value="o" />
            </el-select>
          </div>
        </div>
        <div class="card__body" style="padding:0">
          <el-table :data="filteredBottleneck" stripe v-if="filteredBottleneck.length > 0" :row-class-name="tableRowClass" max-height="360" row-key="instance_id">
            <el-table-column prop="instance_name" label="项目" min-width="120" show-overflow-tooltip />
            <el-table-column prop="organization_name" label="所属组织" min-width="80" />
            <el-table-column label="难度" min-width="48" align="center">
              <template #default="{ row }">
                <span class="diff-badge" :class="'diff--' + (row.difficulty || '1')">{{ row.difficulty || '1' }}级</span>
              </template>
            </el-table-column>
            <el-table-column prop="current_node_name" label="当前节点" min-width="72" />
            <el-table-column prop="current_assignee_name" label="负责人" min-width="64" />
            <el-table-column label="进度" min-width="160" align="center">
              <template #default="{ row }">
                <div class="bt-progress">
                  <el-progress
                    :percentage="row.total_nodes > 0 ? Math.round((row.finished_count / row.total_nodes) * 100) : 0"
                    :stroke-width="8"
                    :show-text="false"
                  />
                  <span class="bt-progress__text">
                    {{ row.total_nodes > 0 ? Math.round((row.finished_count / row.total_nodes) * 100) : 0 }}%（{{ row.finished_count }}/{{ row.total_nodes }}）
                  </span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="状态" min-width="72" align="center">
              <template #default="{ row }">
                <span class="od-tag" :class="odClass(row.overdue_status)">{{ row.overdue_status }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" min-width="50" align="center" fixed="right">
              <template #default="{ row }">
                <el-button text type="primary" size="small" @click="$router.push(`/flows/instances/${row.instance_id}`)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div v-else style="text-align:center;padding:36px 0;color:var(--el-text-color-secondary);font-size:13px">暂无运行中流程</div>
        </div>
      </div>
    </div>

    <!-- ====== 各所项目概览（柱状图） ====== -->
    <div class="card">
      <div class="card__header"><span class="card__title">各所项目概览</span></div>
      <div class="card__body" style="padding:16px 20px">
        <BarChart :items="data.org_overview" @org-click="handleBarClick" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import { getDashboard, type DashboardData } from '@/api/dashboard'
import PieChart from './components/PieChart.vue'
import BarChart from './components/BarChart.vue'

const router = useRouter()
const loading = ref(false)
const catTab = ref<'project' | 'proposal'>('project')
const bottleneckOrgFilter = ref('')

const ORG_COLORS = ['#5470C6', '#91CC75', '#FAC858', '#EE6666', '#73C0DE', '#3BA272', '#FC8452', '#9A60B4', '#EA7CCC', '#6E7074']

const data = reactive<DashboardData>({
  stats: { running_instances: 0, archived_total: 0, archived_this_month: 0, overdue_warnings: 0 },
  proposal_stats: { running_instances: 0, archived_total: 0, archived_this_month: 0, overdue_warnings: 0 },
  task_distribution: [],
  bottleneck: [],
  overdue_list: [],
  org_overview: [],
  my_task_counts: { pending: 0, checking: 0, approval: 0 },
})

onMounted(() => fetchData())

async function fetchData() {
  loading.value = true
  try { const d = await getDashboard(); Object.assign(data, d) }
  catch { /* ok */ }
  finally { loading.value = false }
}

// ─── 统计卡片 ───
const catLabel = computed(() => catTab.value === 'project' ? '项目' : '方案')
const curStats = computed(() => catTab.value === 'project' ? data.stats : data.proposal_stats)

function cardNavStyle(to: string) {
  return catTab.value === 'project' ? 'cursor:pointer' : ''
}

// ─── 我的待办 ───
/** 从后端 my_task_counts 读取当前用户个人待办数 */
const myCounts = computed(() => data.my_task_counts)
const myPendingCount = computed(() => myCounts.value.pending + myCounts.value.checking + myCounts.value.approval)

// ─── 饼图 → 跳转所内主页 ───
function handlePieClick(orgId: string) {
  router.push(`/flows/organization/${orgId}`)
}

// ─── 柱状图 → 跳转所内主页 ───
function handleBarClick(orgId: number) {
  router.push(`/flows/organization/${orgId}`)
}

// ─── 卡点追踪 ───
const orgNames = computed(() => [...new Set(data.bottleneck.map(b => b.organization_name).filter(Boolean))].sort())
const filteredBottleneck = computed(() =>
  bottleneckOrgFilter.value ? data.bottleneck.filter(b => b.organization_name === bottleneckOrgFilter.value) : data.bottleneck
)
/** 饼图数据 */
const orgPieItems = computed(() => {
  return data.org_overview
    .filter(o => o.running_count > 0)
    .map((o, i) => ({
      status: String(o.org_id),
      label: o.org_name,
      color: ORG_COLORS[i % ORG_COLORS.length],
      count: o.running_count,
    }))
})

// ─── table helpers ───
function tableRowClass({ row }: any) {
  if (row.overdue_status === '已逾期') return 'r--red'
  if (row.overdue_status === '即将逾期') return 'r--yel'
  if (row.priority === 'urgent') return 'r--pri-urgent'
  if (row.priority === 'high') return 'r--pri-high'
  return ''
}
function odClass(s: string) { return s === '已逾期' ? 'od--r' : s === '即将逾期' ? 'od--y' : 'od--g' }
</script>

<style lang="scss" scoped>
/* ─── 页面标题 ─── */
.page-header__subtitle { margin-left: 12px; font-weight: 400; }

/* ─── 分类 Tab ─── */
.cat-tabs { display: flex; gap: 4px; margin-bottom: 16px; }
.cat-tab {
  padding: 6px 18px; border-radius: 6px 6px 0 0; font-size: 14px; cursor: pointer;
  color: var(--el-text-color-secondary); background: var(--el-fill-color-light);
  transition: all .2s; user-select: none; border: 1px solid transparent; border-bottom: none;
  &:hover { color: var(--el-color-primary); }
  &--active {
    color: var(--el-color-primary); background: #fff; border-color: var(--el-border-color-light);
    font-weight: 600;
  }
}

/* ─── 统计卡片 ─── */
.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 16px; }

.stat-card {
  background: #fff; border: 1px solid var(--el-border-color-light);
  border-radius: 10px; padding: 24px 20px; text-align: center; cursor: default;
  border-bottom: 3px solid transparent;
  transition: box-shadow .2s, transform .2s;
  &:hover { box-shadow: 0 4px 16px rgba(0,0,0,.08); transform: translateY(-1px); }

  &__num { font-size: 34px; font-weight: 700; line-height: 1.2; font-variant-numeric: tabular-nums; }
  &__num--primary { color: var(--el-color-primary); }
  &__num--success { color: var(--el-color-success); }
  &__num--info    { color: #409EFF; }
  &__num--danger  { color: var(--el-color-danger); }

  &__label { font-size: 14px; color: var(--el-text-color-secondary); margin-top: 6px; }

  &--primary { border-bottom-color: var(--el-color-primary); }
  &--success { border-bottom-color: var(--el-color-success); }
  &--info    { border-bottom-color: #409EFF; }
  &--danger  { border-bottom-color: var(--el-color-danger); }
}

/* ─── 我的待办 ─── */
.my-tasks-bar {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 18px; margin-bottom: 20px;
  background: var(--el-color-primary-light-9); border-radius: 8px;
  font-size: 13px; color: var(--el-text-color-regular); cursor: pointer;
  transition: background .2s;
  &:hover { background: var(--el-color-primary-light-8); }
  &__label { font-weight: 500; margin-right: 4px; }
  &__item b { color: var(--el-color-primary); font-size: 15px; }
  &__sep { color: var(--el-text-color-placeholder); }
  &__arrow { margin-left: auto; color: var(--el-text-color-placeholder); font-size: 14px; }
}

/* ─── 双栏弹性 ─── */
.dash-row { display: grid; grid-template-columns: minmax(300px, 420px) 1fr; gap: 20px; margin-bottom: 20px; }
.dash-pie { min-width: 0; display: flex; flex-direction: column; }
.dash-bn { min-width: 0; overflow: hidden; :deep(.el-table__cell) { padding: 10px 0; } }

/* ─── 进度条 ─── */
.bt-progress {
  display: flex; align-items: center; gap: 8px; padding: 4px 8px;
  :deep(.el-progress) { flex: 1; min-width: 60px; }
  :deep(.el-progress-bar__outer) { border-radius: 4px; }
}
.bt-progress__text { font-size: 12px; color: var(--el-text-color-secondary); white-space: nowrap; flex-shrink: 0; }

/* ─── 逾期标签 ─── */
.od-tag { font-size: 12px; padding: 2px 10px; border-radius: 10px; font-weight: 500; }
.od--r { background: #fde2e2; color: #c0392b; }
.od--y { background: #fef5e7; color: #d68910; }
.od--g { background: #eafaf1; color: #1e8449; }

/* ─── 难度 badge ─── */
.diff-badge {
  font-size: 12px; font-weight: 500; padding: 1px 8px; border-radius: 10px;
  &.diff--1 { color: #1e8449; background: #eafaf1; }
  &.diff--2 { color: #2471a3; background: #eaf2f8; }
  &.diff--3 { color: #b87333; background: #fef5e7; }
  &.diff--4 { color: #fff; background: var(--el-color-danger); }
}
</style>

<style lang="scss">
.r--red td { background: #fef0f0 !important; }
.r--yel td { background: #fffaf0 !important; }
.r--pri-urgent td { background: #fde8e8 !important; }
.r--pri-high td { background: #fef3e2 !important; }
</style>
