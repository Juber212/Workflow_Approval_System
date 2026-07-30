<template>
  <!-- 首页 —— 统计卡片 + 我的待办 + 饼图/卡点追踪 + 各所柱状图 -->
  <div class="page-container" v-loading="loading">
    <div class="page-header">
      <div class="page-header__info">
        <h1 class="page-header__title">首页<span class="page-header__subtitle">全局运行概况</span></h1>
      </div>
      <div class="page-header__actions">
        <el-button :icon="Refresh" circle @click="fetchData" :loading="loading" />
        <NotificationBell />
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

    <!-- ====== 统计卡片 —— 点击跳转对应筛选页 ====== -->
    <div class="stats-grid">
      <!-- 进行中 → 流程管理页预选运行中 -->
      <div class="stat-card stat-card--primary stat-card--clickable"
           @click="$router.push(catTab === 'project' ? { name: 'Flows', query: { status: 'running' } } : { name: 'Proposals', query: { status: 'running' } })">
        <div class="stat-card__num stat-card__num--primary">{{ curStats.running_instances }}</div>
        <div class="stat-card__label">进行中{{ catLabel }}</div>
      </div>
      <!-- 已归档 → 流程管理页预选已完成 -->
      <div class="stat-card stat-card--success stat-card--clickable"
           @click="$router.push(catTab === 'project' ? { name: 'Flows', query: { status: 'completed' } } : { name: 'Proposals', query: { status: 'completed' } })">
        <div class="stat-card__num stat-card__num--success">{{ curStats.archived_total }}</div>
        <div class="stat-card__label">已归档{{ catLabel }}</div>
      </div>
      <!-- 本月归档 → 同已归档（用高级搜索日期筛选区分） -->
      <div class="stat-card stat-card--info stat-card--clickable"
           @click="$router.push(catTab === 'project' ? { name: 'Flows', query: { status: 'completed' } } : { name: 'Proposals', query: { status: 'completed' } })">
        <div class="stat-card__num stat-card__num--info">{{ curStats.archived_this_month }}</div>
        <div class="stat-card__label">本月归档</div>
      </div>
      <!-- 超期预警 → 独立超期预警页面 -->
      <div class="stat-card stat-card--danger stat-card--clickable"
           @click="$router.push({ name: 'OverdueWarning' })">
        <div class="stat-card__num stat-card__num--danger">{{ curStats.overdue_warnings }}</div>
        <div class="stat-card__label">超期预警</div>
      </div>
    </div>

    <!-- ====== 饼图 + 卡点追踪 ====== -->
    <div class="dash-row">
      <div class="card dash-pie">
        <div class="card__header"><span class="card__title">各所运行中{{ catLabel }}分布</span></div>
        <div class="card__body" style="display:flex;align-items:center;justify-content:center;padding:24px 20px;flex:1">
          <PieChart :items="orgPieItems" @click="handlePieClick" />
        </div>
      </div>

      <div class="card dash-bn">
        <div class="card__header">
          <span class="card__title">{{ catLabel }}卡点追踪</span>
          <div style="display:flex;align-items:center;gap:8px">
            <el-select v-model="bottleneckOrgFilter" placeholder="全部组织" clearable size="small" style="width:120px">
              <el-option v-for="o in orgNames" :key="o" :label="o" :value="o" />
            </el-select>
          </div>
        </div>
        <div class="card__body" style="padding:0">
          <el-table :data="filteredBottleneck" stripe border v-if="filteredBottleneck.length > 0" :row-class-name="tableRowClass" max-height="360" row-key="instance_id">
            <el-table-column prop="instance_name" :label="catLabel" min-width="120" show-overflow-tooltip />
            <el-table-column prop="organization_name" label="所属组织" min-width="80" show-overflow-tooltip />
            <!-- 项目专属列：难度 / 当前节点 / 进度 -->
            <el-table-column v-if="catTab === 'project'" label="难度" min-width="72">
              <template #default="{ row }">
                <span class="diff-badge" :class="'diff--' + (row.difficulty || '1')">{{ row.difficulty || '1' }}级</span>
              </template>
            </el-table-column>
            <el-table-column v-if="catTab === 'project'" prop="current_node_name" label="当前节点" min-width="72" show-overflow-tooltip />
            <el-table-column prop="current_handlers" label="当前处理人" min-width="80" show-overflow-tooltip />
            <el-table-column v-if="catTab === 'project'" label="进度" min-width="160">
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
            <el-table-column label="状态" min-width="72">
              <template #default="{ row }">
                <span class="od-tag" :class="odClass(row.overdue_status)">{{ row.overdue_status }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" min-width="60" fixed="right" align="left" header-align="left">
              <template #default="{ row }">
                <el-button class="btn-cell" text type="primary" size="small" @click="$router.push(catTab === 'project' ? { name: 'InstanceDetail', params: { id: row.instance_id } } : { name: 'ProposalDetail', params: { id: row.instance_id } })">详情</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div v-else style="text-align:center;padding:36px 0;color:var(--el-text-color-secondary);font-size:13px">暂无运行中{{ catLabel }}</div>
        </div>
      </div>
    </div>

    <!-- ====== 我的待办列表 ====== -->
    <div class="card" style="margin-bottom:20px">
      <div class="card__header">
        <span class="card__title">我的待办</span>
        <el-button text type="primary" size="small" @click="$router.push({ name: 'Profile' })">查看更多 →</el-button>
      </div>
      <div class="card__body" style="padding:0">
        <el-table
          :data="curPending" stripe border
          v-if="curPending.length > 0"
          :row-class-name="(d: any) => deadlineRowClass(d)"
          row-key="id" max-height="360"
        >
          <!-- 类型标签 -->
          <el-table-column label="类型" min-width="68">
            <template #default="{ row }">
              <span class="pt-tag" :class="'pt--' + row.type">{{ row.type_label }}</span>
            </template>
          </el-table-column>
          <!-- 项目/方案名称 -->
          <el-table-column prop="instance_name" :label="catLabel + '名称'" min-width="130" show-overflow-tooltip />
          <!-- 当前节点 -->
          <el-table-column prop="node_name" label="当前节点" min-width="80" show-overflow-tooltip />
          <!-- 优先级 -->
          <el-table-column label="优先级" min-width="72">
            <template #default="{ row }">
              <span class="pri-badge" :class="'pri--' + row.priority">{{ priLabel(row.priority) }}</span>
            </template>
          </el-table-column>
          <!-- 截止时间 -->
          <el-table-column label="截止时间" min-width="120">
            <template #default="{ row }">
              <span v-if="row.deadline">{{ formatTime(row.deadline) }}</span>
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>
          <!-- 操作 -->
          <el-table-column label="操作" min-width="60" fixed="right" align="left" header-align="left">
            <template #default="{ row }">
              <el-button class="btn-cell" text type="primary" size="small" @click="handleMyTaskClick(row)">处理</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div v-else style="text-align:center;padding:36px 0;color:var(--el-text-color-secondary);font-size:13px">暂无待办{{ catLabel }}</div>
      </div>
    </div>

    <!-- ====== 各所项目概览（柱状图） ====== -->
    <div class="card">
      <div class="card__header"><span class="card__title">各所{{ catLabel }}概览</span></div>
      <div class="card__body" style="padding:16px 20px">
        <BarChart :items="curOrgOverview" @org-click="handleBarClick" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { getDashboard, type DashboardData, type MyPendingItem } from '@/api/dashboard'
import PieChart from './components/PieChart.vue'
import BarChart from './components/BarChart.vue'
import NotificationBell from '@/components/NotificationBell.vue'
import { priLabel } from '@/utils/labels'
import { formatTime } from '@/utils/format'

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
  proposal_bottleneck: [],  // 方案卡点追踪（简化列）
  overdue_list: [],
  org_overview: [],
  proposal_org_overview: [],  // 各所方案概览（tab 切换用）
  my_task_counts: { pending: 0, checking: 0, approval: 0 },
  my_pending: [],           // 当前用户待办列表（项目视图）
  proposal_my_pending: [],   // 当前用户待办列表（方案视图）
})

onMounted(() => fetchData())

async function fetchData() {
  loading.value = true
  try { const d = await getDashboard(); Object.assign(data, d) }
  catch { ElMessage.error('加载首页数据失败，请检查网络后刷新页面') }
  finally { loading.value = false }
}

// ─── 统计卡片 ───
const catLabel = computed(() => catTab.value === 'project' ? '项目' : '方案')
const curStats = computed(() => catTab.value === 'project' ? data.stats : data.proposal_stats)
/** 根据 tab 切换图表数据源 */
const curOrgOverview = computed(() => catTab.value === 'project' ? data.org_overview : data.proposal_org_overview)

// ─── 我的待办列表（跟随 tab 切换项目/方案） ───
const curPending = computed(() => catTab.value === 'project' ? data.my_pending : data.proposal_my_pending)

/** 格式化截止时间 */
/** 逾期/临期行标色 */
function deadlineRowClass({ row }: any): string {
  if (row?.is_overdue) return 'r--red'
  if (row?.days_remaining != null && row.days_remaining <= 1) return 'r--yel'
  return ''
}

/** 点击待办行 → 跳转对应处理页 */
function handleMyTaskClick(row: { type: string; id: number }) {
  const routeMap: Record<string, string> = { task: 'TaskDetail', check: 'CheckDetail', approval: 'ApprovalDetail', endorse: 'EndorseDetail', endorsement: 'EndorseDetail' }
  const routeName = routeMap[row.type]
  if (routeName) router.push({ name: routeName, params: { id: row.id } })
}

// ─── 饼图 → 跳转所内主页（跟随 tab） ───
function handlePieClick(orgId: string) {
  const routeName = catTab.value === 'proposal' ? 'OrgProposalHome' : 'OrgHome'
  router.push({ name: routeName, params: { orgId } })
}

// ─── 柱状图 → 跳转所内主页（跟随 tab） ───
function handleBarClick(orgId: number) {
  const routeName = catTab.value === 'proposal' ? 'OrgProposalHome' : 'OrgHome'
  router.push({ name: routeName, params: { orgId } })
}

// ─── 卡点追踪（跟随 tab 切换数据源） ───
const curBottleneck = computed(() => catTab.value === 'project' ? data.bottleneck : data.proposal_bottleneck)
const orgNames = computed(() => [...new Set(curBottleneck.value.map(b => b.organization_name).filter(Boolean))].sort())
const filteredBottleneck = computed(() =>
  bottleneckOrgFilter.value ? curBottleneck.value.filter(b => b.organization_name === bottleneckOrgFilter.value) : curBottleneck.value
)
/** 饼图数据（跟随 tab 切换项目/方案） */
const orgPieItems = computed(() => {
  return curOrgOverview.value
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

  // 可点击卡片
  &--clickable { cursor: pointer; }
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

/* ─── 我的待办类型标签 ─── */
.pt-tag {
  font-size: 12px; padding: 2px 8px; border-radius: 10px; font-weight: 500;
  &.pt--task     { background: #eaf2f8; color: #2471a3; }  // 待办=蓝
  &.pt--check    { background: #fef5e7; color: #b87333; }  // 校验=橙
  &.pt--approval { background: #eafaf1; color: #1e8449; }  // 审批=绿
}

/* ─── 优先级徽标 ─── */
.pri-badge {
  font-size: 12px; padding: 1px 8px; border-radius: 10px; font-weight: 500;
  &.pri--urgent  { background: #fde2e2; color: #c0392b; }  // 紧急=红
  &.pri--high    { background: #fef5e7; color: #d68910; }  // 高=黄
  &.pri--normal  { background: #eaf2f8; color: #2471a3; }  // 普通=蓝
  &.pri--low     { background: #f2f3f5; color: #86909c; }  // 低=灰
}

/* ─── 逾期文本 ─── */
.text-muted { color: var(--el-text-color-placeholder); }

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
