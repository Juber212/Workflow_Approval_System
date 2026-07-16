<template>
  <!-- 首页 —— 全局统计 + 饼图 + 卡点追踪 + 超期预警 + 各所概览（PRD §4） -->
  <div class="page-container" v-loading="loading">
    <div class="page-header">
      <div class="page-header__info">
        <h1 class="page-header__title">首页<span class="page-header__subtitle">全局运行概况</span></h1>
      </div>
      <div class="page-header__actions">
        <el-button :icon="Refresh" circle @click="fetchData" :loading="loading" />
      </div>
    </div>

    <!-- ====== 统计卡片 ====== -->
    <div class="stats-grid">
      <div class="stat-card stat-card--primary" @click="$router.push('/flows')">
        <div class="stat-card__num stat-card__num--primary">{{ data.stats.running_instances }}</div>
        <div class="stat-card__label">进行中项目</div>
      </div>
      <div class="stat-card stat-card--success">
        <div class="stat-card__num stat-card__num--success">{{ data.stats.archived_total }}</div>
        <div class="stat-card__label">已归档项目</div>
      </div>
      <div class="stat-card stat-card--info">
        <div class="stat-card__num stat-card__num--info">{{ data.stats.archived_this_month }}</div>
        <div class="stat-card__label">本月归档</div>
      </div>
      <div class="stat-card stat-card--danger" @click="$router.push('/profile')">
        <div class="stat-card__num stat-card__num--danger">{{ data.stats.overdue_warnings }}</div>
        <div class="stat-card__label">超期预警</div>
      </div>
    </div>

    <!-- ====== 超期预警 ====== -->
    <div class="card">
      <div class="card__header"><span class="card__title">⚠️ 超期预警</span></div>
      <div class="card__body" style="padding:0">
        <el-table :data="data.overdue_list" stripe v-if="data.overdue_list.length > 0">
          <el-table-column prop="instance_name" label="项目" min-width="150" show-overflow-tooltip />
          <el-table-column prop="node_name" label="当前节点" min-width="100" />
          <el-table-column prop="assignee_name" label="负责人" min-width="68" />
          <el-table-column label="截止时间" min-width="96">
            <template #default="{ row }">{{ fmt(row.deadline) }}</template>
          </el-table-column>
          <el-table-column label="剩余天数" min-width="108">
            <template #default="{ row }">
              <span :class="row.is_overdue ? 'c-red' : 'c-ora'">{{ row.days_label }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="55" align="center">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click="$router.push(`/flows/instances/${row.instance_id}`)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div v-else style="text-align:center;padding:36px 0;color:var(--el-text-color-secondary);font-size:13px">🎉 暂无超期任务</div>
      </div>
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
            <el-button size="small" text @click="toggleAllExpand">{{ allExpanded ? '收起全部' : '展开全部' }}</el-button>
            <el-select v-model="bottleneckOrgFilter" placeholder="全部组织" clearable size="small" style="width:120px">
              <el-option v-for="o in orgNames" :key="o" :label="o" :value="o" />
            </el-select>
          </div>
        </div>
        <div class="card__body" style="padding:0">
          <el-table :data="filteredBottleneck" stripe v-if="filteredBottleneck.length > 0" :row-class-name="tableRowClass" max-height="360" row-key="instance_id" :expand-row-keys="expandedRows" @expand-change="onExpandChange">
            <el-table-column type="expand">
              <template #default="{ row }">
                <div class="bt-chain">
                  <template v-for="(seg, i) in row.progress_chain" :key="i">
                    <span v-if="i > 0" class="bt-arr">→</span>
                    <span class="bt-node" :class="chainNodeClass(seg)">{{ chainNodeLabel(seg) }}</span>
                  </template>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="instance_name" label="项目" min-width="120" show-overflow-tooltip />
            <el-table-column prop="organization_name" label="所属组织" min-width="80" />
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

    <!-- ====== 各所概览 ====== -->
    <div class="card">
      <div class="card__header"><span class="card__title">各所流程概览</span></div>
      <div class="card__body" style="padding:0">
        <template v-if="data.org_overview.length > 0">
          <el-collapse v-model="activeOrgs">
            <el-collapse-item v-for="org in data.org_overview" :key="org.org_id" :name="org.org_id">
              <template #title>
                <span class="ov-title">{{ org.org_name }}</span>
                <el-tag size="small" effect="plain" style="margin-left:8px">运行中 {{ org.running_count }}</el-tag>
              </template>
              <div v-if="org.instances.length === 0" class="ov-empty">暂无运行中项目</div>
              <el-table v-else :data="org.instances" size="small" stripe @row-click="(row: any) => $router.push(`/flows/instances/${row.id}`)" style="cursor:pointer">
                <el-table-column prop="name" label="项目名称" min-width="140" show-overflow-tooltip />
                <el-table-column prop="current_node_name" label="当前节点" min-width="100" />
                <el-table-column prop="current_assignee_name" label="负责人" min-width="72" />
                <el-table-column label="优先级" min-width="64" align="center">
                  <template #default="{ row }">
                    <span class="pri-sm" :class="'pri--' + row.priority">{{ pri(row.priority) }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="状态" min-width="64" align="center">
                  <template #default="{ row }">
                    <span class="status-tag" :class="statusClass(row.status)">{{ statusLabel(row.status) }}</span>
                  </template>
                </el-table-column>
              </el-table>
            </el-collapse-item>
          </el-collapse>
        </template>
        <div v-else style="text-align:center;padding:36px 0;color:var(--el-text-color-secondary);font-size:13px">暂无组织数据</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { getDashboard, type DashboardData } from '@/api/dashboard'
import PieChart from './components/PieChart.vue'

const loading = ref(false)
const bottleneckOrgFilter = ref('')
/** el-collapse 当前展开的组织 ID 列表（饼图点击联动） */
const activeOrgs = ref<number[]>([])
/** 卡点追踪表格当前展开的行 ID 列表 */
const expandedRows = ref<number[]>([])

/** 组织饼图色板（最多支持 10 个组织） */
const ORG_COLORS = ['#5470C6', '#91CC75', '#FAC858', '#EE6666', '#73C0DE', '#3BA272', '#FC8452', '#9A60B4', '#EA7CCC', '#6E7074']

const data = reactive<DashboardData>({
  stats: { running_instances: 0, archived_total: 0, archived_this_month: 0, overdue_warnings: 0 },
  task_distribution: [],
  bottleneck: [],
  overdue_list: [],
  org_overview: [],
})

onMounted(() => fetchData())

async function fetchData() {
  loading.value = true
  try { const d = await getDashboard(); Object.assign(data, d) }
  catch { /* ok */ }
  finally { loading.value = false }
}

// ─── computed ───
const orgNames = computed(() => [...new Set(data.bottleneck.map(b => b.organization_name).filter(Boolean))].sort())
const filteredBottleneck = computed(() =>
  bottleneckOrgFilter.value ? data.bottleneck.filter(b => b.organization_name === bottleneckOrgFilter.value) : data.bottleneck
)

/** 是否所有行已展开 */
const allExpanded = computed(() => {
  const ids = filteredBottleneck.value.map(b => b.instance_id)
  return ids.length > 0 && ids.every(id => expandedRows.value.includes(id))
})

/** 一键展开/收起全部 */
function toggleAllExpand() {
  if (allExpanded.value) {
    expandedRows.value = []
  } else {
    expandedRows.value = filteredBottleneck.value.map(b => b.instance_id)
  }
}

/** 同步用户手动点击展开/收起 */
function onExpandChange(row: any, rows: any[]) {
  expandedRows.value = rows.map((r: any) => r.instance_id)
}

/** 饼图数据源：各所运行中项目分布（仅 running_count > 0 的组织） */
const orgPieItems = computed(() => {
  return data.org_overview
    .filter(o => o.running_count > 0)
    .map((o, i) => ({
      status: String(o.org_id),           // 扇区标识 → 组织 ID
      label: o.org_name,                   // 扇区名称 → 组织名称
      color: ORG_COLORS[i % ORG_COLORS.length],
      count: o.running_count,
    }))
})

// ─── helpers ───
/** 饼图点击扇区 → 展开/收起下方"各所概览"中对应组织 */
function handlePieClick(orgId: string) {
  const id = Number(orgId)
  const idx = activeOrgs.value.indexOf(id)
  if (idx >= 0) {
    activeOrgs.value.splice(idx, 1)       // 已展开 → 收起
  } else {
    activeOrgs.value.push(id)             // 未展开 → 展开
  }
}
function tableRowClass({ row }: any) {
  // 逾期状态优先高亮
  if (row.overdue_status === '已逾期') return 'r--red'
  if (row.overdue_status === '即将逾期') return 'r--yel'
  // 运行中实例按优先级高亮
  if (row.priority === 'urgent') return 'r--pri-urgent'
  if (row.priority === 'high') return 'r--pri-high'
  return ''
}
function odClass(s: string) { return s === '已逾期' ? 'od--r' : s === '即将逾期' ? 'od--y' : 'od--g' }
function fmt(d: string | null) { return d ? d.substring(0, 10) : '—' }
function pri(p: string) { const m: Record<string, string> = { urgent: '紧急', high: '高', normal: '普通', low: '低' }; return m[p] || p }
function statusClass(s: string) { return s === 'running' ? 'status-tag--running' : s === 'completed' ? 'status-tag--completed' : s === 'terminated' ? 'status-tag--terminated' : '' }
function statusLabel(s: string) { const m: Record<string, string> = { running: '运行中', completed: '已完成', terminated: '已终止' }; return m[s] || s }

/** 提取进度链片段的节点名称（去掉 emoji 图标前缀） */
function chainNodeLabel(seg: string): string {
  if (seg.startsWith('✅') || seg.startsWith('🔵') || seg.startsWith('⚪')) return seg.slice(2)
  return seg
}

/** 返回进度链片段的 CSS 类 */
function chainNodeClass(seg: string): string {
  if (seg.startsWith('🔵')) return 'bt-node--active'        // 当前节点高亮
  if (seg.startsWith('✅')) return 'bt-node--done'           // 已完成
  return 'bt-node--wait'                                     // 待开始
}
</script>

<style lang="scss" scoped>
/* ─── 页面标题 ─── */
.page-header__subtitle { margin-left: 12px; font-weight: 400; }
/* ─── 统计卡片 ─── */
.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 20px; }

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

  // 底部色条
  &--primary { border-bottom-color: var(--el-color-primary); }
  &--success { border-bottom-color: var(--el-color-success); }
  &--info    { border-bottom-color: #409EFF; }
  &--danger  { border-bottom-color: var(--el-color-danger); }
}

/* ─── 双栏 ─── */
.dash-row { display: grid; grid-template-columns: 400px 1fr; gap: 20px; margin-bottom: 20px; }
.dash-pie { min-width: 0; display: flex; flex-direction: column; }
.dash-bn { min-width: 0; overflow: hidden; :deep(.el-table__cell) { padding: 10px 0; } }

/* ─── 卡点追踪：可展开进度链 ─── */
.bt-chain { display: flex; flex-wrap: wrap; align-items: center; gap: 0; font-size: 13px; line-height: 1.8; padding: 10px 0; justify-content: center; }
.bt-arr { color: var(--el-text-color-placeholder); margin: 0 6px; flex-shrink: 0; font-size: 12px; }

.bt-node {
  display: inline-block; padding: 3px 12px; border-radius: 5px;
  font-size: 13px; white-space: nowrap; border: 1px solid var(--el-border-color);
  &--done { background: #eafaf1; color: #1e8449; border-color: #a3d9b1; }
  &--active { background: var(--el-color-primary-light-9); color: var(--el-color-primary); border-color: var(--el-color-primary); font-weight: 600; }
  &--wait { background: #fafafa; color: var(--el-text-color-placeholder); border-color: #eee; }
}

/* ─── 进度条 --- */
.bt-progress {
  display: flex; align-items: center; gap: 8px; padding: 4px 8px;
  :deep(.el-progress) { flex: 1; min-width: 60px; }
  :deep(.el-progress-bar__outer) { border-radius: 4px; }
}
.bt-progress__text { font-size: 12px; color: var(--el-text-color-secondary); white-space: nowrap; flex-shrink: 0; }

/* ─── 逾期 --- */
.od-tag { font-size: 12px; padding: 2px 10px; border-radius: 10px; font-weight: 500; }
.od--r { background: #fde2e2; color: #c0392b; }
.od--y { background: #fef5e7; color: #d68910; }
.od--g { background: #eafaf1; color: #1e8449; }

.c-red { color: var(--el-color-danger); font-weight: 500; }
.c-ora { color: var(--el-color-warning); font-weight: 500; }

/* ─── 各所概览 ─── */
:deep(.el-collapse-item__header) { padding-left: 20px !important; padding-right: 20px !important; }
:deep(.el-collapse-item__content) { padding-left: 20px; padding-right: 20px; }
.ov-title { font-weight: 500; font-size: 14px; }
.ov-empty { padding: 6px 0; color: var(--el-text-color-secondary); font-size: 12px; }

.pri-sm {
  font-size: 12px; padding: 2px 8px; border-radius: 8px; font-weight: 500;
  &.pri--urgent  { color: #fff; background: var(--el-color-danger); }
  &.pri--high    { color: #fff; background: var(--el-color-warning); }
  &.pri--normal  { color: var(--el-text-color-secondary); background: var(--el-fill-color); }
  &.pri--low     { color: var(--el-color-info); background: var(--el-color-info-light-9); }
}
</style>

<style lang="scss">
/* 全局：表格行高亮 */
.r--red td { background: #fef0f0 !important; }
.r--yel td { background: #fffaf0 !important; }
.r--pri-urgent td { background: #fde8e8 !important; }
.r--pri-high td { background: #fef3e2 !important; }
</style>
